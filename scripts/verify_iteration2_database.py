"""R5 iteration-2 acceptance on a disposable, loopback-only MySQL container.

Python standard library + Docker + an already-built Java 17 backend JAR.
Only the container created by this run is mutated/removed. Existing databases,
containers and applications are never selected. Credentials and dumps stay out
of the public result JSON. Exit nonzero on any failed assertion or cleanup.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import tempfile
import threading
import time
import traceback
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid
import xml.etree.ElementTree as ET
import zlib

from migrate_iteration2 import DockerMySQL, ROOT, TABLES, LEGACY_TABLES, MIGRATIONS

DB_DIR = ROOT / "backend/src/main/resources/db"
FIXTURE = ROOT / "docs/test/fixtures/iteration1-schema.sql"


def png(rgb):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\0" + bytes(rgb))) + chunk(b"IEND", b""))


class Verification:
    def __init__(self, args):
        self.args = args
        self.owner = uuid.uuid4().hex
        self.container = "oxstore-r5-it2-" + self.owner[:12]
        self.created = False
        self.app = None
        self.app_log = []
        self.root_password = secrets.token_hex(24)
        self.admin_password = "R5!" + secrets.token_hex(12)
        self.customer_password = "Buyer!" + secrets.token_hex(10)
        self.jwt_secret = secrets.token_hex(32)
        self.report = {"run_at": datetime.now().astimezone().isoformat(), "scope":
                       "Disposable MySQL: fresh schema, constraints, HTTP/JPA, V4/V5, backup restore, restart",
                       "base_commit": self.command(["git", "rev-parse", "HEAD"]).stdout.decode().strip(),
                       "checks": [], "http_requests": [], "source_sha256": {}}

    def command(self, args, payload=None, check=True, timeout=120, env=None):
        result = subprocess.run(args, input=payload, capture_output=True, timeout=timeout, env=env, cwd=ROOT)
        if check and result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-1500:])
        return result

    def verify(self, code, tasks, description, condition):
        self.report["checks"].append({"id": code, "tasks": tasks.split(","), "description": description,
                                      "status": "PASS" if condition else "FAIL"})
        print(f"{'PASS' if condition else 'FAIL'} {code}: {description}", flush=True)
        if not condition:
            raise AssertionError(f"{code}: {description}")

    def admin_sql(self, text):
        return self.command(["docker", "exec", "-i", self.container, "sh", "-c",
                             'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot --default-character-set=utf8mb4'],
                            payload=text.encode("utf-8"))

    def setup_database(self):
        env = os.environ.copy()
        env["MYSQL_ROOT_PASSWORD"] = self.root_password
        self.command(["docker", "run", "-d", "--pull=never", "--name", self.container,
                      "--label", "oxstore.r5.owner=" + self.owner,
                      "-e", "MYSQL_ROOT_PASSWORD", "-p", "127.0.0.1::3306", self.args.image,
                      "--character-set-server=utf8mb4", "--collation-server=utf8mb4_0900_ai_ci"], env=env)
        self.created = True
        self.wait_mysql()
        self.admin_sql(";".join(f"CREATE DATABASE {name} CHARACTER SET utf8mb4" for name in
                                 ("fresh", "legacy", "restored", "guarded", "partial", "staged", "incomplete")) + ";")
        self.fresh = DockerMySQL(self.container, "fresh")
        self.fresh.sql((DB_DIR / "schema.sql").read_text(encoding="utf-8"))
        self.report["mysql_version"] = self.fresh.query("SELECT VERSION()")
        self.report["image_id"] = self.command(["docker", "inspect", "--format", "{{.Image}}", self.container]).stdout.decode().strip()
        self.report["docker_version"] = self.command(["docker", "version", "--format", "{{.Server.Version}}"] ).stdout.decode().strip()
        self.verify("D01", "T-001", "Fresh schema creates the nine expected tables on real MySQL", self.fresh.tables() == TABLES)
        self.verify("D02", "T-001", "MySQL 8.0 server is used", self.report["mysql_version"].startswith("8.0."))

    def wait_mysql(self):
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            result = self.command(["docker", "exec", self.container, "sh", "-c",
                                   'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -h127.0.0.1 --protocol=TCP -uroot -N -e "SELECT 1"'], check=False)
            if result.returncode == 0 and result.stdout.strip() == b"1":
                return
            time.sleep(1)
        raise TimeoutError("Disposable MySQL did not become ready")

    def start_app(self, database, scratch):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        mapping = self.command(["docker", "port", self.container, "3306/tcp"]).stdout.decode().strip()
        assert mapping.startswith("127.0.0.1:")
        env = os.environ.copy()
        env.update(DB_HOST="127.0.0.1", DB_PORT=mapping.rsplit(":", 1)[1], DB_NAME=database,
                   DB_USERNAME="root", DB_PASSWORD=self.root_password, JWT_SECRET=self.jwt_secret,
                   ADMIN_INITIAL_PASSWORD=self.admin_password, TZ="Asia/Shanghai")
        self.base_url = f"http://127.0.0.1:{port}"
        self.app_log = []
        self.app = subprocess.Popen([self.args.java, "-jar", str(self.args.jar.resolve()),
                                    "--server.address=127.0.0.1", f"--server.port={port}",
                                    "--spring.jpa.hibernate.ddl-auto=validate", f"--shop.upload-dir={scratch / 'uploads'}"],
                                   cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        def consume():
            for line in self.app.stdout:
                text = line.decode("utf-8", errors="replace").rstrip()
                if any(value in text for value in (self.root_password, self.admin_password,
                                                   self.customer_password, self.jwt_secret)):
                    text = "[credential-related log omitted]"
                self.app_log.append(text)
        self.reader = threading.Thread(target=consume, daemon=True)
        self.reader.start()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if self.app.poll() is not None:
                raise RuntimeError("Application exited: " + "\n".join(self.app_log[-16:]))
            try:
                with urlopen(self.base_url + "/api/categories/tree", timeout=2) as response:
                    if (response.status == 200 and DockerMySQL(self.container, database).query(
                            "SELECT COUNT(*) FROM seller WHERE username='admin'") == "1"):
                        return
            except (URLError, HTTPError, TimeoutError, ConnectionError):
                time.sleep(.5)
        raise TimeoutError("Backend did not become ready")

    def stop_app(self):
        if self.app and self.app.poll() is None:
            self.app.terminate()
            try:
                self.app.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.app.kill()
                self.app.wait(timeout=10)
        if hasattr(self, "reader"):
            self.reader.join(timeout=5)

    def request(self, method, path, data=None, token=None, expected=200, files=None):
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        if files is None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode("utf-8") if data is not None else None
        else:
            boundary = "r5-" + uuid.uuid4().hex
            parts = []
            for name, value in data.items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
            for filename, content in files:
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="images"; filename="{filename}"\r\nContent-Type: image/png\r\n\r\n'.encode() + content + b"\r\n")
            body = b"".join(parts) + f"--{boundary}--\r\n".encode()
            headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
        try:
            with urlopen(Request(self.base_url + path, data=body, headers=headers, method=method), timeout=25) as response:
                status, raw = response.status, response.read()
        except HTTPError as error:
            status, raw = error.code, error.read()
        self.report["http_requests"].append({"method": method, "path": path, "status": status})
        if status != expected:
            raise AssertionError(f"{method} {path}: HTTP {status}, expected {expected}")
        result = json.loads(raw)
        return result.get("data")

    def login(self, username, seller=False):
        return self.request("POST", "/api/admin/auth/login" if seller else "/api/auth/login",
                            {"username": username, "password": self.admin_password if seller else self.customer_password})["token"]

    def publish(self, name, stock, category=None, images=(), expected=201):
        return self.request("POST", "/api/admin/products", {"name": name, "price": "12.50",
                             "stock": stock, "category2Id": category if category is not None else self.leaf,
                             "descriptionHtml": '<p><strong>OrionProbe</strong><img src="https://example.invalid/inline.png"></p>'},
                            self.seller, expected, files=images)

    def failed_sql(self, db, code, tasks, description, statement, error_code):
        result = db.sql(statement, check=False)
        self.verify(code, tasks, description, result.returncode != 0 and
                    f"ERROR {error_code} ".encode() in result.stderr)

    def fingerprint(self, db):
        body = "\n".join(table + "\n" + db.query(f"SELECT * FROM {table} ORDER BY id") for table in sorted(db.tables()))
        return hashlib.sha256(body.encode()).hexdigest()

    def schema_signature(self, db):
        return [db.query(query) for query in (
            "SELECT table_name,column_name,column_type,is_nullable FROM information_schema.columns "
            "WHERE table_schema=DATABASE() ORDER BY table_name,column_name",
            "SELECT table_name,constraint_name,constraint_type FROM information_schema.table_constraints "
            "WHERE constraint_schema=DATABASE() ORDER BY table_name,constraint_name",
            "SELECT table_name,index_name,non_unique,GROUP_CONCAT(column_name ORDER BY seq_in_index) "
            "FROM information_schema.statistics WHERE table_schema=DATABASE() "
            "GROUP BY table_name,index_name,non_unique ORDER BY table_name,index_name")]

    def http_and_constraints(self):
        db = self.fresh
        self.seller = self.login("admin", seller=True)
        customers = []
        for name in ("r5_buyer_a", "r5_buyer_b", "r5_never_ordered"):
            customers.append(self.request("POST", "/api/auth/register", {"username": name,
                              "password": self.customer_password, "phone": "13800000000"}, expected=201)["customerId"])
        self.a, self.b = self.login("r5_buyer_a"), self.login("r5_buyer_b")
        self.verify("A01", "T-002", "Three registered customers can share a phone; login succeeds", len(set(customers)) == 3)
        self.verify("A02", "T-002", "Passwords are BCrypt hashes and optional locations remain NULL",
                    db.query("SELECT COUNT(*) FROM customer WHERE password_hash LIKE '$2%' AND location IS NULL") == "3")
        self.request("POST", "/api/auth/register", {"username": "r5_buyer_a", "password": self.customer_password,
                      "phone": "13800000000"}, expected=409)
        self.failed_sql(db, "A03", "T-002", "Database rejects duplicate usernames",
                        "INSERT INTO customer(username,password_hash,phone,registered_at) "
                        "SELECT username,password_hash,phone,registered_at FROM customer LIMIT 1", 1062)
        self.request("GET", "/api/me/order-history", expected=401)
        self.request("GET", "/api/admin/customers", token=self.a, expected=403)
        self.verify("A04", "T-002,T-032", "History requires login and seller customer data rejects customer tokens", True)
        tree = self.request("GET", "/api/categories/tree")
        self.root, self.leaf = tree[0]["id"], tree[0]["children"][0]["id"]
        self.verify("C01", "T-006", "Initialized category tree has selectable second-level categories", bool(self.leaf))
        self.publish("invalid root category", 1, category=self.root, expected=400)
        self.verify("C02", "T-006", "Publishing against a root category is rejected", True)
        images = [("first.png", png((255, 0, 0))), ("second.png", png((0, 0, 255)))]
        product_a = self.publish("数据库商品A", 2, images=images)
        product_b = self.publish("数据库商品B", 1)
        pa, pb = product_a["productId"], product_b["productId"]
        self.verify("P01", "T-010,T-028", "Multiple products are ONLINE and first uploaded image is the main image",
                    db.query("SELECT COUNT(*) FROM product WHERE status='ONLINE'") == "2" and
                    product_a["mainImagePath"] == product_a["images"][0] and len(product_a["images"]) == 2)
        self.verify("P02", "T-028", "Image MIME/byte length/order are persisted; inline image is separate",
                    db.query(f"SELECT GROUP_CONCAT(CONCAT(sort_order,':',content_type,':',size_bytes) ORDER BY sort_order) "
                             f"FROM product_image WHERE product_id={pa}") ==
                    f"0:image/png:{len(images[0][1])},1:image/png:{len(images[1][1])}")
        with urlopen(self.base_url + product_a["images"][0], timeout=10) as response:
            self.verify("P03", "T-028", "Stored product image is retrievable without byte changes", response.read() == images[0][1])
        search = self.request("GET", f"/api/products?category2Id={self.leaf}&q=OrionProbe&page=1&size=1")
        no_tag = self.request("GET", "/api/products?q=strong")
        self.verify("C03", "T-006", "Anonymous browse combines category/search/pagination and excludes HTML tags",
                    search["total"] == 2 and len(search["items"]) == 1 and no_tag["total"] == 0)
        self.failed_sql(db, "P04", "T-014", "Negative inventory is rejected by MySQL", f"UPDATE product SET stock=-1 WHERE id={pa}", 3819)
        self.failed_sql(db, "P05", "T-006", "Invalid category reference is rejected by MySQL", f"UPDATE product SET category2_id=999999 WHERE id={pa}", 1452)
        self.failed_sql(db, "P06", "T-028", "Image position outside the nine-image range is rejected",
                        f"UPDATE product_image SET sort_order=9 WHERE product_id={pa} AND sort_order=0", 3819)
        self.failed_sql(db, "P07", "T-028", "Oversized persisted image metadata is rejected",
                        f"UPDATE product_image SET size_bytes=5242881 WHERE product_id={pa}", 3819)
        self.failed_sql(db, "P08", "T-028", "Half-populated image metadata is rejected",
                        f"UPDATE product_image SET size_bytes=NULL WHERE product_id={pa}", 3819)
        def submit(product, token):
            return self.request("POST", f"/api/products/{product}/intents", token=token)["intentId"]
        a1, a2 = submit(pa, self.a), submit(pa, self.b)
        a2_submitted_at = db.query(f"SELECT submitted_at FROM purchase_intent WHERE id={a2}")
        b1, b2 = submit(pb, self.a), submit(pb, self.b)
        self.verify("Q01", "T-010", "Each product starts its own queue sequence",
                    db.query("SELECT GROUP_CONCAT(queue_seq ORDER BY id) FROM purchase_intent") == "1,2,1,2")
        self.request("POST", f"/api/admin/intents/{a1}/start", token=self.seller)
        self.request("POST", f"/api/admin/intents/{b1}/start", token=self.seller)
        self.verify("Q02", "T-010", "Different products can each freeze one queue head without reducing stock",
                    db.query("SELECT COUNT(*) FROM purchase_intent WHERE status='IN_TRANSACTION'") == "2" and
                    db.query(f"SELECT stock FROM product WHERE id={pa}") == "2")
        self.request("POST", f"/api/admin/intents/{a2}/start", token=self.seller, expected=409)
        self.failed_sql(db, "Q03", "T-010", "MySQL forbids a second trading intent for the same product",
                        f"UPDATE purchase_intent SET status='IN_TRANSACTION' WHERE id={a2}", 1062)
        self.verify("H01", "T-018", "Queuing and in-progress intents do not appear in terminal history",
                    self.request("GET", "/api/me/order-history", token=self.a)["total"] == 0)
        self.request("POST", f"/api/admin/intents/{a1}/success", token=self.seller)
        self.verify("Q04", "T-010,T-014", "A success decrements one unit and leaves next head queued; B stays frozen",
                    db.query(f"SELECT CONCAT(stock,':',status) FROM product WHERE id={pa}") == "1:ONLINE" and
                    db.query(f"SELECT status FROM purchase_intent WHERE id={a2}") == "QUEUING" and
                    db.query(f"SELECT status FROM product WHERE id={pb}") == "FROZEN")
        self.request("POST", f"/api/admin/intents/{b1}/success", token=self.seller)
        self.verify("I01", "T-014,T-018", "Last sale takes product offline and writes failure history for its queued intent",
                    db.query(f"SELECT CONCAT(stock,':',status) FROM product WHERE id={pb}") == "0:OFFLINE" and
                    db.query(f"SELECT status FROM purchase_intent WHERE id={b2}") == "FAILED" and
                    db.query(f"SELECT status FROM order_history WHERE intent_id={b2}") == "FAILED")
        self.request("GET", f"/api/products/{pb}", expected=404)
        self.request("POST", f"/api/admin/intents/{a2}/start", token=self.seller)
        self.request("POST", f"/api/admin/intents/{a2}/fail", {"action": "REQUEUE"}, self.seller)
        self.verify("Q05", "T-010,T-018", "Requeue advances sequence while keeping original time and no terminal history",
                    db.query(f"SELECT queue_seq FROM purchase_intent WHERE id={a2}") == "3" and
                    db.query(f"SELECT submitted_at FROM purchase_intent WHERE id={a2}") == a2_submitted_at and
                    db.query(f"SELECT COUNT(*) FROM order_history WHERE intent_id={a2}") == "0")
        self.request("POST", f"/api/admin/intents/{a2}/start", token=self.seller)
        self.request("POST", f"/api/admin/intents/{a2}/fail", {"action": "DISCARD"}, self.seller)
        self.verify("H02", "T-018", "Discard creates exactly one FAILED history snapshot",
                    db.query(f"SELECT COUNT(*) FROM order_history WHERE intent_id={a2} AND status='FAILED'") == "1")
        db.sql(f"UPDATE product SET name='数据库商品A已变更' WHERE id={pa}")
        history = self.request("GET", "/api/me/order-history?page=1&size=1", token=self.a)
        page2 = self.request("GET", "/api/me/order-history?page=2&size=1", token=self.a)
        self.verify("H03", "T-018", "History pages contain stable snapshots and distinct descending records",
                    history["total"] == 2 and len(history["items"]) == 1 and
                    history["items"][0]["orderId"] != page2["items"][0]["orderId"] and
                    page2["items"][0]["productName"] == "数据库商品A")
        self.verify("H04", "T-018,T-032", "Buyer history is isolated by customer and contains only terminal results",
                    {i["status"] for i in self.request("GET", "/api/me/order-history", token=self.b)["items"]} == {"FAILED"})
        self.failed_sql(db, "H05", "T-018", "History rejects nonterminal states", "UPDATE order_history SET status='QUEUING' LIMIT 1", 3819)
        self.failed_sql(db, "H06", "T-018", "History rejects duplicate results for the same intent",
                        "INSERT INTO order_history(intent_id,customer_id,product_name_snapshot,submitted_at,status,transacted_at) "
                        "SELECT intent_id,customer_id,product_name_snapshot,submitted_at,status,transacted_at FROM order_history LIMIT 1", 1062)
        product_c = self.publish("手动上下架商品", 3)
        pc = product_c["productId"]
        c1 = submit(pc, self.a)
        self.request("POST", f"/api/admin/products/{pc}/offline", token=self.seller)
        self.verify("S01", "T-024", "Manual offline retains inventory and ends queued intents with FAILED history",
                    db.query(f"SELECT CONCAT(stock,':',status) FROM product WHERE id={pc}") == "3:OFFLINE" and
                    db.query(f"SELECT status FROM order_history WHERE intent_id={c1}") == "FAILED")
        self.request("PATCH", f"/api/admin/products/{pc}", {"stock": 0}, self.seller)
        self.request("PATCH", f"/api/admin/products/{pc}", {"stock": 2, "name": "forbidden edit"}, self.seller)
        self.verify("S02", "T-024", "Restock keeps OFFLINE and forbidden name edit does not change the product",
                    db.query(f"SELECT CONCAT(stock,':',status,':',name) FROM product WHERE id={pc}") == "2:OFFLINE:手动上下架商品")
        self.request("POST", f"/api/admin/products/{pc}/online", token=self.seller)
        self.verify("S03", "T-024", "Explicit manual online is persisted as a status event",
                    db.query(f"SELECT COUNT(*) FROM product_status_event WHERE product_id={pc} AND event_type='MANUAL_ONLINE'") == "1")
        db.sql("UPDATE customer SET registered_at='2026-10-28 01:00:00.000000'")
        listed = self.request("GET", "/api/admin/customers?page=1&size=1", token=self.seller)
        empty = self.request("GET", f"/api/admin/customers/{customers[2]}/order-history", token=self.seller)
        self.verify("R01", "T-032", "Seller pagination includes never-ordered customer, stable ID tie-break and optional-address text",
                    listed["total"] == 3 and listed["items"][0]["customerId"] == customers[2] and
                    listed["items"][0]["location"] == "未设置" and empty["total"] == 0)
        own = self.request("GET", "/api/me/order-history", token=self.a)
        seller_view = self.request("GET", f"/api/admin/customers/{customers[0]}/order-history", token=self.seller)
        self.verify("R02", "T-018,T-032", "Seller and buyer views of the same customer's terminal history agree", own == seller_view)
        index_names = db.query("SELECT DISTINCT index_name FROM information_schema.statistics WHERE table_schema=DATABASE()")
        self.verify("R03", "T-006,T-032", "Catalog, customer registration and history pagination indexes exist",
                    all(name in index_names.splitlines() for name in ("idx_product_category_status", "idx_product_status_time",
                        "idx_customer_registered", "idx_order_history_customer_time")))
        self.failed_sql(db, "Q06", "T-010", "Fresh schema rejects unknown intent statuses",
                        "UPDATE purchase_intent SET status='UNKNOWN' LIMIT 1", 3819)
        self.product_a, self.image_bytes, self.customers = product_a, images[0][1], customers

    def migrations(self, scratch):
        fixture = FIXTURE.read_text(encoding="utf-8-sig")
        seed = """
INSERT INTO seller(id,username,password_hash) VALUES(1,'legacy_admin','legacy-fixture-hash');
INSERT INTO product(id,name,description,image_path,price,status,published_at) VALUES
 (1,'旧商品中文','旧描述','/api/images/legacy.png',12.50,'ONLINE','2026-10-01 10:00:00'),
 (2,'历史售出商品','历史描述','/api/images/history.jpg',2.00,'SOLD','2026-09-30 10:00:00');
INSERT INTO purchase_intent(id,product_id,buyer_name,buyer_phone,token_hash,token_lookup,status,submitted_at,queue_seq) VALUES
 (1,2,'历史买家','13800000000','old-hash','old-lookup-1','SUCCESS','2026-10-01 09:00:00',1),
 (2,1,'排队买家','13800000000','old-hash','old-lookup-2','QUEUING','2026-10-01 10:01:00',1),
 (3,1,'失败买家','13800000000',NULL,NULL,'UNSOLD','2026-10-01 10:02:00',2);
INSERT INTO trade_attempt(id,intent_id,started_at,finished_at,result) VALUES
 (1,1,'2026-10-01 09:10:00','2026-10-01 09:20:00','SUCCESS');
INSERT INTO product_status_event(product_id,event_type,from_status,to_status,occurred_at) VALUES
 (1,'PUBLISHED',NULL,'ONLINE','2026-10-01 10:00:00'),
 (2,'TRADE_SUCCEEDED','FROZEN','SOLD','2026-10-01 09:20:00');
"""
        legacy = DockerMySQL(self.container, "legacy")
        legacy.sql(fixture + seed)
        before = self.fingerprint(legacy)
        upgraded = legacy.upgrade(scratch / "backups")
        self.verify("M01", "T-001", "Upgrade saves a nonempty backup before applying V4/V5",
                    upgraded["applied"] == ["V4", "V5"] and Path(upgraded["backup"]).stat().st_size > 0)
        self.verify("M02", "T-001,T-014", "Unknown legacy inventory becomes zero/offline without invented customers",
                    legacy.query("SELECT COUNT(*) FROM product WHERE stock=0 AND status='OFFLINE'") == "2" and
                    legacy.query("SELECT COUNT(*) FROM customer") == "0")
        self.verify("M03", "T-018,T-028", "Upgrade preserves names/images, finishes old queue, and omits guest history",
                    legacy.query("SELECT name FROM product WHERE id=1") == "旧商品中文" and
                    legacy.query("SELECT COUNT(*) FROM product_image") == "2" and
                    legacy.query("SELECT COUNT(*) FROM product_image WHERE content_type IS NULL AND size_bytes IS NULL") == "2" and
                    legacy.query("SELECT COUNT(*) FROM purchase_intent WHERE status='FAILED'") == "2" and
                    legacy.query("SELECT COUNT(*) FROM order_history") == "0")
        self.verify("M04", "T-001,T-002,T-006,T-010,T-014,T-018,T-024,T-028,T-032",
                    "Fresh and upgraded schemas agree on column types/nullability, constraints and indexes",
                    self.schema_signature(legacy) == self.schema_signature(self.fresh))
        after = self.fingerprint(legacy)
        repeat = legacy.upgrade(scratch / "backups")
        self.verify("M05", "T-001", "Repeated upgrade skips V4 and keeps all application data unchanged",
                    repeat["applied"] == ["V5"] and self.fingerprint(legacy) == after)
        self.failed_sql(legacy, "M06", "T-010", "Upgraded schema also rejects unknown intent statuses",
                        "UPDATE purchase_intent SET status='UNKNOWN' WHERE id=2", 3819)
        restored = DockerMySQL(self.container, "restored")
        restored.sql(Path(upgraded["backup"]).read_text(encoding="utf-8"))
        self.verify("M07", "T-001", "Backup restores the complete five-table legacy dataset exactly",
                    restored.tables() == LEGACY_TABLES and self.fingerprint(restored) == before)
        guarded = DockerMySQL(self.container, "guarded")
        guarded.sql(fixture + seed + "UPDATE purchase_intent SET status='IN_TRANSACTION' WHERE id=2;")
        guarded_before = self.fingerprint(guarded)
        try:
            guarded.upgrade(scratch / "backups")
        except RuntimeError:
            refused = True
        else:
            refused = False
        self.verify("M08", "T-001,T-010", "Upgrade refuses unfinished trades before schema/data mutation",
                    refused and self.fingerprint(guarded) == guarded_before and guarded.tables() == LEGACY_TABLES)
        result = guarded.sql((MIGRATIONS / "V4__iteration2_customer_inventory_catalog.sql").read_text(encoding="utf-8"), check=False)
        self.verify("M09", "T-001", "Direct V4 SQL also blocks unfinished trades before table changes",
                    result.returncode != 0 and guarded.tables() == LEGACY_TABLES and self.fingerprint(guarded) == guarded_before)
        partial = DockerMySQL(self.container, "partial")
        partial.sql(fixture + "CREATE TABLE category(id BIGINT PRIMARY KEY);")
        try:
            partial.upgrade(scratch / "backups")
        except RuntimeError:
            refused = True
        else:
            refused = False
        self.verify("M10", "T-001", "Partial V4 layouts are refused without inventing a recovery state",
                    refused and "stock" not in partial.columns("product"))
        staged = DockerMySQL(self.container, "staged")
        staged.sql(fixture + seed)
        staged.sql((MIGRATIONS / "V4__iteration2_customer_inventory_catalog.sql").read_text(encoding="utf-8"))
        staged.sql("ALTER TABLE product_image ADD COLUMN content_type VARCHAR(20) NULL AFTER sort_order;")
        staged.upgrade(scratch / "backups")
        self.verify("M11", "T-001,T-028", "V5 resumes after its metadata column step without duplicating data",
                    self.schema_signature(staged) == self.schema_signature(self.fresh) and
                    staged.query("SELECT COUNT(*) FROM product_image") == "2")
        incomplete = DockerMySQL(self.container, "incomplete")
        incomplete.sql((DB_DIR / "schema.sql").read_text(encoding="utf-8"))
        incomplete.sql("ALTER TABLE purchase_intent DROP FOREIGN KEY fk_intent_customer, "
                       "DROP INDEX idx_intent_customer_status_time, DROP COLUMN customer_id;")
        try:
            incomplete.upgrade(scratch / "backups")
        except RuntimeError:
            refused = True
        else:
            refused = False
        self.verify("M12", "T-001,T-010", "A nine-table layout missing an essential V4 relation is also refused",
                    refused and "customer_id" not in incomplete.columns("purchase_intent"))
        self.report["backup_restore"] = {"backup_sha256": upgraded["backup_sha256"],
                                         "before_data_sha256": before, "after_data_sha256": after,
                                         "restored_data_sha256": self.fingerprint(restored)}

    def restart(self, scratch):
        before = self.fingerprint(self.fresh)
        self.stop_app()
        self.command(["docker", "restart", self.container])
        self.wait_mysql()
        self.verify("E01", "T-001,T-018,T-024,T-028", "MySQL restart preserves all application rows", self.fingerprint(self.fresh) == before)
        self.start_app("fresh", scratch)
        self.seller = self.login("admin", seller=True)
        self.a = self.login("r5_buyer_a")
        self.verify("E02", "T-002,T-018", "Backend restart preserves password hashes, login and order history",
                    self.request("GET", "/api/me/order-history", token=self.a)["total"] == 3)
        with urlopen(self.base_url + self.product_a["images"][0], timeout=10) as response:
            self.verify("E03", "T-028", "Image bytes remain accessible after database/backend restart", response.read() == self.image_bytes)
        self.stop_app()
        self.start_app("legacy", scratch)
        self.verify("E04", "T-001,T-002,T-006", "JPA validation and backend startup also succeed on the upgraded legacy schema",
                    bool(self.login("admin", seller=True)))

    def finish(self):
        self.stop_app()
        if self.created:
            actual = self.command(["docker", "inspect", "--format", '{{index .Config.Labels "oxstore.r5.owner"}}', self.container]).stdout.decode().strip()
            if actual != self.owner:
                raise RuntimeError("Cleanup ownership check failed")
            self.command(["docker", "rm", "-f", "-v", self.container])
            self.created = False
            self.report["cleanup"] = "owned container and its anonymous volume removed; apps stopped"

    def save(self):
        for base in (ROOT / "backend/src/main", ROOT / "backend/src/test"):
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    self.report["source_sha256"][path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (Path(__file__), ROOT / "scripts/migrate_iteration2.py", FIXTURE, ROOT / "backend/pom.xml", self.args.jar):
            self.report["source_sha256"][path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        tests = []
        for xml in sorted((ROOT / "backend/target/surefire-reports").glob("TEST-*.xml")):
            suite = ET.parse(xml).getroot()
            for case in suite.findall("testcase"):
                tests.append({"class": case.attrib["classname"], "name": case.attrib["name"],
                              "status": "FAIL" if case.find("failure") is not None or case.find("error") is not None
                              else "SKIP" if case.find("skipped") is not None else "PASS"})
        self.report["junit"] = {"total": len(tests), "passed": sum(t["status"] == "PASS" for t in tests)}
        self.report["finished_at"] = datetime.now().astimezone().isoformat()
        self.args.output.parent.mkdir(parents=True, exist_ok=True)
        self.args.output.write_text(json.dumps(self.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.args.output.with_name("junit-results.json").write_text(json.dumps(tests, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="mysql:8.0.46")
    parser.add_argument("--java", default="java")
    parser.add_argument("--jar", type=Path, default=ROOT / "backend/target/shop-0.1.0.jar")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/test/evidence/r5-iteration2-20261028/mysql-results.json")
    args = parser.parse_args()
    run = Verification(args)
    run.report["java_version"] = run.command([args.java, "-version"]).stderr.decode("utf-8", errors="replace").strip()
    error = None
    try:
        with tempfile.TemporaryDirectory(prefix="oxstore-r5-it2-") as temp:
            scratch = Path(temp)
            run.setup_database()
            run.start_app("fresh", scratch)
            run.verify("D03", "T-001", "Backend validates real MySQL tables with Hibernate ddl-auto=validate", True)
            run.http_and_constraints()
            run.migrations(scratch)
            run.restart(scratch)
            run.stop_app()
    except Exception as exc:
        error = exc
        run.report["error"] = str(exc)
        traceback.print_exc()
    finally:
        try:
            run.finish()
        except Exception as exc:
            error = error or exc
            run.report["cleanup_error"] = str(exc)
        run.report["success"] = error is None
        run.save()
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
