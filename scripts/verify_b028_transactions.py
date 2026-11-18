"""R5 B-028: real-MySQL constraint and transaction verification of the challenge-B trade path.

Runs the packaged backend JAR (ddl-auto=validate) against a disposable MySQL and drives the real HTTP API
with genuinely concurrent requests (thread barrier). All assertions read the database through a separate
mysql client connection, never through the application. Covered: oversell across customers, idempotent
checkout/cart/move replays, cancel races (double cancel, cancel vs ship, cancel vs complete), exact one-time
stock restore, manual-stock additivity, cross-customer lock ordering, unbounded numbers, database-injected
failures at every write point (checkout, cancel, move-to-favorites), authorization with zero side effects,
legacy intent isolation, restart persistence and a final stock ledger.

Two database sources: --db docker (mysql:8.0.46 container created and removed by this run; the target
environment) or --db local (a throw-away mysqld instance in a temp directory on a random loopback port;
it never touches an installed service). Failed checks are recorded and the run continues, so one run
shows every defect. This is R5's DB-layer verification, not R2's independent business acceptance.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal, getcontext
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import traceback
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from migrate_iteration2 import DockerMySQL, ROOT
from verify_iteration2_database import DB_DIR

getcontext().prec = 200  # default 28 digits would silently round the 30-digit stock in exact-arithmetic checks
HUGE_STOCK = "123456789012345678901234567890"
HUGE_QTY = "98765432109876543210"


class LocalMySQL:
    """Same sql/query surface as DockerMySQL, over a mysql client on a throw-away local server."""

    def __init__(self, client, port, user, password, database):
        self.client, self.port, self.user, self.password, self.database = client, port, user, password, database

    def sql(self, statement, check=True):
        env = dict(os.environ, MYSQL_PWD=self.password)
        result = subprocess.run([self.client, "-h127.0.0.1", f"-P{self.port}", f"-u{self.user}",
                                 "--default-character-set=utf8mb4", "--batch", "--skip-column-names", self.database],
                                input=("SET NAMES utf8mb4;\n" + statement).encode("utf-8"), capture_output=True,
                                env=env, timeout=120)
        if check and result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-1200:])
        return result

    def query(self, statement):
        return self.sql(statement).stdout.decode("utf-8").replace("\r", "").strip()


class Resp:
    def __init__(self, status, code=None, message=None, data=None):
        self.status, self.code, self.message, self.data = status, code, message, data

    def brief(self):
        return f"{self.status}/{self.code}"


class Customer:
    def __init__(self, name, token, cid):
        self.name, self.token, self.id = name, token, cid


class B028:
    def __init__(self, args):
        self.args = args
        self.run = uuid.uuid4().hex[:6]
        self.n = 0
        self.container = "oxstore-b028-" + uuid.uuid4().hex[:10]
        self.created = False
        self.mysqld = None
        self.app = None
        self.app_log = []
        self.db_password = secrets.token_hex(16)
        self.admin_password = "R5!" + secrets.token_hex(12)
        self.customer_password = "Buyer!" + secrets.token_hex(10)
        self.jwt_secret = secrets.token_hex(32)
        self.initial = {}
        self.adjusted = set()
        self.ctx = {}
        self.report = {"run_at": datetime.now().astimezone().isoformat(), "db_source": args.db, "checks": [],
                       "scenario_errors": [], "http_request_count": 0,
                       "base_commit": self.sh(["git", "rev-parse", "HEAD"]).stdout.decode().strip()}

    # ---- plumbing -------------------------------------------------------------------------------
    def sh(self, args, payload=None, check=True, timeout=180, env=None):
        result = subprocess.run(args, input=payload, capture_output=True, timeout=timeout, env=env, cwd=ROOT)
        if check and result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-1500:])
        return result

    def check(self, code, tasks, description, condition, detail=None):
        status = "PASS" if condition else "FAIL"
        entry = {"id": code, "tasks": tasks.split(","), "description": description, "status": status}
        if detail is not None:
            entry["detail"] = detail
        self.report["checks"].append(entry)
        print(f"{status} {code}: {description}" + ("" if condition or detail is None else f"  -> {detail}"), flush=True)
        return condition

    def setup_error(self, response, what):
        raise RuntimeError(f"setup failed: {what}: {response.brief()} {response.message}")

    # ---- database ---------------------------------------------------------------------------------
    def start_database(self):
        if self.args.db == "docker":
            env = dict(os.environ, MYSQL_ROOT_PASSWORD=self.db_password)
            self.sh(["docker", "run", "-d", "--pull=never", "--name", self.container, "--label", "oxstore.r5.b028=1",
                     "-e", "MYSQL_ROOT_PASSWORD", "-p", "127.0.0.1::3306", self.args.image,
                     "--character-set-server=utf8mb4", "--collation-server=utf8mb4_0900_ai_ci"], env=env)
            self.created = True
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                r = self.sh(["docker", "exec", self.container, "sh", "-c",
                             'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -h127.0.0.1 --protocol=TCP -uroot -N -e "SELECT 1"'],
                            check=False)
                if r.returncode == 0 and r.stdout.strip() == b"1":
                    break
                time.sleep(1)
            else:
                raise TimeoutError("MySQL container did not become ready")
            self.sh(["docker", "exec", "-i", self.container, "sh", "-c",
                     'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot'], payload=b"CREATE DATABASE b028 CHARACTER SET utf8mb4;")
            mapping = self.sh(["docker", "port", self.container, "3306/tcp"]).stdout.decode().strip()
            self.db_host, self.db_port, self.db_user = "127.0.0.1", mapping.rsplit(":", 1)[1], "root"
            self.db = DockerMySQL(self.container, "b028")
            self.report["image_id"] = self.sh(["docker", "inspect", "--format", "{{.Image}}", self.container]).stdout.decode().strip()
        else:
            bin_dir = Path(self.args.mysql_bin)
            mysqld, client = bin_dir / "mysqld.exe", bin_dir / "mysql.exe"
            self.tmp = Path(tempfile.mkdtemp(prefix="oxstore-b028-mysql-"))
            data = self.tmp / "data"
            self.sh([str(mysqld), "--no-defaults", "--initialize-insecure", f"--datadir={data}", "--console"], timeout=300)
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            self.mysqld = subprocess.Popen([str(mysqld), "--no-defaults", f"--datadir={data}", f"--port={port}",
                                            "--bind-address=127.0.0.1", "--mysqlx=OFF", "--console",
                                            "--character-set-server=utf8mb4", "--collation-server=utf8mb4_0900_ai_ci"],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                r = subprocess.run([str(client), "-h127.0.0.1", f"-P{port}", "-uroot", "-N", "-e", "SELECT 1"],
                                   capture_output=True)
                if r.returncode == 0 and r.stdout.strip() == b"1":
                    break
                time.sleep(1)
            else:
                raise TimeoutError("Local mysqld did not become ready")
            admin = ("CREATE DATABASE b028 CHARACTER SET utf8mb4;"
                     f"CREATE USER 'b028'@'localhost' IDENTIFIED BY '{self.db_password}';"
                     f"CREATE USER 'b028'@'127.0.0.1' IDENTIFIED BY '{self.db_password}';"
                     "GRANT ALL ON *.* TO 'b028'@'localhost'; GRANT ALL ON *.* TO 'b028'@'127.0.0.1';")
            subprocess.run([str(client), "-h127.0.0.1", f"-P{port}", "-uroot"], input=admin.encode(), capture_output=True, check=True)
            self.db_host, self.db_port, self.db_user = "127.0.0.1", str(port), "b028"
            self.db = LocalMySQL(str(client), port, "b028", self.db_password, "b028")
        self.report["mysql_version"] = self.db.sql("SELECT VERSION()").stdout.decode().replace("\r", "").strip()
        self.db.sql((DB_DIR / "schema.sql").read_text(encoding="utf-8"))

    def stop_database(self):
        if self.created:
            self.sh(["docker", "rm", "-f", self.container], check=False)
            left = self.sh(["docker", "ps", "-aq", "--filter", f"name={self.container}"]).stdout.strip()
            self.check("Z01", "B-028", "Disposable MySQL container removed", not left)
        if self.mysqld:
            pid = self.mysqld.pid  # only the PID this run started; an installed MySQL service is never addressed
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            try:
                self.mysqld.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
            time.sleep(1)
            listing = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True).stdout.decode(errors="replace")
            self.check("Z01", "B-028", "Throw-away local mysqld stopped (verified by PID, not by the Popen handle)", str(pid) not in listing)

    # ---- backend --------------------------------------------------------------------------------------
    def start_app(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        env = dict(os.environ, DB_HOST=self.db_host, DB_PORT=self.db_port, DB_NAME="b028", DB_USERNAME=self.db_user,
                   DB_PASSWORD=self.db_password, JWT_SECRET=self.jwt_secret,
                   ADMIN_INITIAL_PASSWORD=self.admin_password, TZ="Asia/Shanghai")
        self.base = f"http://127.0.0.1:{port}"
        self.app_log = []
        self.app = subprocess.Popen([self.args.java, "-jar", str(self.args.jar.resolve()), "--server.address=127.0.0.1",
                                     f"--server.port={port}", "--spring.jpa.hibernate.ddl-auto=validate",
                                     f"--shop.upload-dir={self.tmp_uploads}"], cwd=ROOT, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def consume():
            secrets_ = (self.db_password, self.admin_password, self.customer_password, self.jwt_secret)
            for line in self.app.stdout:
                text = line.decode("utf-8", errors="replace").rstrip()
                self.app_log.append("[credential-related log omitted]" if any(s in text for s in secrets_) else text)
        self.reader = threading.Thread(target=consume, daemon=True)
        self.reader.start()
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if self.app.poll() is not None:
                raise RuntimeError("Application exited: " + "\n".join(self.app_log[-14:]))
            try:
                with urlopen(self.base + "/api/categories/tree", timeout=2) as r:
                    if r.status == 200 and self.db.query("SELECT COUNT(*) FROM seller WHERE username='admin'") == "1":
                        return
            except (URLError, HTTPError, TimeoutError, ConnectionError):
                time.sleep(.5)
        raise TimeoutError("Backend did not become ready")

    def stop_app(self):
        if self.app and self.app.poll() is None:
            self.app.terminate()
            try:
                self.app.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.app.kill()
                self.app.wait(timeout=10)
        if hasattr(self, "reader"):
            self.reader.join(timeout=5)

    # ---- HTTP -----------------------------------------------------------------------------------------
    def call(self, method, path, body=None, token=None, key=None, timeout=45):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if key:
            headers["Idempotency-Key"] = key
        data = json.dumps(body).encode("utf-8") if body is not None else None
        try:
            with urlopen(Request(self.base + path, data=data, headers=headers, method=method), timeout=timeout) as r:
                status, raw = r.status, r.read()
        except HTTPError as error:
            status, raw = error.code, error.read()
        except Exception as error:  # timeout / connection reset: report as status 0
            return Resp(0, None, f"{type(error).__name__}: {error}")
        self.report["http_request_count"] += 1
        try:
            parsed = json.loads(raw)
        except ValueError:
            return Resp(status, None, raw[:120].decode("utf-8", errors="replace"))
        return Resp(status, parsed.get("code"), parsed.get("message"), parsed.get("data"))

    def race(self, calls):
        barrier = threading.Barrier(len(calls))

        def run(fn):
            barrier.wait()
            return fn()
        with ThreadPoolExecutor(len(calls)) as pool:
            return [f.result() for f in [pool.submit(run, fn) for fn in calls]]

    def publish(self, name, stock, price="10.00"):
        boundary = "b028-" + uuid.uuid4().hex
        fields = {"name": name, "price": price, "stock": stock, "category2Id": str(self.leaf),
                  "descriptionHtml": "<p>b028</p>"}
        body = b"".join(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                        for k, v in fields.items()) + f"--{boundary}--\r\n".encode()
        request = Request(self.base + "/api/admin/products", data=body, method="POST", headers={
            "Authorization": "Bearer " + self.seller, "Content-Type": "multipart/form-data; boundary=" + boundary})
        try:
            with urlopen(request, timeout=30) as r:
                payload = json.loads(r.read())
        except HTTPError as error:
            raise RuntimeError(f"publish failed: {error.code} {error.read()[:200]!r}")
        return str(payload["data"]["productId"])

    # ---- fixtures ---------------------------------------------------------------------------------------
    def product(self, stock, price="10.00"):
        self.n += 1
        pid = self.publish(f"b28p{self.run}{self.n}", str(stock), price)
        self.initial[pid] = int(stock)
        return pid

    def customer(self):
        self.n += 1
        name = f"b28c{self.run}{self.n}"
        r = self.call("POST", "/api/auth/register", {"username": name, "password": self.customer_password,
                                                      "phone": "13800000000"})
        if r.status != 201:
            self.setup_error(r, "register")
        r = self.call("POST", "/api/auth/login", {"username": name, "password": self.customer_password})
        if r.status != 200:
            self.setup_error(r, "login")
        return Customer(name, r.data["token"], int(self.db.query(f"SELECT id FROM customer WHERE username='{name}'")))

    def cart(self, c, items):
        ids = []
        for pid, qty in items:
            r = self.call("POST", "/api/me/cart/items", {"productId": pid}, c.token, key=str(uuid.uuid4()))
            if r.status != 200:
                self.setup_error(r, "cart add")
            ids.append(str(r.data["cartItemId"]))
            if str(qty) != "1":
                r2 = self.call("PATCH", f"/api/me/cart/items/{ids[-1]}", {"quantity": str(qty)}, c.token)
                if r2.status != 200:
                    self.setup_error(r2, "cart set quantity")
        return ids

    def confirm(self, c, ids):
        r = self.call("POST", "/api/me/checkout/confirmations", {"cartItemIds": ids}, c.token)
        if r.status != 200:
            self.setup_error(r, "confirm")
        return r.data["confirmationToken"]

    def place(self, c, token, key=None):
        return self.call("POST", "/api/me/orders", {"confirmationToken": token}, c.token, key=key or str(uuid.uuid4()))

    def order(self, c, items):
        r = self.place(c, self.confirm(c, self.cart(c, items)))
        if r.status != 201:
            self.setup_error(r, "place order")
        return str(r.data["orderId"])

    def cancel(self, c, oid, expected="PLACED", seller=False):
        path = f"/api/admin/orders/{oid}/cancel" if seller else f"/api/me/orders/{oid}/cancel"
        return self.call("POST", path, {"expectedStatus": expected}, self.seller if seller else c.token)

    def act(self, oid, action, expected):
        return self.call("POST", f"/api/admin/orders/{oid}/actions", {"action": action, "expectedStatus": expected}, self.seller)

    def advance_to(self, oid, target):
        for action, expected in (("CONFIRM", "PLACED"), ("PREPARE", "CONFIRMED"), ("SHIP", "PREPARED"), ("COMPLETE", "SHIPPED")):
            if self.q(f"SELECT status FROM shop_order WHERE id={oid}") == target:
                return
            r = self.act(oid, action, expected)
            if r.status != 200:
                self.setup_error(r, f"advance {action}")

    def q(self, statement):
        return self.db.query(statement)

    def stock(self, pid):
        return self.q(f"SELECT stock FROM product WHERE id={pid}")

    def snap(self, cid, pid):
        q = self.q
        return {"stock": q(f"SELECT stock FROM product WHERE id={pid}"),
                "state": q(f"SELECT CONCAT(status,':',IFNULL(offline_reason,'-')) FROM product WHERE id={pid}"),
                "orders": q(f"SELECT COUNT(*) FROM shop_order WHERE customer_id={cid}"),
                "items": q(f"SELECT COUNT(*) FROM order_item i JOIN shop_order o ON o.id=i.order_id WHERE o.customer_id={cid}"),
                "cart": q(f"SELECT IFNULL(GROUP_CONCAT(CONCAT(id,':',quantity) ORDER BY id),'') FROM cart_item WHERE customer_id={cid}"),
                "tombstones": q(f"SELECT COUNT(*) FROM cart_item_tombstone WHERE customer_id={cid}"),
                "receipts": q(f"SELECT COUNT(*) FROM operation_receipt WHERE customer_id={cid}"),
                "favorites": q(f"SELECT COUNT(*) FROM favorite WHERE customer_id={cid}")}

    def sold(self, pid):
        return Decimal(self.q("SELECT IFNULL(SUM(CAST(i.quantity_snapshot AS DECIMAL(65,0))),0) FROM order_item i "
                              f"JOIN shop_order o ON o.id=i.order_id WHERE i.product_id={pid} AND o.status<>'CANCELLED'"))

    def inject(self, table, event, condition):
        self.db.sql("DROP TRIGGER IF EXISTS b028_fail;\nDELIMITER //\n"
                    f"CREATE TRIGGER b028_fail BEFORE {event} ON {table} FOR EACH ROW BEGIN IF {condition} THEN "
                    "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='b028 injected failure'; END IF; END//\nDELIMITER ;")

    def clear(self):
        self.db.sql("DROP TRIGGER IF EXISTS b028_fail")

    # ---- scenarios -------------------------------------------------------------------------------------
    def s01_oversell(self):
        rounds, bad = [], []
        for rnd in range(3):
            pid = self.product(3)
            custs = [self.customer() for _ in range(6)]
            tokens = [self.confirm(c, self.cart(c, [(pid, 1)])) for c in custs]
            res = self.race([lambda c=c, t=t: self.place(c, t) for c, t in zip(custs, tokens)])
            wins = [c for c, r in zip(custs, res) if r.status == 201]
            losses = [(c, r) for c, r in zip(custs, res) if r.status != 201]
            reasons = {(r.status, r.code, (r.data or {}).get("errors", [{}])[0].get("reason")) for _, r in losses}
            lines = self.q(f"SELECT COUNT(*),IFNULL(SUM(CAST(quantity_snapshot AS DECIMAL(65,0))),0) FROM order_item WHERE product_id={pid}")
            tomb = sum(int(self.q(f"SELECT COUNT(*) FROM cart_item_tombstone WHERE customer_id={c.id}")) for c in wins)
            kept = sum(int(self.q(f"SELECT COUNT(*) FROM cart_item WHERE customer_id={c.id} AND quantity='1'")) for c, _ in losses)
            row = {"wins": len(wins), "loss_outcomes": sorted(map(str, reasons)), "order_items": lines,
                   "stock": self.stock(pid), "state": self.snap(0, pid)["state"], "winner_tombstones": tomb, "loser_rows_kept": kept}
            rounds.append(row)
            if not (len(wins) == 3 and lines == "3\t3" and row["stock"] == "0" and row["state"] == "OFFLINE:AUTO_ZERO"
                    and tomb == 3 and kept == 3 and all(s == 409 and c == 40910 and rs in ("INSUFFICIENT_STOCK", "OFFLINE")
                                                        for s, c, rs in reasons)):
                bad.append(row)
        self.check("S01", "B-011,B-012", "6 customers race for 3 units x3 rounds: exactly 3 orders, stock 0, auto offline, "
                   "winners' rows tombstoned, losers' rows kept, losers get 40910 per-item errors", not bad, rounds if bad else rounds[:1])

    def s02_multi_quantity(self):
        pid = self.product(10)
        custs = [self.customer() for _ in range(5)]
        tokens = [self.confirm(c, self.cart(c, [(pid, 3)])) for c in custs]
        res = self.race([lambda c=c, t=t: self.place(c, t) for c, t in zip(custs, tokens)])
        wins = sum(r.status == 201 for r in res)
        fails = [r for r in res if r.status != 201]
        avail = [((r.data or {}).get("errors") or [{}])[0].get("availableStock") for r in fails]
        self.check("S02", "B-011,B-012", "5 customers x qty 3 on stock 10: 3 orders, stock 1 and still ONLINE, 2 INSUFFICIENT_STOCK",
                   wins == 3 and self.stock(pid) == "1" and self.snap(0, pid)["state"] == "ONLINE:-" and
                   all(r.status == 409 and r.code == 40910 for r in fails) and self.sold(pid) == 9,
                   {"wins": wins, "stock": self.stock(pid), "fail_codes": [r.brief() for r in fails], "availableStock": avail})

    def s03_same_key(self):
        c, pid = self.customer(), self.product(5)
        token = self.confirm(c, self.cart(c, [(pid, 2)]))
        key = str(uuid.uuid4())
        res = self.race([lambda: self.place(c, token, key) for _ in range(6)])
        wins = [r for r in res if r.status == 201]
        dups = [r for r in res if r.status != 201]
        order_ids = {str((r.data or {}).get("orderId")) for r in dups if r.code == 40909}
        counts = self.q(f"SELECT (SELECT COUNT(*) FROM shop_order WHERE customer_id={c.id}),"
                        f"(SELECT COUNT(*) FROM operation_receipt WHERE customer_id={c.id} AND operation_type='CHECKOUT')")
        self.ctx["s03"] = {"c": c, "pid": pid, "token": token, "key": key,
                           "order": self.q(f"SELECT id FROM shop_order WHERE customer_id={c.id}")}
        self.check("S03", "B-012", "6 concurrent requests with the same token and key: exactly one order and receipt, stock deducted once, "
                   "the rest 409/40909 pointing at the original order",
                   len(wins) == 1 and counts == "1\t1" and self.stock(pid) == "3" and
                   all(r.status == 409 and r.code == 40909 for r in dups) and order_ids <= {str(wins[0].data["orderId"])},
                   {"results": [r.brief() for r in res], "counts": counts, "stock": self.stock(pid)})

    def s04_two_confirmations(self):
        c, pid = self.customer(), self.product(5)
        ids = self.cart(c, [(pid, 2)])
        t1, t2 = self.confirm(c, ids), self.confirm(c, ids)
        res = self.race([lambda: self.place(c, t1), lambda: self.place(c, t2)])
        wins = [r for r in res if r.status == 201]
        self.check("S04", "B-011,B-012", "Two confirmations of the same cart row placed concurrently with different keys: one order only, "
                   "stock deducted once, the other refused with a per-item/changed error",
                   len(wins) == 1 and self.stock(pid) == "3" and self.snap(c.id, pid)["orders"] == "1" and
                   all(r.status == 409 and r.code in (40910, 40913) for r in res if r.status != 201),
                   [r.brief() for r in res])

    def s05_cancel_race(self):
        outcomes = []
        for _ in range(3):
            c, pid = self.customer(), self.product(5)
            oid = self.order(c, [(pid, 2)])
            res = self.race([lambda: self.cancel(c, oid) for _ in range(4)] +
                            [lambda: self.cancel(c, oid, seller=True) for _ in range(4)])
            wins = [r for r in res if r.status == 200]
            by = self.q(f"SELECT IFNULL(cancelled_by,'-') FROM shop_order WHERE id={oid}")
            outcomes.append({"wins": len(wins), "stock": self.stock(pid), "status": self.q(f"SELECT status FROM shop_order WHERE id={oid}"),
                             "cancelled_by": by, "others": sorted({r.brief() for r in res if r.status != 200})})
        self.check("S05", "B-014", "8 racing cancels (4 customer + 4 seller) x3: exactly one succeeds, stock restored exactly once to 5, "
                   "cancel metadata present, the rest refused with 409",
                   all(o["wins"] == 1 and o["stock"] == "5" and o["status"] == "CANCELLED" and o["cancelled_by"] in ("CUSTOMER", "SELLER")
                       and all(x.startswith("409/") for x in o["others"]) for o in outcomes), outcomes)

    def s06_cancel_vs_ship(self):
        outcomes, bad = {"SHIPPED": 0, "CANCELLED": 0}, []
        for _ in range(8):
            c, pid = self.customer(), self.product(5)
            oid = self.order(c, [(pid, 1)])
            self.advance_to(oid, "PREPARED")
            cancel, ship = self.race([lambda: self.cancel(c, oid, "PREPARED"), lambda: self.act(oid, "SHIP", "PREPARED")])
            status, stock = self.q(f"SELECT status FROM shop_order WHERE id={oid}"), self.stock(pid)
            outcomes[status] = outcomes.get(status, 0) + 1
            fine = ((status == "SHIPPED" and ship.status == 200 and cancel.status == 409 and stock == "4") or
                    (status == "CANCELLED" and cancel.status == 200 and ship.status == 409 and stock == "5"))
            if not fine:
                bad.append({"status": status, "cancel": cancel.brief(), "ship": ship.brief(), "stock": stock})
        self.check("S06", "B-013,B-014", "Customer cancel vs seller SHIP on a PREPARED order x8: exactly one wins; stock restored iff cancelled",
                   not bad, {"outcomes": outcomes, "violations": bad})

    def s07_cancel_vs_complete(self):
        c, pid = self.customer(), self.product(5)
        oid = self.order(c, [(pid, 1)])
        self.advance_to(oid, "SHIPPED")
        denied = self.cancel(c, oid, "SHIPPED")
        outcomes, bad = {}, []
        denied_ok = denied.status == 409 and self.stock(pid) == "4"
        for _ in range(6):
            c2, p2 = self.customer(), self.product(5)
            o2 = self.order(c2, [(p2, 1)])
            self.advance_to(o2, "SHIPPED")
            cancel, complete = self.race([lambda: self.cancel(c2, o2, "SHIPPED", seller=True), lambda: self.act(o2, "COMPLETE", "SHIPPED")])
            status, stock = self.q(f"SELECT status FROM shop_order WHERE id={o2}"), self.stock(p2)
            outcomes[status] = outcomes.get(status, 0) + 1
            if not ((status == "COMPLETED" and complete.status == 200 and cancel.status == 409 and stock == "4") or
                    (status == "CANCELLED" and cancel.status == 200 and complete.status == 409 and stock == "5")):
                bad.append({"status": status, "cancel": cancel.brief(), "complete": complete.brief(), "stock": stock})
        self.check("S07", "B-013,B-014", "SHIPPED: customer cancel refused with no stock change; seller cancel vs COMPLETE x6: exactly one wins, "
                   "stock restored iff cancelled", denied_ok and not bad,
                   {"customer_cancel": denied.brief() + " " + str(denied.message), "outcomes": outcomes, "violations": bad})

    def s08_stock_additive(self):
        c = self.customer()
        pid = self.product(5)
        self.adjusted.add(pid)
        oid = self.order(c, [(pid, 3)])
        self.call("PATCH", f"/api/admin/products/{pid}", {"stock": "7"}, self.seller)
        self.cancel(c, oid)
        a = self.stock(pid)  # manual 7 then restore 3 -> 10
        oid = self.order(c, [(pid, 3)])
        self.cancel(c, oid)
        self.call("PATCH", f"/api/admin/products/{pid}", {"stock": "4"}, self.seller)
        b = self.stock(pid)  # cancel first, manual 4 afterwards -> 4
        p2 = self.product(2)
        self.adjusted.add(p2)
        o2 = self.order(c, [(p2, 1)])
        self.call("POST", f"/api/admin/products/{p2}/offline", None, self.seller)
        self.cancel(c, o2)
        manual = self.snap(0, p2)
        p3 = self.product(1)
        self.adjusted.add(p3)
        o3 = self.order(c, [(p3, 1)])
        zero = self.snap(0, p3)["state"]
        self.cancel(c, o3)
        auto = self.snap(0, p3)
        self.check("S08", "B-006,B-014", "Manual stock edits and cancel restores add up (7+3=10; cancel then set 4 = 4); MANUAL offline stays offline "
                   "after restore; AUTO_ZERO offline recovers to ONLINE with reason cleared",
                   a == "10" and b == "4" and manual["stock"] == "2" and manual["state"] == "OFFLINE:MANUAL" and
                   zero == "OFFLINE:AUTO_ZERO" and auto["stock"] == "1" and auto["state"] == "ONLINE:-",
                   {"manual_then_restore": a, "restore_then_manual": b, "manual_offline": manual, "auto_zero_before": zero, "after_restore": auto})

    def s09_cart_add(self):
        c, pid = self.customer(), self.product(50)
        key = str(uuid.uuid4())
        same = self.race([lambda: self.call("POST", "/api/me/cart/items", {"productId": pid}, c.token, key=key) for _ in range(6)])
        row = self.q(f"SELECT CONCAT(COUNT(*),':',IFNULL(MAX(quantity),'-')) FROM cart_item WHERE customer_id={c.id} AND product_id={pid}")
        ids = {str((r.data or {}).get("cartItemId")) for r in same if r.status == 200}
        c2, p2 = self.customer(), self.product(50)
        many = self.race([lambda: self.call("POST", "/api/me/cart/items", {"productId": p2}, c2.token, key=str(uuid.uuid4())) for _ in range(5)])
        okc = sum(r.status == 200 for r in many)
        rows2 = self.q(f"SELECT CONCAT(COUNT(*),':',IFNULL(MAX(quantity),'-')) FROM cart_item WHERE customer_id={c2.id} AND product_id={p2}")
        self.check("S09", "B-008,B-012", "Same key x6: one row with quantity 1 and one id; five different keys: one row whose quantity equals the "
                   "number of successes (no lost update), no 5xx",
                   row == "1:1" and len(ids) == 1 and all(r.status == 200 for r in same) and rows2 == f"1:{okc}" and okc == 5,
                   {"same_key": [r.brief() for r in same], "row": row, "distinct_keys": [r.brief() for r in many], "row2": rows2})

    def s10_move(self):
        c = self.customer()
        pids = [self.product(5) for _ in range(3)]
        ids = self.cart(c, [(p, 2) for p in pids])
        key = str(uuid.uuid4())
        res = self.race([lambda: self.call("POST", "/api/me/cart/move-to-favorites", {"cartItemIds": ids}, c.token, key=key) for _ in range(5)])
        s = self.snap(c.id, pids[0])
        move_receipts = self.q(f"SELECT COUNT(*) FROM operation_receipt WHERE customer_id={c.id} AND operation_type='MOVE_TO_FAVORITES'")
        wins = [r for r in res if r.status == 200]
        self.check("S10a", "B-025,B-026", "Move 3 rows with the same key x5: one success (3 rows), others 409/40915; 3 favorites, cart empty, "
                   "3 tombstones, one receipt, stock untouched",
                   len(wins) == 1 and wins[0].data["movedLineCount"] == 3 and s["favorites"] == "3" and s["cart"] == "" and
                   s["tombstones"] == "3" and move_receipts == "1" and all(r.status == 409 and r.code == 40915 for r in res if r.status != 200)
                   and all(self.stock(p) == "5" for p in pids),
                   {"responses": [r.brief() for r in res], "moved": (wins[0].data if wins else None), "db": s,
                    "stocks": [self.stock(p) for p in pids]})
        c2 = self.customer()
        a, b = self.product(5), self.product(5)
        ia, ib = self.cart(c2, [(a, 1), (b, 1)])
        mv, rm = self.race([lambda: self.call("POST", "/api/me/cart/move-to-favorites", {"cartItemIds": [ia, ib]}, c2.token, key=str(uuid.uuid4())),
                            lambda: self.call("DELETE", f"/api/me/cart/items/{ia}", None, c2.token)])
        favs = set(self.q(f"SELECT product_id FROM favorite WHERE customer_id={c2.id}").split())
        self.check("S10b", "B-025,B-026", "Move vs deleting one selected row: no 5xx, cart ends without both rows, the surviving product is always "
                   "favourited, a favourite exists for the deleted one only if the move won",
                   mv.status == 200 and rm.status == 200 and self.snap(c2.id, a)["cart"] == "" and b in favs and
                   (a not in favs or mv.data["movedLineCount"] == 2), {"move": mv.brief(), "delete": rm.brief(), "favourites": sorted(favs),
                                                                         "moved": (mv.data or {}).get("movedLineCount")})
        c3, p3 = self.customer(), self.product(5)
        self.call("PUT", f"/api/me/favorites/{p3}", None, c3.token)
        i3 = self.cart(c3, [(p3, 1)])
        mv3, un = self.race([lambda: self.call("POST", "/api/me/cart/move-to-favorites", {"cartItemIds": i3}, c3.token, key=str(uuid.uuid4())),
                             lambda: self.call("DELETE", f"/api/me/favorites/{p3}", None, c3.token)])
        self.check("S10c", "B-026", "Move vs cancelling the same favourite: both succeed, the cart row is gone either way, no half state",
                   mv3.status == 200 and un.status == 200 and self.snap(c3.id, p3)["cart"] == "" and
                   self.q(f"SELECT COUNT(*) FROM favorite WHERE customer_id={c3.id}") in ("0", "1"), {"move": mv3.brief(), "unfavourite": un.brief()})

    def s11_lock_order(self):
        abundant, scarce = [], []
        for stock, sink in ((40, abundant), (4, scarce)):
            a, b = self.product(stock), self.product(stock)
            custs = [self.customer() for _ in range(8)]
            tokens = []
            for i, c in enumerate(custs):
                order = [(a, 1), (b, 1)] if i % 2 == 0 else [(b, 1), (a, 1)]
                tokens.append(self.confirm(c, self.cart(c, order)))
            res = self.race([lambda c=c, t=t: self.place(c, t) for c, t in zip(custs, tokens)])
            sink.append({"wins": sum(r.status == 201 for r in res), "server_errors": [r.brief() for r in res if r.status >= 500 or r.status == 0],
                         "stock": (self.stock(a), self.stock(b)), "non_201": sorted({r.brief() for r in res if r.status != 201})})
        ok_a = abundant[0]["wins"] == 8 and not abundant[0]["server_errors"] and abundant[0]["stock"] == ("32", "32")
        ok_s = scarce[0]["wins"] == 4 and not scarce[0]["server_errors"] and scarce[0]["stock"] == ("0", "0")
        self.check("S11", "B-011,B-012", "8 customers buying products A,B in opposite cart orders: no deadlock/5xx; abundant stock -> 8 orders; "
                   "scarce stock (4) -> exactly 4 orders and both stocks 0", ok_a and ok_s, {"abundant": abundant[0], "scarce": scarce[0]})

    def s12_fault_injection(self):
        def prepare(qty=2, stock=5):
            c, pid = self.customer(), self.product(stock)
            ids = self.cart(c, [(pid, qty)])
            return c, pid, ids, self.confirm(c, ids)
        points = (("order_item", "INSERT", "NEW.product_id = {pid}"), ("product", "UPDATE", "OLD.id = {pid} AND NEW.stock <> OLD.stock"),
                  ("cart_item_tombstone", "INSERT", "NEW.customer_id = {cid}"), ("operation_receipt", "INSERT", "NEW.customer_id = {cid}"))
        bad, seen = [], []
        for table, event, cond in points:
            c, pid, ids, token = prepare()
            before, key = self.snap(c.id, pid), str(uuid.uuid4())
            self.inject(table, event, cond.format(pid=pid, cid=c.id))
            failed = self.place(c, token, key)
            after = self.snap(c.id, pid)
            self.clear()
            retry = self.place(c, token, key)
            seen.append({"point": f"{table}.{event}", "failed": failed.brief(), "unchanged": after == before, "retry": retry.brief(),
                         "stock_after_retry": self.stock(pid)})
            if not (failed.status >= 500 and after == before and retry.status == 201 and self.stock(pid) == "3"):
                bad.append(seen[-1] | {"before": before, "after": after})
        self.check("S12a", "B-011,B-012", "Failure injected at 4 write points of checkout (order item, stock deduction, cart tombstone, receipt): "
                   "request fails, nothing persisted (no order/deduction/cart change/receipt), and the same key+token then succeeds", not bad, bad or seen)
        bad, seen = [], []
        for table, event, cond in (("product", "UPDATE", "OLD.id = {pid} AND NEW.stock <> OLD.stock"),
                                   ("shop_order", "UPDATE", "NEW.id = {oid} AND NEW.status = 'CANCELLED'")):
            c, pid = self.customer(), self.product(5)
            oid = self.order(c, [(pid, 2)])
            before, status0 = self.snap(c.id, pid), self.q(f"SELECT status FROM shop_order WHERE id={oid}")
            self.inject(table, event, cond.format(pid=pid, oid=oid))
            failed = self.cancel(c, oid)
            after, status1 = self.snap(c.id, pid), self.q(f"SELECT status FROM shop_order WHERE id={oid}")
            self.clear()
            retry = self.cancel(c, oid)
            seen.append({"point": f"{table}.{event}", "failed": failed.brief(), "unchanged": after == before and status0 == status1,
                         "retry": retry.brief(), "stock_after_retry": self.stock(pid)})
            if not (failed.status >= 500 and after == before and status1 == "PLACED" and retry.status == 200 and self.stock(pid) == "5"):
                bad.append(seen[-1])
        self.check("S12b", "B-014", "Failure injected while cancelling (stock restore, order update): order stays PLACED, stock unchanged, "
                   "a later cancel restores exactly once", not bad, bad or seen)
        bad, seen = [], []
        for table, event in (("favorite", "INSERT"), ("cart_item_tombstone", "INSERT"), ("operation_receipt", "INSERT")):
            c = self.customer()
            pids = [self.product(5) for _ in range(2)]
            ids = self.cart(c, [(p, 1) for p in pids])
            before, key = self.snap(c.id, pids[0]), str(uuid.uuid4())
            self.inject(table, event, f"NEW.customer_id = {c.id}")
            failed = self.call("POST", "/api/me/cart/move-to-favorites", {"cartItemIds": ids}, c.token, key=key)
            after = self.snap(c.id, pids[0])
            self.clear()
            retry = self.call("POST", "/api/me/cart/move-to-favorites", {"cartItemIds": ids}, c.token, key=key)
            seen.append({"point": f"{table}.{event}", "failed": failed.brief(), "message": failed.message, "unchanged": after == before,
                         "retry": retry.brief()})
            if not (failed.status == 500 and failed.code == 50001 and after == before and retry.status == 200):
                bad.append(seen[-1])
        self.check("S12c", "B-025,B-026", "Failure injected at favourite insert, cart tombstone and receipt of move-to-favorites: 500/50001, "
                   "nothing persisted, the same key then succeeds", not bad, bad or seen)

    def s13_huge_numbers(self):
        c, pid = self.customer(), self.product(HUGE_STOCK, "12.50")
        ids = self.cart(c, [(pid, HUGE_QTY)])
        order = self.place(c, self.confirm(c, ids))
        want_total = (Decimal("12.50") * Decimal(HUGE_QTY)).quantize(Decimal("0.01"))
        remaining = Decimal(HUGE_STOCK) - Decimal(HUGE_QTY)
        stock_db = Decimal(self.stock(pid))
        total_db = self.q(f"SELECT total_amount FROM shop_order WHERE id={(order.data or {}).get('orderId')}")
        okay = order.status == 201 and stock_db == remaining and Decimal(total_db) == want_total and (order.data or {}).get("totalAmount") == format(want_total, "f")
        cancel = self.cancel(c, str(order.data["orderId"])) if order.status == 201 else Resp(0)
        self.check("S13", "B-003,B-011,B-014", "Stock 1.2e29 and quantity 9.9e19: exact total, exact deduction, exact one-time restore (no int/long/JS-safe cap)",
                   okay and cancel.status == 200 and Decimal(self.stock(pid)) == Decimal(HUGE_STOCK),
                   {"place": order.brief(), "total_api": (order.data or {}).get("totalAmount"), "total_expected": format(want_total, "f"),
                    "stock_after": str(stock_db), "restored": self.stock(pid)})

    def s14_authorization(self):
        a, b = self.customer(), self.customer()
        pid = self.product(5)
        ids = self.cart(a, [(pid, 2)])
        oid = self.order(self.customer(), [(self.product(5), 1)])
        own = self.order(a, [(self.product(5), 1)])
        before = (self.snap(a.id, pid), self.q(f"SELECT status FROM shop_order WHERE id={own}"))
        cases = {"anonymous place": self.call("POST", "/api/me/orders", {"confirmationToken": str(uuid.uuid4())}, None, key=str(uuid.uuid4())),
                 "seller on customer cart": self.call("GET", "/api/me/cart", None, self.seller),
                 "customer on admin orders": self.call("GET", "/api/admin/orders?page=1&size=10", None, a.token),
                 "other customer reads order": self.call("GET", f"/api/me/orders/{own}", None, b.token),
                 "other customer cancels order": self.cancel(b, own),
                 "other customer edits cart row": self.call("PATCH", f"/api/me/cart/items/{ids[0]}", {"quantity": "9"}, b.token),
                 "other customer deletes cart row": self.call("DELETE", f"/api/me/cart/items/{ids[0]}", None, b.token),
                 "other customer checks out the row": self.call("POST", "/api/me/checkout/confirmations", {"cartItemIds": ids}, b.token),
                 "other customer moves the row": self.call("POST", "/api/me/cart/move-to-favorites", {"cartItemIds": ids}, b.token, key=str(uuid.uuid4()))}
        after = (self.snap(a.id, pid), self.q(f"SELECT status FROM shop_order WHERE id={own}"))
        denied = {k: v.brief() for k, v in cases.items()}
        self.check("S14", "B-005", "Anonymous, wrong-role and other-customer calls are all refused (401/403) and leave the owner's cart, orders, "
                   "stock and receipts byte-identical", all(v.status in (401, 403) for v in cases.values()) and before == after, denied)
        self.ctx["foreign_order"] = oid

    def s15_legacy(self):
        c, pid = self.customer(), self.product(5)
        r = self.call("POST", f"/api/products/{pid}/intents", {}, c.token)
        count = self.q(f"SELECT COUNT(*) FROM purchase_intent WHERE product_id={pid}")
        self.check("S15", "B-016", "Submitting a legacy purchase intent for a fixed-price product is refused with 409/40917 and writes no intent",
                   r.status == 409 and r.code == 40917 and count == "0", {"response": r.brief(), "message": r.message, "intents": count})

    def s16_restart(self):
        s = self.ctx["s03"]
        order_before = self.q(f"SELECT COUNT(*) FROM shop_order") + ":" + self.q("SELECT COUNT(*) FROM operation_receipt")
        self.stop_app()
        self.start_app()
        self.check("S16a", "B-028", "Backend restarts on the same database with ddl-auto=validate", True)
        login = self.call("POST", "/api/auth/login", {"username": s["c"].name, "password": self.customer_password})
        token = login.data["token"] if login.status == 200 else ""
        s["c"].token = token
        self.seller = self.call("POST", "/api/admin/auth/login", {"username": "admin", "password": self.admin_password}).data["token"]
        replay = self.place(s["c"], s["token"], s["key"])
        detail = self.call("GET", f"/api/me/orders/{s['order']}", None, token)
        self.check("S16b", "B-012", "After restart the receipt still answers the original key with 409/40909 and the original order, "
                   "stock stays deducted once, the order is readable",
                   replay.status == 409 and replay.code == 40909 and str((replay.data or {}).get("orderId")) == s["order"] and
                   self.stock(s["pid"]) == "3" and detail.status == 200 and
                   self.q("SELECT COUNT(*) FROM shop_order") + ":" + self.q("SELECT COUNT(*) FROM operation_receipt") == order_before,
                   {"replay": replay.brief(), "detail": detail.brief()})

    def s17_ledger(self):
        wrong, offline_bad = [], []
        for pid, initial in self.initial.items():
            stock = Decimal(self.stock(pid))
            if stock < 0:
                wrong.append((pid, "negative", str(stock)))
            if pid in self.adjusted:
                continue
            expected = Decimal(initial) - self.sold(pid)
            if stock != expected:
                wrong.append((pid, f"stock {stock} != initial {initial} - sold {self.sold(pid)}"))
            state = self.snap(0, pid)["state"]
            if (stock == 0) != state.startswith("OFFLINE"):
                offline_bad.append((pid, str(stock), state))
        both = self.q("SELECT COUNT(*) FROM cart_item c JOIN cart_item_tombstone t ON t.cart_item_id = c.id")
        self.check("S17", "B-028", "Final ledger over every product the run created: stock >= 0 and initial - live order quantities = stock "
                   "(manually edited products excluded); OFFLINE exactly when stock 0; no cart row shares an id with a tombstone",
                   not wrong and not offline_bad and both == "0",
                   {"products": len(self.initial), "ledger_errors": wrong[:5], "offline_errors": offline_bad[:5], "rows_also_tombstoned": both})

    # ---- driver -----------------------------------------------------------------------------------------
    def bootstrap(self):
        self.tmp_uploads = Path(tempfile.mkdtemp(prefix="oxstore-b028-up-"))
        self.start_app()
        self.check("D01", "B-028", "Packaged backend starts on the V7/V8-era schema with Hibernate ddl-auto=validate", True)
        self.seller = self.call("POST", "/api/admin/auth/login", {"username": "admin", "password": self.admin_password}).data["token"]
        tree = self.call("GET", "/api/categories/tree").data
        self.leaf = tree[0]["children"][0]["id"]

    def finish(self):
        try:
            self.stop_app()
        finally:
            try:
                self.stop_database()
            finally:  # only directories this run created
                for name in ("tmp", "tmp_uploads"):
                    if hasattr(self, name):
                        shutil.rmtree(getattr(self, name), ignore_errors=True)
        self.report["app_log_tail"] = self.app_log[-12:] if any("ERROR" in line for line in self.app_log[-200:]) else []

    def save(self):
        passed = sum(c["status"] == "PASS" for c in self.report["checks"])
        self.report["summary"] = {"pass": passed, "fail": len(self.report["checks"]) - passed,
                                  "scenario_errors": len(self.report["scenario_errors"])}
        self.args.output.parent.mkdir(parents=True, exist_ok=True)
        self.args.output.write_text(json.dumps(self.report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print("summary", self.report["summary"], "->", self.args.output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", choices=("docker", "local"), default="docker")
    parser.add_argument("--image", default="mysql:8.0.46")
    parser.add_argument("--mysql-bin", default=r"C:\Program Files\MySQL\MySQL Server 9.5\bin")
    parser.add_argument("--java", default="java")
    parser.add_argument("--jar", type=Path, default=ROOT / "backend/target/shop-0.1.0.jar")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/test/evidence/r5-challenge-b-db/b028-results.json")
    args = parser.parse_args()
    run = B028(args)
    fatal = None
    try:
        run.start_database()
        run.bootstrap()
        for name in ("s01_oversell", "s02_multi_quantity", "s03_same_key", "s04_two_confirmations", "s05_cancel_race",
                     "s06_cancel_vs_ship", "s07_cancel_vs_complete", "s08_stock_additive", "s09_cart_add", "s10_move",
                     "s11_lock_order", "s12_fault_injection", "s13_huge_numbers", "s14_authorization", "s15_legacy",
                     "s16_restart", "s17_ledger"):
            try:
                getattr(run, name)()
            except Exception as exc:  # one broken scenario must not hide the others
                run.report["scenario_errors"].append({"scenario": name, "error": str(exc)[:600]})
                print(f"ERROR {name}: {exc}", flush=True)
                traceback.print_exc()
    except Exception as exc:
        fatal = exc
        run.report["fatal"] = str(exc)
        traceback.print_exc()
    finally:
        try:
            run.finish()
        except Exception as exc:
            fatal = fatal or exc
            run.report["cleanup_error"] = str(exc)
        run.save()
    failed = fatal or run.report["summary"]["fail"] or run.report["summary"]["scenario_errors"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
