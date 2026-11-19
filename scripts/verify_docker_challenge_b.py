"""B-038 integration and B-039 deployment verification of the challenge-B Docker release with real containers.

Two scenarios, each in its own randomly named Compose project with a random port and fresh volumes, driven only
through the public Nginx port (no mocked API, no direct database writes except reading state for assertions):

  clean            exported bundle -> new empty volumes -> health, SPA, schema, challenge-B API flow, concurrency,
                   restart and container re-creation persistence
  existing-volume  a database volume created and filled by the PREVIOUS release (iteration2 + auction images) ->
                   start the new images WITHOUT upgrading (must fail: Compose does not change tables) -> run the
                   explicit upgrade tool -> start the new images -> old data, auction and new flow all work ->
                   restart and re-creation persistence

Credentials are generated per run and never written to the result files. Only the projects created here are
started and removed (down -v on their own random names). This is R5's deployment verification, not R2's
independent acceptance (B-036/B-040).
"""
from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import uuid
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
NEW_VERSION = os.environ.get("OXSTORE_VERSION", "0.1.0-iteration3-challenge-b.1")
OLD_VERSION = "0.1.0-iteration2-auction-docker.1"
OLD_SCHEMA_COMMIT = "0cef9ec"  # last develop commit before V7: the V6-era schema.sql the previous release shipped
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=")


class Resp:
    def __init__(self, status, code=None, message=None, data=None):
        self.status, self.code, self.message, self.data = status, code, message, data

    def brief(self):
        return f"{self.status}/{self.code}"


class Stack:
    def __init__(self, bundle: Path, output: Path, label: str):
        self.bundle, self.output = bundle.resolve(), output.resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.project = f"oxstore-b039-{label}-" + uuid.uuid4().hex[:8]
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.admin_password = "Ox!" + secrets.token_hex(12)
        self.customer_password = "Cu!" + secrets.token_hex(8)
        self.env = dict(os.environ, COMPOSE_PROJECT_NAME=self.project, APP_PORT=str(self.port), APP_BIND_ADDRESS="127.0.0.1",
                        DB_PASSWORD=secrets.token_hex(24), JWT_SECRET=secrets.token_hex(32),
                        ADMIN_INITIAL_PASSWORD=self.admin_password, OXSTORE_VERSION=NEW_VERSION)
        self.base = f"http://127.0.0.1:{self.port}"
        self.report = {"label": label, "run_at": datetime.now().astimezone().isoformat(), "project": self.project,
                       "checks": [], "requests": 0}
        self.seller = ""
        self.n = 0
        self.secrets = (self.admin_password, self.customer_password, self.env["DB_PASSWORD"], self.env["JWT_SECRET"])

    # ---- compose / database -----------------------------------------------------------------------
    def compose(self, *args, check=True, timeout=300, compose_file=None, version=None, payload=None):
        env = dict(self.env, OXSTORE_VERSION=version or self.env["OXSTORE_VERSION"])
        result = subprocess.run(["docker", "compose", "-f", str(compose_file or self.bundle / "compose.yml"), "-p", self.project, *args],
                                cwd=(compose_file or self.bundle / "compose.yml").parent, env=env, input=payload,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        text = result.stdout.decode("utf-8", errors="replace")
        for secret in self.secrets:
            text = text.replace(secret, "[redacted]")
        with (self.output / "compose-operations.log").open("a", encoding="utf-8") as log:
            log.write(f"[{self.report['label']}] docker compose {' '.join(args)}\n{text}\n")
        if check and result.returncode:
            raise RuntimeError(text[-1800:])
        return result.returncode, text

    def up(self, **kw):
        return self.compose("up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "240", **kw)

    def sql(self, statement):
        _, text = self.compose("exec", "-T", "mysql", "sh", "-c",
                               'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot -N --batch --default-character-set=utf8mb4 shop',
                               payload=("SET NAMES utf8mb4;\n" + statement).encode("utf-8"))
        return text.replace("\r", "").strip()

    def services(self):
        _, text = self.compose("ps", "--format", "json")
        return [json.loads(line) for line in text.splitlines() if line.startswith("{")]

    def check(self, code, description, condition, detail=None):
        entry = {"id": code, "description": description, "status": "PASS" if condition else "FAIL"}
        if detail is not None:
            entry["detail"] = detail
        self.report["checks"].append(entry)
        print(f"{entry['status']} [{self.report['label']}] {code}: {description}" + ("" if condition or detail is None else f"  -> {detail}"), flush=True)
        if not condition:
            raise AssertionError(f"{code}: {description}")

    # ---- HTTP ---------------------------------------------------------------------------------------
    def call(self, method, path, body=None, token=None, key=None, files=None, timeout=40):
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        if key:
            headers["Idempotency-Key"] = key
        if files is None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8") if body is not None else None
        else:
            boundary = "b039-" + uuid.uuid4().hex
            parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in (body or {}).items()]
            for name, content in files:
                parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="images"; filename="{name}"\r\n'
                              "Content-Type: image/png\r\n\r\n").encode() + content + b"\r\n")
            data = b"".join(parts) + f"--{boundary}--\r\n".encode()
            headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
        try:
            with urlopen(Request(self.base + path, data=data, headers=headers, method=method), timeout=timeout) as r:
                status, raw = r.status, r.read()
        except HTTPError as error:
            status, raw = error.code, error.read()
        except Exception as error:
            return Resp(0, None, f"{type(error).__name__}")
        self.report["requests"] += 1
        try:
            parsed = json.loads(raw)
        except ValueError:
            return Resp(status, None, None, raw)
        return Resp(status, parsed.get("code"), parsed.get("message"), parsed.get("data"))

    def must(self, response, status, what):
        if response.status != status:
            raise AssertionError(f"{what}: expected HTTP {status}, got {response.brief()} {response.message}")
        return response.data

    def race(self, calls):
        barrier = threading.Barrier(len(calls))

        def run(fn):
            barrier.wait()
            return fn()
        with ThreadPoolExecutor(len(calls)) as pool:
            return [f.result() for f in [pool.submit(run, fn) for fn in calls]]

    # ---- fixtures -----------------------------------------------------------------------------------
    def login_seller(self):
        self.seller = self.must(self.call("POST", "/api/admin/auth/login", {"username": "admin", "password": self.admin_password}), 200, "seller login")["token"]

    def leaf(self):
        return self.must(self.call("GET", "/api/categories/tree"), 200, "categories")[0]["children"][0]["id"]

    def register(self, name):
        self.must(self.call("POST", "/api/auth/register", {"username": name, "password": self.customer_password, "phone": "13800000000"}), 201, "register")
        return self.login(name)

    def login(self, name):
        return self.must(self.call("POST", "/api/auth/login", {"username": name, "password": self.customer_password}), 200, "login")["token"]

    def customer(self):
        self.n += 1
        name = f"b39c{self.tag}{self.n}"
        return name, self.register(name)

    def publish(self, name, stock, price="12.50", with_image=True):
        fields = {"name": name, "price": price, "stock": str(stock), "category2Id": str(self.leaf_id), "descriptionHtml": "<p>b039</p>"}
        r = self.call("POST", "/api/admin/products", fields, self.seller, files=[("p.png", PNG)] if with_image else [])
        return str(self.must(r, 201, "publish")["productId"])

    def add_cart(self, token, pid, qty=1):
        row = self.must(self.call("POST", "/api/me/cart/items", {"productId": pid}, token, key=str(uuid.uuid4())), 200, "cart add")
        if qty != 1:
            self.must(self.call("PATCH", f"/api/me/cart/items/{row['cartItemId']}", {"quantity": str(qty)}, token), 200, "cart set")
        return str(row["cartItemId"])

    def confirm(self, token, ids):
        return self.must(self.call("POST", "/api/me/checkout/confirmations", {"cartItemIds": ids}, token), 200, "confirm")["confirmationToken"]

    def place(self, token, conf, key=None):
        return self.call("POST", "/api/me/orders", {"confirmationToken": conf}, token, key=key or str(uuid.uuid4()))

    def order(self, token, pid, qty):
        r = self.place(token, self.confirm(token, [self.add_cart(token, pid, qty)]))
        return self.must(r, 201, "place order")

    def stock(self, pid):
        return self.sql(f"SELECT stock FROM product WHERE id={pid}")

    # ---- the challenge-B flow through Nginx ---------------------------------------------------------
    def challenge_b_flow(self, prefix):
        c = self.check
        self.tag = uuid.uuid4().hex[:5]
        self.leaf_id = self.leaf()
        a_name, a = self.customer()
        p1, p2 = self.publish(f"{prefix}商品一", 5), self.publish(f"{prefix}商品二", 2)
        img = re.search(r"/api/images/[^\"\\]+", json.dumps(self.call("GET", f"/api/products/{p1}").data or ""))
        with urlopen(self.base + img.group(0), timeout=20) as r:
            self.image = r.read()
        c(f"{prefix}01", "Fixed-price product published with an image served through Nginx", self.image == PNG)

        self.must(self.call("PUT", f"/api/me/favorites/{p1}", None, a), 200, "favorite")
        state = self.call("GET", f"/api/me/favorites/{p1}", None, a).data
        page = self.call("GET", "/api/me/favorites?page=1", None, a).data
        c(f"{prefix}02", "Favourite stored, readable and listed (F01/F03/F04)", state.get("favorited") is True and any(str(i.get("productId")) == p1 for i in page["items"]))

        order = self.order(a, p1, 3)
        c(f"{prefix}03", "Cart -> confirmation -> order: 201, six-state PLACED, exact total, stock deducted in the database",
          order["status"] == "PLACED" and order["totalAmount"] == "37.50" and self.stock(p1) == "2" and order["allowedActions"] == ["CANCEL"], {"status": order["status"], "total": order["totalAmount"]})
        oid = str(order["orderId"])
        listed = self.call("GET", "/api/me/orders?page=1&size=10", None, a).data
        detail = self.call("GET", f"/api/me/orders/{oid}", None, a)
        admin_list = self.call("GET", "/api/admin/orders?page=1&size=10", None, self.seller)
        admin_detail = self.call("GET", f"/api/admin/orders/{oid}", None, self.seller)
        c(f"{prefix}04", "Customer and seller read the same order (O01/O02/A01/A02): identical except allowedActions (customer [CANCEL], seller [CONFIRM, CANCEL])",
          any(str(o["orderId"]) == oid for o in listed["items"]) and detail.status == 200 and admin_detail.status == 200
          and {k: v for k, v in detail.data.items() if k != "allowedActions"} == {k: v for k, v in admin_detail.data.items() if k != "allowedActions"}
          and detail.data["allowedActions"] == ["CANCEL"] and admin_detail.data["allowedActions"] == ["CONFIRM", "CANCEL"] and admin_list.status == 200,
          {"detail": detail.brief(), "admin_detail": admin_detail.brief(), "admin_list": admin_list.brief(),
           "differs": sorted(k for k in set(detail.data or {}) | set(admin_detail.data or {}) if (detail.data or {}).get(k) != (admin_detail.data or {}).get(k))})
        c(f"{prefix}05", "A cart row whose quantity was ordered is gone from the cart", self.call("GET", "/api/me/cart", None, a).data["items"] == [])

        step = lambda action, expected: self.call("POST", f"/api/admin/orders/{oid}/actions", {"action": action, "expectedStatus": expected}, self.seller)
        c(f"{prefix}06", "Seller advances CONFIRM -> PREPARE; skipping or repeating a step is refused (409)",
          step("CONFIRM", "PLACED").status == 200 and step("PREPARE", "CONFIRMED").status == 200 and step("PREPARE", "CONFIRMED").status == 409
          and step("COMPLETE", "PREPARED").status == 409)
        cancelled = self.call("POST", f"/api/me/orders/{oid}/cancel", {"expectedStatus": "PREPARED", "reason": "不要了"}, a)
        again = self.call("POST", f"/api/me/orders/{oid}/cancel", {"expectedStatus": "PREPARED"}, a)
        c(f"{prefix}07", "Customer cancel before shipping: CANCELLED with initiator/time, stock restored once, repeat refused",
          cancelled.status == 200 and cancelled.data["status"] == "CANCELLED" and cancelled.data["cancelledBy"] == "CUSTOMER"
          and cancelled.data["cancelledAt"] and self.stock(p1) == "5" and again.status == 409 and again.code == 40911, {"repeat": again.brief()})

        oid2 = str(self.order(a, p1, 1)["orderId"])
        for action, expected in (("CONFIRM", "PLACED"), ("PREPARE", "CONFIRMED"), ("SHIP", "PREPARED")):
            self.call("POST", f"/api/admin/orders/{oid2}/actions", {"action": action, "expectedStatus": expected}, self.seller)
        refused = self.call("POST", f"/api/me/orders/{oid2}/cancel", {"expectedStatus": "SHIPPED"}, a)
        seller_cancel = self.call("POST", f"/api/admin/orders/{oid2}/cancel", {"expectedStatus": "SHIPPED"}, self.seller)
        c(f"{prefix}08", "After shipping the customer cannot cancel but the seller can; stock restored",
          refused.status == 409 and seller_cancel.status == 200 and self.stock(p1) == "5")

        key = str(uuid.uuid4())
        conf = self.confirm(a, [self.add_cart(a, p2, 1)])
        first = self.place(a, conf, key)
        replay = self.place(a, conf, key)
        c(f"{prefix}09", "Same confirmation and Idempotency-Key: second request is 409/40909 pointing at the first order",
          first.status == 201 and replay.status == 409 and replay.code == 40909 and str(replay.data["orderId"]) == str(first.data["orderId"]))

        p3 = self.publish(f"{prefix}抢购", 2, with_image=False)
        custs = [self.customer() for _ in range(5)]
        confs = [self.confirm(t, [self.add_cart(t, p3, 1)]) for _, t in custs]
        results = self.race([lambda t=t, cf=cf: self.place(t, cf) for (_, t), cf in zip(custs, confs)])
        c(f"{prefix}10", "5 customers race for 2 units through Nginx: exactly 2 orders, stock 0, auto offline, losers get 409/40910",
          sum(r.status == 201 for r in results) == 2 and self.stock(p3) == "0" and all(r.status == 409 and r.code == 40910 for r in results if r.status != 201)
          and self.sql(f"SELECT CONCAT(status,':',offline_reason) FROM product WHERE id={p3}") == "OFFLINE:AUTO_ZERO", [r.brief() for r in results])

        p4 = self.publish(f"{prefix}转收藏", 3, with_image=False)
        row = self.add_cart(a, p4, 2)
        moved = self.call("POST", "/api/me/cart/move-to-favorites", {"cartItemIds": [row]}, a, key=str(uuid.uuid4()))
        fav4 = self.call("GET", f"/api/me/favorites/{p4}", None, a).data
        c(f"{prefix}11", "Move-to-favourites moves the whole row: favourite exists, cart row gone, no order, stock untouched",
          moved.status == 200 and moved.data["movedLineCount"] == 1 and fav4["favorited"] is True and
          not any(str(i["cartItemId"]) == row for i in self.call("GET", "/api/me/cart", None, a).data["items"]) and self.stock(p4) == "3")

        c(f"{prefix}12", "Anonymous and wrong-role calls are refused (401/403)",
          all(r.status in (401, 403) for r in (self.call("GET", "/api/me/cart"), self.call("GET", "/api/me/cart", None, self.seller),
                                              self.call("GET", "/api/admin/orders?page=1&size=10", None, a),
                                              self.call("POST", "/api/me/orders", {"confirmationToken": str(uuid.uuid4())}, None, key=str(uuid.uuid4())))))
        legacy = self.call("POST", f"/api/products/{p1}/intents", {}, a)
        c(f"{prefix}13", "Legacy purchase intent on a fixed-price product is closed: 409/40917; archive endpoints answer 200",
          legacy.status == 409 and legacy.code == 40917 and self.call("GET", "/api/me/legacy-intents?page=1&size=10", None, a).status == 200
          and self.call("GET", "/api/admin/legacy-intents?page=1&size=10", None, self.seller).status == 200)

        ends = (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=2)).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")
        auction = self.must(self.call("POST", "/api/admin/products", {"name": f"{prefix}拍卖", "category2Id": str(self.leaf_id), "sellingMode": "AUCTION",
                                                                        "startPrice": "10.00", "minIncrement": "2.00", "endsAt": ends}, self.seller, files=[]), 201, "auction")["productId"]
        bid = self.call("POST", f"/api/products/{auction}/auction/bids", {"amount": "10.00"}, a)
        snap = self.call("GET", f"/api/products/{auction}/auction").data
        cart_refused = self.call("POST", "/api/me/cart/items", {"productId": str(auction)}, a, key=str(uuid.uuid4()))
        c(f"{prefix}14", "Auction regression: bid accepted, public snapshot LIVE, auction cannot enter the cart (409)",
          bid.status == 201 and snap["auctionStatus"] == "LIVE" and snap["bidCount"] == 1 and cart_refused.status == 409, {"cart": cart_refused.brief()})
        self.ids = {"p1": p1, "auction": str(auction), "customer": (a_name, a), "order": oid}

    def snapshot(self):
        name, _ = self.ids["customer"]
        token = self.login(name)
        return {"orders": self.sql("SELECT COUNT(*) FROM shop_order") + ":" + self.sql("SELECT status,COUNT(*) FROM shop_order GROUP BY status ORDER BY 1").replace("\n", ","),
                "stock": self.sql("SELECT id,stock FROM product ORDER BY id").replace("\n", ","),
                "receipts": self.sql("SELECT COUNT(*) FROM operation_receipt"),
                "favorites": self.sql("SELECT COUNT(*) FROM favorite"),
                "auction": json.dumps({k: v for k, v in self.call("GET", f"/api/products/{self.ids['auction']}/auction").data.items() if k != "serverTime"}, sort_keys=True),
                "history": self.call("GET", "/api/me/orders?page=1&size=10", None, token).data["total"]}

    def persistence(self, prefix):
        before = self.snapshot()
        self.compose("restart", "backend")
        self.up()
        self.login_seller()
        after_restart = self.snapshot()
        self.compose("down")
        self.up()
        self.login_seller()
        after_recreate = self.snapshot()
        with urlopen(self.base + re.search(r"/api/images/[^\"\\]+", json.dumps(self.call("GET", f"/api/products/{self.ids['p1']}").data)).group(0), timeout=20) as r:
            image = r.read()
        self.check(f"{prefix}", "Orders, stock, receipts, favourites, auction and uploaded image identical after backend restart and after container re-creation",
                   before == after_restart == after_recreate and image == PNG, None if before == after_recreate else {"before": before, "after": after_recreate})

    def common_health(self, prefix):
        ps = self.services()
        self.check(f"{prefix}01", "mysql, backend and frontend are healthy with no build and no registry pull", len(ps) == 3 and all(s.get("Health") == "healthy" for s in ps),
                   [(s["Service"], s.get("Health")) for s in ps])
        self.check(f"{prefix}02", "Only the frontend port is published to the host",
                   all(not any(p.get("PublishedPort", 0) for p in s.get("Publishers") or []) for s in ps if s["Service"] != "frontend"))
        for path in ("/", "/admin/login", "/cart"):
            with urlopen(self.base + path, timeout=20) as r:
                self.check(f"{prefix}03{path.replace('/', '_')}", "SPA route served by Nginx", r.status == 200 and '<div id="root"></div>' in r.read().decode())

    def schema_facts(self, prefix):
        tables = self.sql("SHOW TABLES").split()
        triggers = self.sql("SELECT trigger_name FROM information_schema.triggers WHERE trigger_schema='shop' ORDER BY 1").split()
        stock = self.sql("SELECT data_type FROM information_schema.columns WHERE table_schema='shop' AND table_name='product' AND column_name='stock'")
        self.check(prefix, "Database has the 21 tables, 3 triggers and the text stock column of the challenge-B schema",
                   len(tables) == 21 and len(triggers) == 3 and stock == "longtext", {"tables": len(tables), "triggers": len(triggers), "stock": stock})
        self.report["mysql_version"] = self.sql("SELECT VERSION()")

    def teardown(self):
        self.compose("down", "-v", "--remove-orphans", check=False)
        left = subprocess.run(["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={self.project}"], capture_output=True).stdout.strip()
        vols = subprocess.run(["docker", "volume", "ls", "-q", "--filter", f"label=com.docker.compose.project={self.project}"], capture_output=True).stdout.strip()
        self.report["cleanup"] = {"containers_left": bool(left), "volumes_left": bool(vols)}
        print(f"cleanup [{self.report['label']}]: containers_left={bool(left)} volumes_left={bool(vols)}", flush=True)

    def finish(self, name, ok):
        self.report["result"] = "PASS" if ok else "FAIL"
        (self.output / name).write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8")


def run_clean(bundle, output):
    s = Stack(bundle, output, "clean")
    ok = False
    try:
        s.compose("config", "-q")
        s.up()
        s.common_health("C")
        s.schema_facts("C04")
        s.login_seller()
        s.challenge_b_flow("F")
        s.persistence("C99")
        ok = True
    except Exception as error:
        s.report["error"] = f"{type(error).__name__}: {str(error)[:600]}"
        print("ERROR", s.report["error"], flush=True)
    finally:
        s.teardown()
        s.finish("b039-clean-results.json", ok)
    return ok


def run_existing_volume(bundle, output):
    s = Stack(bundle, output, "volume")
    ok = False
    staging = Path(tempfile.mkdtemp(prefix="oxstore-b039-old-"))
    backups = Path(tempfile.mkdtemp(prefix="oxstore-b039-backups-"))
    try:
        for version in (OLD_VERSION, NEW_VERSION):
            for image in ("backend", "frontend"):
                subprocess.run(["docker", "image", "inspect", f"oxstore/{image}:{version}"], capture_output=True, check=True)
        old_dir = staging / "database"
        old_dir.mkdir()
        shutil.copy2(bundle / "compose.yml", staging / "compose.yml")
        schema = subprocess.run(["git", "-C", str(ROOT), "show", f"{OLD_SCHEMA_COMMIT}:backend/src/main/resources/db/schema.sql"], capture_output=True, check=True).stdout
        (old_dir / "schema.sql").write_bytes(schema)
        old_compose = staging / "compose.yml"

        # 1. the previous release creates the volume and fills it through its own API
        s.up(compose_file=old_compose, version=OLD_VERSION)
        s.check("V01", "Previous release (iteration2 + auction) starts healthy on a new volume with its V6-era schema",
                all(x.get("Health") == "healthy" for x in s.services()) and len(s.sql("SHOW TABLES").split()) == 12)
        s.login_seller()
        s.tag = uuid.uuid4().hex[:5]
        s.leaf_id = s.leaf()
        buyers = [s.customer() for _ in range(4)]
        fixed_a, fixed_b, sold = s.publish("旧版在售交易中", 3), s.publish("旧版排队中", 2), s.publish("旧版已成交", 1)
        ia = s.must(s.call("POST", f"/api/products/{fixed_a}/intents", None, buyers[0][1]), 200, "intent a")["intentId"]
        s.must(s.call("POST", f"/api/admin/intents/{ia}/start", None, s.seller), 200, "start a")
        for _, token in (buyers[1], buyers[2]):
            s.must(s.call("POST", f"/api/products/{fixed_b}/intents", None, token), 200, "intent b")
        isold = s.must(s.call("POST", f"/api/products/{sold}/intents", None, buyers[3][1]), 200, "intent sold")["intentId"]
        s.must(s.call("POST", f"/api/admin/intents/{isold}/start", None, s.seller), 200, "start sold")
        s.must(s.call("POST", f"/api/admin/intents/{isold}/success", None, s.seller), 200, "success sold")
        ends = (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=2)).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")
        auction = str(s.must(s.call("POST", "/api/admin/products", {"name": "旧版拍卖", "category2Id": str(s.leaf_id), "sellingMode": "AUCTION", "startPrice": "10.00",
                                                                     "minIncrement": "2.00", "endsAt": ends}, s.seller, files=[]), 201, "auction")["productId"])
        s.must(s.call("POST", f"/api/products/{auction}/auction/bids", {"amount": "10.00"}, buyers[1][1]), 201, "bid")
        s.ids = {"p1": fixed_a, "auction": auction, "customer": buyers[0], "order": None}
        pre = {"intents": s.sql("SELECT status,COUNT(*) FROM purchase_intent GROUP BY status ORDER BY 1").replace("\n", ","),
               "products": s.sql("SELECT id,name,status,IFNULL(freeze_source,'-'),stock FROM product ORDER BY id").replace("\n", " | "),
               "history": s.sql("SELECT COUNT(*) FROM order_history"), "bids": s.sql("SELECT COUNT(*) FROM auction_bid"),
               "auction": json.dumps({k: v for k, v in s.call("GET", f"/api/products/{auction}/auction").data.items() if k != "serverTime"}, sort_keys=True)}
        s.report["old_state"] = {k: pre[k] for k in ("intents", "history", "bids")}
        s.check("V02", "Old data exists: 1 trade-frozen product, 2 queued intents, 1 SUCCESS history, a LIVE auction with a bid",
                "IN_TRANSACTION	1" in pre["intents"] and "QUEUING	2" in pre["intents"] and "SUCCESS	1" in pre["intents"], s.report["old_state"])
        s.compose("down", compose_file=old_compose, version=OLD_VERSION)

        # 2. new images on the old volume WITHOUT upgrading: Compose must not (and does not) change tables
        code, text = s.compose("up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "90", check=False, timeout=200)
        _, logs = s.compose("logs", "--no-color", "--tail", "400", "backend", check=False)
        reason = next((line.split("|", 1)[-1].strip()[:200] for line in logs.splitlines() if re.search(r"Unknown column|doesn.t exist|Schema.validation|missing table|wrong column", line)), None)
        tables_now = len(s.sql("SHOW TABLES").split())
        s.check("V03", "New images on the un-upgraded volume do NOT come up healthy and leave the 12-table database untouched (Compose restart does not upgrade tables); the backend defaults to ddl-auto=none, so it fails on its first query instead of validating at start-up",
                code != 0 and tables_now == 12, {"compose_exit": code, "tables": tables_now, "backend_reason": reason})
        s.compose("stop", "backend", "frontend", check=False)

        # 3. explicit, backup-first upgrade of the volume's database
        container = subprocess.run(["docker", "compose", "-f", str(bundle / "compose.yml"), "-p", s.project, "ps", "-q", "mysql"], env=s.env,
                                   capture_output=True, cwd=bundle).stdout.decode().strip()
        name = subprocess.run(["docker", "inspect", "--format", "{{.Name}}", container], capture_output=True).stdout.decode().strip().lstrip("/")
        tool = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/migrate_challenge_b.py"), "--container", name, "--database", "shop",
                               "--backup-dir", str(backups)], capture_output=True, cwd=ROOT)
        try:
            result = json.loads(tool.stdout.decode("utf-8"))
        except ValueError:
            result = {}
        s.report["upgrade_tool"] = {k: result.get(k) for k in ("phase_before", "phase_after", "applied", "v8_counts", "backup_bytes")}
        if tool.returncode:
            s.report["upgrade_tool"]["stderr_tail"] = tool.stderr.decode("utf-8", errors="replace")[-400:]
        s.check("V04", "The explicit upgrade tool classifies the volume 'auction', applies V7+V8 after a non-empty backup, ends 'challenge_b'",
                tool.returncode == 0 and result.get("phase_before") == "auction" and result.get("applied") == ["V7", "V8"]
                and result.get("backup_bytes", 0) > 0 and result.get("phase_after") == "challenge_b", s.report["upgrade_tool"])
        s.check("V05", "V8 closed exactly the live fixed-price intents (1 in-trade + 2 queued) and the trade-frozen product returned to sale",
                (result.get("v8_counts") or {}).get("closed_intents") == 3 and (result.get("v8_counts") or {}).get("unfrozen_products") == 1, result.get("v8_counts"))

        # 4. new images on the upgraded volume
        s.up()
        s.common_health("V1")
        s.schema_facts("V06")
        s.login_seller()
        a_name, a_token = buyers[0]
        a_token = s.login(a_name)
        legacy = s.call("GET", "/api/me/legacy-intents?page=1&size=10", None, a_token)
        legacy_items = (legacy.data or {}).get("items", [])
        history = s.call("GET", "/api/me/order-history", None, s.login(buyers[3][0])).data
        post = {"intents": s.sql("SELECT status,COUNT(*) FROM purchase_intent GROUP BY status ORDER BY 1").replace("\n", ","),
                "history": s.sql("SELECT COUNT(*) FROM order_history"), "bids": s.sql("SELECT COUNT(*) FROM auction_bid"),
                "auction": json.dumps({k: v for k, v in s.call("GET", f"/api/products/{auction}/auction").data.items() if k != "serverTime"}, sort_keys=True)}
        s.check("V07", "Old data survives: intent statuses unchanged (no CANCELLED/FAILED invented), SUCCESS history readable, auction and bid unchanged",
                post["intents"] == pre["intents"] and post["history"] == pre["history"] and post["bids"] == pre["bids"] and post["auction"] == pre["auction"]
                and history["total"] == 1 and history["items"][0]["status"] == "SUCCESS", {"pre": pre["intents"], "post": post["intents"]})
        s.check("V08", "The closed intent is shown read-only in the buyer's archive without becoming a new order",
                legacy.status == 200 and len(legacy_items) >= 1 and s.sql("SELECT COUNT(*) FROM shop_order") == "0", {"archive_rows": len(legacy_items)})
        s.check("V09", "Closed intents cannot be driven any more (start/success on a closed fixed-price intent is refused with 409/40917)",
                s.call("POST", f"/api/admin/intents/{ia}/success", None, s.seller).code == 40917)
        s.check("V10", "The previously trade-frozen product is on sale again with its stock unchanged and uploaded images still served",
                s.sql(f"SELECT CONCAT(status,':',stock,':',IFNULL(freeze_source,'-')) FROM product WHERE id={fixed_a}") == "ONLINE:3:-")
        s.challenge_b_flow("VF")
        s.ids["auction"] = auction
        s.persistence("V99")
        ok = True
    except Exception as error:
        s.report["error"] = f"{type(error).__name__}: {str(error)[:600]}"
        print("ERROR", s.report["error"], flush=True)
    finally:
        s.teardown()
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(backups, ignore_errors=True)
        s.finish("b039-existing-volume-results.json", ok)
    return ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True, help="exported release folder containing compose.yml and database/")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scenario", choices=("clean", "existing-volume", "both"), default="both")
    args = parser.parse_args()
    results = []
    if args.scenario in ("clean", "both"):
        results.append(run_clean(args.bundle, args.output))
    if args.scenario in ("existing-volume", "both"):
        results.append(run_existing_volume(args.bundle, args.output))
    raise SystemExit(0 if all(results) else 1)
