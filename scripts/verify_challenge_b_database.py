"""R5 challenge-B database acceptance for B-001～B-004 on a disposable MySQL container.

Python standard library + Docker only (no backend JAR). Only the container created by this
run is mutated and removed; the root password is generated per run and never written to the
JSON. Covers: fresh schema, V7/V8 upgrade of an iteration-2 + auction database, repeat and
resume behaviour, refusal paths that must change nothing, constraint/trigger rejections, and
fresh-vs-upgraded schema equality. It is a DB-layer self-check by R5, not the independent R2
business acceptance and not the concurrent-transaction verification of B-028.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import traceback
import uuid

from migrate_iteration2 import DockerMySQL, ROOT, MIGRATIONS
from verify_iteration2_database import DB_DIR, FIXTURE
from verify_auction_database import LEGACY_SEED

V = {n: (MIGRATIONS / f).read_text(encoding="utf-8") for n, f in (
    ("V4", "V4__iteration2_customer_inventory_catalog.sql"), ("V5", "V5__iteration2_database_contract.sql"),
    ("V6", "V6__auction_mode.sql"), ("V7", "V7__challenge_b_order_cart_favorite.sql"),
    ("V8", "V8__close_legacy_fixed_price_intents.sql"))}
NEW_TABLES = {"shop_order", "order_item", "favorite", "favorite_mutation", "cart_item", "cart_item_tombstone",
              "checkout_confirmation", "checkout_confirmation_item", "operation_receipt"}
INDEXES = {("shop_order", "uk_shop_order_no"), ("shop_order", "idx_shop_order_customer_time"),
           ("shop_order", "idx_shop_order_time"), ("order_item", "uk_order_item_product"),
           ("favorite", "uk_favorite_customer_product"), ("favorite", "idx_favorite_customer_time"),
           ("cart_item", "uk_cart_customer_product"), ("cart_item", "idx_cart_customer"),
           ("cart_item_tombstone", "uk_cart_tombstone_item"), ("checkout_confirmation", "uk_confirmation_token"),
           ("operation_receipt", "uk_receipt_request"), ("purchase_intent", "idx_intent_legacy_customer"),
           ("purchase_intent", "idx_intent_legacy_product")}
TRIGGERS = {"trg_product_selling_mode_immutable", "trg_shop_order_guard", "trg_order_item_immutable"}
HUGE = "123456789012345678901234567890"
HUGE_MONEY = HUGE + ".00"

# Iteration-2 + auction data (after V6), built around the cases V8 must treat differently.
CATEGORY = "(SELECT MIN(id) FROM category WHERE parent_id IS NOT NULL)"
UPGRADE_SEED = f"""
INSERT INTO product(id,name,description,price,stock,category2_id,selling_mode,status,freeze_source,published_at) VALUES
 (10,'在售一口价','',10.00,5,{CATEGORY},'FIXED_PRICE','ONLINE',NULL,'2026-11-01 10:00:00'),
 (11,'交易冻结一口价','',11.00,3,{CATEGORY},'FIXED_PRICE','FROZEN','TRADE','2026-11-01 10:00:00'),
 (12,'排队中一口价','',12.00,2,{CATEGORY},'FIXED_PRICE','ONLINE',NULL,'2026-11-01 10:00:00'),
 (13,'手动冻结一口价','',13.00,4,{CATEGORY},'FIXED_PRICE','FROZEN','MANUAL','2026-11-01 10:00:00'),
 (14,'零库存下架','',14.00,0,{CATEGORY},'FIXED_PRICE','OFFLINE',NULL,'2026-11-01 10:00:00'),
 (15,'手动下架有库存','',15.00,6,{CATEGORY},'FIXED_PRICE','OFFLINE',NULL,'2026-11-01 10:00:00'),
 (16,'拍卖成交履约中','',16.00,1,{CATEGORY},'AUCTION','FROZEN','TRADE','2026-11-01 10:00:00'),
 (17,'有历史的一口价','',17.00,1,{CATEGORY},'FIXED_PRICE','ONLINE',NULL,'2026-11-01 10:00:00');
INSERT INTO customer(id,username,password_hash,phone,registered_at) VALUES (1,'buyer1','h','13800000000','2026-11-01 09:00:00');
INSERT INTO purchase_intent(id,product_id,customer_id,product_name_snapshot,buyer_name,buyer_phone,status,submitted_at,queue_seq) VALUES
 (21,11,1,'交易冻结一口价','buyer1','13800000000','IN_TRANSACTION','2026-11-02 10:00:00',1),
 (22,12,1,'排队中一口价','buyer1','13800000000','QUEUING','2026-11-02 10:01:00',1),
 (23,12,NULL,'排队中一口价','guest','13800000001','QUEUING','2026-11-02 10:02:00',2),
 (24,16,1,'拍卖成交履约中','buyer1','13800000000','IN_TRANSACTION','2026-11-02 10:03:00',1),
 (25,17,1,'有历史的一口价','buyer1','13800000000','SUCCESS','2026-11-02 10:04:00',1),
 (26,17,1,'有历史的一口价','buyer1','13800000000','FAILED','2026-11-02 10:05:00',2);
INSERT INTO trade_attempt(id,intent_id,started_at,finished_at,result,fail_action) VALUES
 (21,21,'2026-11-02 10:10:00',NULL,NULL,NULL),
 (24,24,'2026-11-02 10:11:00',NULL,NULL,NULL),
 (25,25,'2026-11-02 10:12:00','2026-11-02 10:13:00','SUCCESS',NULL),
 (26,26,'2026-11-02 10:14:00','2026-11-02 10:15:00','FAILED','DISCARD');
INSERT INTO auction_session(id,product_id,start_price,min_increment,status,starts_at,ends_at,winner_intent_id)
 VALUES (1,16,16.00,1.00,'LIVE','2026-11-01 10:00:00','2026-11-30 10:00:00',NULL);
"""


class ChallengeBVerification:
    def __init__(self, args):
        self.args = args
        self.container = "oxstore-b-db-" + uuid.uuid4().hex[:10]
        self.password = secrets.token_urlsafe(18)
        self.report = {"started_at": datetime.now().isoformat(timespec="seconds"), "checks": []}

    def command(self, args, payload=None, check=True, timeout=180, env=None):
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

    def start(self):
        env = os.environ.copy()
        env["MYSQL_ROOT_PASSWORD"] = self.password
        self.command(["docker", "run", "-d", "--pull=never", "--name", self.container,
                      "--label", "oxstore.r5.challenge-b=1", "-e", "MYSQL_ROOT_PASSWORD", self.args.image,
                      "--character-set-server=utf8mb4", "--collation-server=utf8mb4_0900_ai_ci"], env=env)
        self.created = True
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            r = self.command(["docker", "exec", self.container, "sh", "-c",
                              'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -h127.0.0.1 --protocol=TCP -uroot -N -e "SELECT 1"'],
                             check=False)
            if r.returncode == 0 and r.stdout.strip() == b"1":
                break
            time.sleep(1)
        else:
            raise TimeoutError("Disposable MySQL did not become ready")
        names = ("fresh", "upgraded", "norepeat", "resume", "needsv7", "abnormal", "needsv6")
        self.admin_sql(";".join(f"CREATE DATABASE {n} CHARACTER SET utf8mb4" for n in names) + ";")
        self.db = {n: DockerMySQL(self.container, n) for n in names}
        self.report["mysql_version"] = self.db["fresh"].query("SELECT VERSION()")
        self.report["image_id"] = self.command(["docker", "inspect", "--format", "{{.Image}}", self.container]
                                               ).stdout.decode().strip()

    def stop(self):
        if getattr(self, "created", False):
            self.command(["docker", "rm", "-f", self.container], check=False)
            left = self.command(["docker", "ps", "-aq", "--filter", f"name={self.container}"]).stdout.strip()
            self.verify("Z01", "B-028", "Disposable container removed", not left)

    @staticmethod
    def errno(result):
        match = re.search(rb"ERROR (\d+)", result.stderr)
        return int(match.group(1)) if match else None

    def rejected(self, db, code, tasks, description, statement, errno):
        result = db.sql(statement, check=False)
        self.verify(code, tasks, f"{description} (MySQL error {errno})",
                    result.returncode != 0 and self.errno(result) == errno)

    def accepted(self, db, code, tasks, description, statement):
        self.verify(code, tasks, description, db.sql(statement, check=False).returncode == 0)

    def fingerprint(self, db):
        tables = sorted(db.tables())
        body = "\n".join(t + "\n" + db.query(f"SELECT * FROM `{t}` ORDER BY 1") for t in tables)
        return hashlib.sha256(body.encode()).hexdigest()

    def signature(self, db):
        return [db.query(q) for q in (
            "SELECT table_name,column_name,column_type,is_nullable,IFNULL(column_default,'-') FROM information_schema.columns "
            "WHERE table_schema=DATABASE() ORDER BY table_name,column_name",
            "SELECT table_name,constraint_name,constraint_type FROM information_schema.table_constraints "
            "WHERE constraint_schema=DATABASE() ORDER BY table_name,constraint_name",
            "SELECT constraint_name,check_clause FROM information_schema.check_constraints "
            "WHERE constraint_schema=DATABASE() ORDER BY constraint_name",
            "SELECT table_name,index_name,non_unique,GROUP_CONCAT(column_name ORDER BY seq_in_index) "
            "FROM information_schema.statistics WHERE table_schema=DATABASE() "
            "GROUP BY table_name,index_name,non_unique ORDER BY table_name,index_name",
            "SELECT trigger_name,event_manipulation,event_object_table FROM information_schema.triggers "
            "WHERE trigger_schema=DATABASE() ORDER BY trigger_name")]

    def build_v6(self, db, seed=True):
        db.sql(FIXTURE.read_text(encoding="utf-8-sig") + LEGACY_SEED)
        for name in ("V4", "V5", "V6"):
            db.sql(V[name])
        if seed:
            db.sql(UPGRADE_SEED)

    # ---- fresh schema -------------------------------------------------------------------------
    def schema_checks(self):
        db = self.db["fresh"]
        db.sql((DB_DIR / "schema.sql").read_text(encoding="utf-8"))
        self.verify("S01", "B-001,B-002,B-003", "Fresh schema creates the nine challenge-B tables", NEW_TABLES <= db.tables())
        self.verify("S02", "B-003", "product.stock is LONGTEXT and product.offline_reason exists",
                    db.query("SELECT CONCAT(data_type,':',is_nullable) FROM information_schema.columns WHERE table_schema=DATABASE() "
                             "AND table_name='product' AND column_name='stock'") == "longtext:NO" and
                    db.query("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
                             "AND table_name='product' AND column_name='offline_reason'") == "1")
        present = {tuple(r.split("\t")) for r in db.query(
            "SELECT DISTINCT table_name,index_name FROM information_schema.statistics WHERE table_schema=DATABASE()").splitlines()}
        self.verify("S03", "B-001,B-002", "Order, favorite, cart, receipt and legacy-archive indexes exist", INDEXES <= present)
        self.verify("S04", "B-001", "Selling-mode, order-guard and order-item immutability triggers are installed",
                    set(db.query("SELECT trigger_name FROM information_schema.triggers WHERE trigger_schema=DATABASE()").splitlines()) == TRIGGERS)
        self.verify("S05", "B-001,B-003", "Money and quantity columns are LONGTEXT; unit prices stay DECIMAL(10,2)",
                    set(db.query("SELECT CONCAT(table_name,'.',column_name) FROM information_schema.columns WHERE table_schema=DATABASE() "
                                 "AND data_type='longtext' AND (column_name LIKE '%amount%' OR column_name LIKE '%quantity%' "
                                 "OR column_name='quantity' OR column_name='stock')").splitlines()) ==
                    {"shop_order.total_amount", "order_item.quantity_snapshot", "order_item.line_amount_snapshot",
                     "cart_item.quantity", "checkout_confirmation.total_amount", "checkout_confirmation_item.quantity",
                     "product.stock"} and
                    db.query("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() "
                             "AND table_name IN ('order_item','checkout_confirmation_item') "
                             "AND column_name IN ('unit_price_snapshot','unit_price') AND column_type='decimal(10,2)'") == "2")

    # ---- constraint behaviour (fresh) -----------------------------------------------------------
    def constraint_checks(self):
        db = self.db["fresh"]
        db.sql(f"""INSERT INTO customer(id,username,password_hash,phone,registered_at) VALUES
 (1,'c1','h','13800000000','2026-11-01 09:00:00'),(2,'c2','h','13800000000','2026-11-01 09:00:00');
INSERT INTO category(id,name,parent_id) VALUES (1,'一级',NULL),(2,'二级',1);
INSERT INTO product(id,name,description,price,stock,category2_id,selling_mode,status,published_at) VALUES
 (1,'p1','',10.00,'5',2,'FIXED_PRICE','ONLINE','2026-11-01 10:00:00'),
 (2,'p2','',20.00,'7',2,'FIXED_PRICE','ONLINE','2026-11-01 10:00:00'),
 (3,'auc','',30.00,'1',2,'AUCTION','ONLINE','2026-11-01 10:00:00');""")
        P, O = "B-003", "B-001"
        for code, stock in (("C01", "-1"), ("C02", "1.5"), ("C03", "007"), ("C04", ""), ("C05", "1e3"), ("C06", " 5"),
                            ("C07", "5\\n")):
            self.rejected(db, code, P, f"product.stock {stock!r} is not a canonical non-negative integer",
                          f"UPDATE product SET stock='{stock}' WHERE id=1", 3819)
        self.accepted(db, "C08", P, "Stock beyond 64-bit and JS safe integers is accepted", f"UPDATE product SET stock='{HUGE}' WHERE id=1")
        self.verify("C09", P, "The huge stock round-trips as the exact string", db.query("SELECT stock FROM product WHERE id=1") == HUGE)
        self.accepted(db, "C10", P, "Stock 0 is accepted", "UPDATE product SET stock='0' WHERE id=2")
        self.rejected(db, "C11", P, "An auction product cannot hold stock 2", "UPDATE product SET stock='2' WHERE id=3", 3819)
        self.rejected(db, "C12", P, "offline_reason outside AUTO_ZERO/MANUAL is rejected",
                      "UPDATE product SET offline_reason='OTHER' WHERE id=1", 3819)

        no = "'11111111-1111-1111-1111-111111111111'"
        self.accepted(db, "O01", O, "A PLACED order with an unbounded two-decimal total is accepted",
                      f"INSERT INTO shop_order(id,order_no,customer_id,status,total_amount,created_at) VALUES (1,{no},1,'PLACED','{HUGE_MONEY}','2026-11-02 10:00:00')")
        self.rejected(db, "O02", O, "A duplicate order number is rejected",
                      f"INSERT INTO shop_order(order_no,customer_id,status,total_amount,created_at) VALUES ({no},1,'PLACED','1.00','2026-11-02 10:00:00')", 1062)
        for code, field, value in (("O03", "status", "FAILED"), ("O04", "total_amount", "1.5"), ("O05", "total_amount", "01.00"),
                                   ("O06", "total_amount", "-1.00"), ("O07", "total_amount", "1.00\\n"),
                                   ("O08", "order_no", "not-a-uuid")):
            cols = {"status": "'PLACED'", "total_amount": "'1.00'", "order_no": "'22222222-2222-2222-2222-222222222222'"}
            cols[field] = f"'{value}'"
            self.rejected(db, code, O, f"shop_order.{field} {value!r} is rejected",
                          f"INSERT INTO shop_order(order_no,customer_id,status,total_amount,created_at) VALUES ({cols['order_no']},1,{cols['status']},{cols['total_amount']},'2026-11-02 10:00:00')", 3819)
        self.rejected(db, "O09", O, "CANCELLED without initiator/time is rejected",
                      "INSERT INTO shop_order(order_no,customer_id,status,total_amount,created_at) VALUES ('33333333-3333-3333-3333-333333333333',1,'CANCELLED','1.00','2026-11-02 10:00:00')", 3819)
        self.rejected(db, "O10", O, "A non-cancelled order with cancel metadata is rejected",
                      "INSERT INTO shop_order(order_no,customer_id,status,total_amount,created_at,cancelled_by,cancelled_at) VALUES ('44444444-4444-4444-4444-444444444444',1,'PLACED','1.00','2026-11-02 10:00:00','SELLER','2026-11-02 11:00:00')", 3819)
        self.rejected(db, "O11", O, "A cancel time before creation is rejected",
                      "INSERT INTO shop_order(order_no,customer_id,status,total_amount,created_at,cancelled_by,cancelled_at) VALUES ('55555555-5555-5555-5555-555555555555',1,'CANCELLED','1.00','2026-11-02 10:00:00','SELLER','2026-11-02 09:00:00')", 3819)
        self.rejected(db, "O12", O, "An order for an unknown customer is rejected",
                      "INSERT INTO shop_order(order_no,customer_id,status,total_amount,created_at) VALUES ('66666666-6666-6666-6666-666666666666',99,'PLACED','1.00','2026-11-02 10:00:00')", 1452)
        self.accepted(db, "I01", O, "An item with a huge quantity and line amount is accepted",
                      f"INSERT INTO order_item(id,order_id,product_id,product_name_snapshot,unit_price_snapshot,quantity_snapshot,line_amount_snapshot) VALUES (1,1,1,'p1',10.00,'{HUGE}','{HUGE}0.00')")
        self.rejected(db, "I02", O, "A second line for the same order and product is rejected",
                      "INSERT INTO order_item(order_id,product_id,product_name_snapshot,unit_price_snapshot,quantity_snapshot,line_amount_snapshot) VALUES (1,1,'p1',10.00,'1','10.00')", 1062)
        for code, qty in (("I03", "0"), ("I04", "007"), ("I05", "1.5"), ("I06", "-2")):
            self.rejected(db, code, O, f"order_item quantity {qty!r} is rejected",
                          f"INSERT INTO order_item(order_id,product_id,product_name_snapshot,unit_price_snapshot,quantity_snapshot,line_amount_snapshot) VALUES (1,2,'p2',20.00,'{qty}','20.00')", 3819)
        self.rejected(db, "I07", O, "A non-positive unit price snapshot is rejected",
                      "INSERT INTO order_item(order_id,product_id,product_name_snapshot,unit_price_snapshot,quantity_snapshot,line_amount_snapshot) VALUES (1,2,'p2',0,'1','0.00')", 3819)
        for code, column, value in (("I08", "product_name_snapshot", "'改名'"), ("I09", "unit_price_snapshot", "99.00"),
                                    ("I10", "quantity_snapshot", "'2'"), ("I11", "line_amount_snapshot", "'1.00'"),
                                    ("I12", "product_id", "2")):
            self.rejected(db, code, O, f"order_item.{column} is immutable", f"UPDATE order_item SET {column}={value} WHERE id=1", 1644)
        self.accepted(db, "I13", O, "Changing the product's name and price does not touch the stored snapshot",
                      "UPDATE product SET name='改名后', price=99.00 WHERE id=1")
        self.verify("I14", O, "The snapshot still holds the original name and unit price",
                    db.query("SELECT CONCAT(product_name_snapshot,':',unit_price_snapshot) FROM order_item WHERE id=1") == "p1:10.00")
        for code, column, value in (("O13", "total_amount", "'2.00'"), ("O14", "order_no", "'77777777-7777-7777-7777-777777777777'"),
                                    ("O15", "customer_id", "2"), ("O16", "created_at", "'2026-01-01 00:00:00'")):
            self.rejected(db, code, O, f"shop_order.{column} is immutable", f"UPDATE shop_order SET {column}={value} WHERE id=1", 1644)
        self.accepted(db, "O17", O, "PLACED -> CONFIRMED is accepted by the database", "UPDATE shop_order SET status='CONFIRMED' WHERE id=1")
        self.accepted(db, "O18", O, "A seller cancellation with initiator and time is accepted",
                      "UPDATE shop_order SET status='CANCELLED',cancelled_by='SELLER',cancelled_at='2026-11-02 11:00:00',cancel_reason='缺货' WHERE id=1")
        self.rejected(db, "O19", O, "A cancelled order cannot return to another state", "UPDATE shop_order SET status='PLACED' WHERE id=1", 1644)
        self.rejected(db, "O20", O, "Cancel metadata of a terminal order cannot be rewritten",
                      "UPDATE shop_order SET cancelled_by='CUSTOMER' WHERE id=1", 1644)
        self.accepted(db, "O21", O, "Another order can be completed", f"""INSERT INTO shop_order(id,order_no,customer_id,status,total_amount,created_at)
 VALUES (2,'88888888-8888-8888-8888-888888888888',1,'SHIPPED','5.00','2026-11-02 10:00:00');
 UPDATE shop_order SET status='COMPLETED' WHERE id=2;""")
        self.rejected(db, "O22", O, "A COMPLETED order cannot be cancelled afterwards",
                      "UPDATE shop_order SET status='CANCELLED',cancelled_by='SELLER',cancelled_at='2026-11-03 10:00:00' WHERE id=2", 1644)

        Q = "B-002"
        self.accepted(db, "F01", Q, "A favorite is stored", "INSERT INTO favorite(id,customer_id,product_id,created_at) VALUES (1,1,1,'2026-11-02 10:00:00')")
        self.rejected(db, "F02", Q, "A duplicate favorite is rejected",
                      "INSERT INTO favorite(customer_id,product_id,created_at) VALUES (1,1,'2026-11-02 11:00:00')", 1062)
        self.rejected(db, "F03", Q, "A favorite for an unknown product is rejected",
                      "INSERT INTO favorite(customer_id,product_id,created_at) VALUES (1,99,'2026-11-02 11:00:00')", 1452)
        self.accepted(db, "F04", Q, "Mutation counters are stored", "INSERT INTO favorite_mutation(customer_id,product_id,operation_seq,last_cancel_seq) VALUES (1,1,3,2)")
        self.rejected(db, "F05", Q, "last_cancel_seq above operation_seq is rejected",
                      "UPDATE favorite_mutation SET last_cancel_seq=9 WHERE customer_id=1 AND product_id=1", 3819)
        self.rejected(db, "F06", Q, "A second counter row for the same customer/product is rejected",
                      "INSERT INTO favorite_mutation(customer_id,product_id) VALUES (1,1)", 1062)
        self.accepted(db, "K01", Q, "A cart row with a huge quantity is stored",
                      f"INSERT INTO cart_item(id,customer_id,product_id,quantity,updated_at) VALUES (1,1,1,'{HUGE}','2026-11-02 10:00:00')")
        for code, qty in (("K02", "0"), ("K03", "-1"), ("K04", "1.5"), ("K05", "007"), ("K06", ""), ("K07", "1e2")):
            self.rejected(db, code, Q, f"cart quantity {qty!r} is rejected",
                          f"INSERT INTO cart_item(customer_id,product_id,quantity,updated_at) VALUES (1,2,'{qty}','2026-11-02 10:00:00')", 3819)
        self.rejected(db, "K08", Q, "A second cart row for the same customer/product is rejected",
                      "INSERT INTO cart_item(customer_id,product_id,quantity,updated_at) VALUES (1,1,'1','2026-11-02 10:00:00')", 1062)
        self.accepted(db, "K09", Q, "A removed row id is kept as a tombstone", "INSERT INTO cart_item_tombstone(cart_item_id,customer_id,product_id,removed_at) VALUES (1,1,1,'2026-11-02 12:00:00')")
        self.rejected(db, "K10", Q, "The same cart row id cannot be tombstoned twice",
                      "INSERT INTO cart_item_tombstone(cart_item_id,customer_id,product_id,removed_at) VALUES (1,1,1,'2026-11-02 13:00:00')", 1062)
        db.sql("DELETE FROM cart_item WHERE id=1")
        db.sql("INSERT INTO cart_item(customer_id,product_id,quantity,updated_at) VALUES (1,1,'2','2026-11-02 14:00:00')")
        self.verify("K11", Q, "Re-adding after deletion gets a new id; the deleted id is never reused",
                    int(db.query("SELECT id FROM cart_item WHERE customer_id=1 AND product_id=1")) > 1)

        R = "B-003"
        token = "'99999999-9999-9999-9999-999999999999'"
        self.accepted(db, "R01", R, "A confirmation with its rows is stored", f"""INSERT INTO checkout_confirmation(id,token,customer_id,total_amount,digest,created_at)
 VALUES (1,{token},1,'20.00','{'a' * 64}','2026-11-02 10:00:00');
 INSERT INTO checkout_confirmation_item(confirmation_id,cart_item_id,product_id,unit_price,quantity) VALUES (1,7,1,10.00,'2');""")
        self.rejected(db, "R02", R, "A duplicate confirmation token is rejected",
                      f"INSERT INTO checkout_confirmation(token,customer_id,total_amount,digest,created_at) VALUES ({token},1,'1.00','{'a' * 64}','2026-11-02 10:00:00')", 1062)
        self.rejected(db, "R03", R, "A confirmation row with quantity 0 is rejected",
                      "INSERT INTO checkout_confirmation_item(confirmation_id,cart_item_id,product_id,unit_price,quantity) VALUES (1,8,2,20.00,'0')", 3819)
        key = "'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'"
        self.accepted(db, "R04", R, "A receipt with a JSON payload is stored",
                      f"INSERT INTO operation_receipt(customer_id,operation_type,request_key,request_hash,result_payload,completed_at) VALUES (1,'CHECKOUT',{key},'{'b' * 64}','{{\"orderId\":\"1\"}}','2026-11-02 10:00:00')")
        self.rejected(db, "R05", R, "The same (customer, type, key) cannot be stored twice",
                      f"INSERT INTO operation_receipt(customer_id,operation_type,request_key,request_hash,result_payload,completed_at) VALUES (1,'CHECKOUT',{key},'{'c' * 64}','{{}}','2026-11-02 10:00:00')", 1062)
        self.accepted(db, "R06", R, "The same key is allowed for another operation type or customer", f"""INSERT INTO operation_receipt(customer_id,operation_type,request_key,request_hash,result_payload,completed_at) VALUES
 (1,'CART_ADD',{key},'{'b' * 64}','{{}}','2026-11-02 10:00:00'),(2,'CHECKOUT',{key},'{'b' * 64}','{{}}','2026-11-02 10:00:00')""")
        self.rejected(db, "R07", R, "An unknown operation type is rejected",
                      f"INSERT INTO operation_receipt(customer_id,operation_type,request_key,request_hash,result_payload,completed_at) VALUES (1,'REFUND','bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb','{'b' * 64}','{{}}','2026-11-02 10:00:00')", 3819)
        self.rejected(db, "R08", R, "A non-JSON payload is rejected",
                      f"INSERT INTO operation_receipt(customer_id,operation_type,request_key,request_hash,result_payload,completed_at) VALUES (1,'CART_ADD','cccccccc-cccc-cccc-cccc-cccccccccccc','{'b' * 64}','not json','2026-11-02 10:00:00')", 3819)

        L = "B-004"
        db.sql("INSERT INTO purchase_intent(id,product_id,customer_id,product_name_snapshot,buyer_name,buyer_phone,status,submitted_at,queue_seq) "
               "VALUES (1,1,1,'p1','c1','13800000000','QUEUING','2026-11-02 10:00:00',1)")
        self.rejected(db, "L01", L, "legacy_closed_at without a reason is rejected",
                      "UPDATE purchase_intent SET legacy_closed_at='2026-11-05 10:00:00' WHERE id=1", 3819)
        db.sql("INSERT INTO trade_attempt(id,intent_id,started_at,finished_at,result) VALUES (1,1,'2026-11-02 10:10:00','2026-11-02 10:20:00','SUCCESS')")
        self.rejected(db, "L02", L, "A finished attempt cannot be marked legacy-closed",
                      "UPDATE trade_attempt SET legacy_closed_at='2026-11-05 10:00:00' WHERE id=1", 3819)

    # ---- V7 / V8 upgrade ------------------------------------------------------------------------
    def upgrade_checks(self):
        db = self.db["upgraded"]
        self.build_v6(db)
        products = "SELECT id,stock,status,IFNULL(freeze_source,'-'),selling_mode FROM product ORDER BY id"
        stock_before = db.query("SELECT id,stock FROM product ORDER BY id")
        # Pre-V7 columns only: V7 adds columns, so SELECT * would differ in shape, not in data.
        intent_cols = "id,product_id,customer_id,product_name_snapshot,status,submitted_at,queue_seq"
        attempt_cols = "id,intent_id,started_at,finished_at,result,fail_action"
        product_cols = "id,name,price,stock,status,freeze_source,selling_mode,published_at"

        def history():
            return (db.query(f"SELECT {intent_cols} FROM purchase_intent WHERE id IN (25,26) ORDER BY id") +
                    db.query(f"SELECT {attempt_cols} FROM trade_attempt WHERE id IN (25,26) ORDER BY id"))

        def auction():
            return (db.query(f"SELECT {product_cols} FROM product WHERE id=16") +
                    db.query("SELECT * FROM auction_session") +
                    db.query(f"SELECT {intent_cols} FROM purchase_intent WHERE id=24") +
                    db.query(f"SELECT {attempt_cols} FROM trade_attempt WHERE id=24"))

        history_before, auction_before = history(), auction()
        status_before = db.query("SELECT status,COUNT(*) FROM purchase_intent GROUP BY status ORDER BY status")
        db.sql(V["V7"])
        U = "B-003"
        self.verify("U01", U, "V7 adds the new tables, stock LONGTEXT and offline_reason to an iteration-2 + auction database",
                    NEW_TABLES <= db.tables() and db.query(
                        "SELECT data_type FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='product' AND column_name='stock'") == "longtext")
        self.verify("U02", U, "Existing stock values survive the INT -> text conversion unchanged",
                    db.query("SELECT id,stock FROM product ORDER BY id") == stock_before)
        self.verify("U03", U, "offline_reason is initialised for fixed-price OFFLINE rows only (0 stock -> AUTO_ZERO, else MANUAL)",
                    db.query("SELECT id,IFNULL(offline_reason,'-') FROM product WHERE id IN (10,14,15,16,17) ORDER BY id") ==
                    "10\t-\n14\tAUTO_ZERO\n15\tMANUAL\n16\t-\n17\t-")
        self.verify("U04", "B-004", "V7 itself changes no intent/attempt/auction row and no product status",
                    db.query("SELECT status,COUNT(*) FROM purchase_intent GROUP BY status ORDER BY status") == status_before and
                    db.query("SELECT COUNT(*) FROM purchase_intent WHERE legacy_closed_at IS NOT NULL") == "0")
        after_v7 = self.fingerprint(db)
        r = db.sql(V["V7"], check=False)
        self.verify("U05", U, "Re-running V7 succeeds and changes nothing", r.returncode == 0 and self.fingerprint(db) == after_v7)

        # V8
        L = "B-004"
        pre = {"products": db.query(products), "stock": db.query("SELECT id,stock FROM product ORDER BY id")}
        result = db.sql(V["V8"], check=False)
        self.verify("U06", L, "V8 runs and reports 3 closed intents, 1 closed attempt, 1 unfrozen and 1 paused product",
                    result.returncode == 0 and result.stdout.decode().split() == ["3", "1", "1", "1"])
        self.verify("U07", L, "Live fixed-price intents are marked closed with their original status and snapshot kept",
                    db.query("SELECT id,status,IFNULL(legacy_close_reason,'-'),legacy_closed_at IS NOT NULL FROM purchase_intent WHERE id IN (21,22,23) ORDER BY id") ==
                    "21\tIN_TRANSACTION\tFIXED_PRICE_CHALLENGE_B\t1\n22\tQUEUING\tFIXED_PRICE_CHALLENGE_B\t1\n23\tQUEUING\tFIXED_PRICE_CHALLENGE_B\t1" and
                    db.query("SELECT product_name_snapshot FROM purchase_intent WHERE id=21") == "交易冻结一口价")
        self.verify("U08", L, "The unfinished fixed-price attempt is marked closed without inventing a result",
                    db.query("SELECT id,legacy_closed_at IS NOT NULL,IFNULL(result,'-'),finished_at IS NULL FROM trade_attempt WHERE id=21") == "21\t1\t-\t1")
        self.verify("U09", L, "Trade-frozen fixed-price product returns to ONLINE; manual-frozen becomes OFFLINE/MANUAL; stock untouched",
                    db.query("SELECT id,status,IFNULL(freeze_source,'-'),IFNULL(offline_reason,'-') FROM product WHERE id IN (11,13) ORDER BY id") ==
                    "11\tONLINE\t-\t-\n13\tOFFLINE\t-\tMANUAL" and
                    db.query("SELECT id,stock FROM product ORDER BY id") == pre["stock"])
        self.verify("U10", L, "Old SUCCESS/FAILED history is not rewritten",
                    history() == history_before and
                    db.query("SELECT COUNT(*) FROM purchase_intent WHERE id IN (25,26) AND legacy_closed_at IS NOT NULL") == "0")
        self.verify("U11", L, "The auction product, session, winner intent and its attempt are not touched",
                    auction() == auction_before and
                    db.query("SELECT COUNT(*) FROM purchase_intent WHERE id=24 AND legacy_closed_at IS NULL AND legacy_close_reason IS NULL") == "1" and
                    db.query("SELECT COUNT(*) FROM trade_attempt WHERE id=24 AND legacy_closed_at IS NULL") == "1" and
                    db.query("SELECT COUNT(*) FROM product WHERE id=16 AND offline_reason IS NULL") == "1")
        self.verify("U12", L, "No intent was converted to CANCELLED or FAILED by V8 (unlike the old V4 rule)",
                    db.query("SELECT status,COUNT(*) FROM purchase_intent GROUP BY status ORDER BY status") == status_before)
        after_v8 = self.fingerprint(db)
        r = db.sql(V["V8"], check=False)
        self.verify("U13", L, "Re-running V8 reports zero changes and leaves every row identical",
                    r.returncode == 0 and r.stdout.decode().split() == ["0", "0", "0", "0"] and self.fingerprint(db) == after_v8)
        self.verify("U14", "B-001,B-004", "Upgraded schema equals the fresh schema (columns, constraints, checks, indexes, triggers)",
                    self.signature(db) == self.signature(self.db["fresh"]))

        # refusal / resume paths
        db2 = self.db["needsv7"]
        self.build_v6(db2)
        before = self.fingerprint(db2)
        r = db2.sql(V["V8"], check=False)
        self.verify("U15", L, "V8 on a database without V7 stops and changes nothing",
                    r.returncode != 0 and b"requires the complete V7" in r.stderr and self.fingerprint(db2) == before)
        db3 = self.db["needsv6"]
        db3.sql(FIXTURE.read_text(encoding="utf-8-sig") + LEGACY_SEED)
        db3.sql(V["V4"] + V["V5"])
        before = self.fingerprint(db3)
        r = db3.sql(V["V7"], check=False)
        self.verify("U16", U, "V7 on a database without V6 stops and changes nothing",
                    r.returncode != 0 and b"requires the complete V6" in r.stderr and self.fingerprint(db3) == before)
        abnormal = self.db["abnormal"]
        self.build_v6(abnormal)
        abnormal.sql(V["V7"])
        abnormal.sql(f"INSERT INTO product(id,name,description,price,stock,category2_id,selling_mode,status,freeze_source,published_at) "
                     f"VALUES (30,'冻结且零库存','',1.00,'0',{CATEGORY},'FIXED_PRICE','FROZEN','TRADE','2026-11-01 10:00:00')")
        before = self.fingerprint(abnormal)
        r = abnormal.sql(V["V8"], check=False)
        self.verify("U17", L, "A frozen product with stock 0 stops V8 before any change, with a recovery message",
                    r.returncode != 0 and b"stock 0" in r.stderr and self.fingerprint(abnormal) == before)
        abnormal.sql("UPDATE product SET freeze_source=NULL WHERE id=30", check=False)
        resume = self.db["resume"]
        self.build_v6(resume)
        resume.sql(V["V7"])
        resume.sql("ALTER TABLE product DROP CHECK chk_product_stock, DROP CHECK chk_product_auction_stock")
        self.verify("U18", U, "Simulated interruption leaves the stock CHECKs missing",
                    resume.query("SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema=DATABASE() "
                                 "AND constraint_name IN ('chk_product_stock','chk_product_auction_stock')") == "0")
        r = resume.sql(V["V7"], check=False)
        self.verify("U19", U, "Re-running V7 re-creates the missing CHECKs and ends equal to the fresh schema",
                    r.returncode == 0 and self.signature(resume) == self.signature(self.db["fresh"]))
        self.rejected(resume, "U20", U, "The re-created stock CHECK rejects a negative value again",
                      "UPDATE product SET stock='-1' WHERE id=10", 3819)

    def finish(self):
        try:
            self.stop()
        finally:
            self.report["finished_at"] = datetime.now().isoformat(timespec="seconds")

    def save(self):
        self.report["summary"] = {"pass": sum(c["status"] == "PASS" for c in self.report["checks"]),
                                  "fail": sum(c["status"] == "FAIL" for c in self.report["checks"])}
        self.args.output.parent.mkdir(parents=True, exist_ok=True)
        self.args.output.write_text(json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"summary {self.report['summary']} -> {self.args.output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="mysql:8.0.46")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/test/evidence/r5-challenge-b-db/mysql-results.json")
    args = parser.parse_args()
    run = ChallengeBVerification(args)
    error = None
    try:
        run.start()
        run.schema_checks()
        run.constraint_checks()
        run.upgrade_checks()
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
