"""R5 auction-mode database acceptance (P-A01/P-A02) on a disposable MySQL container.

Reuses the iteration-2 harness: only the container created by this run is touched,
credentials and dumps stay out of the JSON, and the backend JAR runs with
ddl-auto=validate. Checks cover the fresh schema, V6 upgrade of an iteration-2
database, repeat/interrupted upgrades, backup restore, the winner fulfilment
link through the existing trade API, and restart persistence.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import traceback

from migrate_iteration2 import DockerMySQL, ROOT, TABLES, ITERATION2_TABLES, MIGRATIONS
from verify_iteration2_database import DB_DIR, FIXTURE, Verification

MONEY_COLUMNS = {("auction_session", "start_price"), ("auction_session", "min_increment"),
                 ("auction_session", "current_price"), ("auction_bid", "amount"),
                 ("auction_notification", "final_price"), ("product", "price")}
INDEXES = {("product", "idx_product_mode_status_time"), ("auction_session", "uk_auction_product"),
           ("auction_session", "uk_auction_winner_intent"), ("auction_session", "idx_auction_status_ends"),
           ("auction_bid", "uk_bid_auction_seq"), ("auction_bid", "uk_bid_auction_amount"),
           ("auction_bid", "idx_bid_customer_time"), ("auction_notification", "uk_notification_auction_type"),
           ("auction_notification", "idx_notification_customer_time"),
           ("auction_notification", "idx_notification_role_time")}
# Query samples handed to R1; each runs against the fresh database and is stored in the report.
QUERY_SAMPLES = {
    "public_snapshot": """SELECT p.id product_id, p.name, p.selling_mode, a.status, a.start_price, a.min_increment,
  a.current_price, a.bid_count, a.ends_at,
  CASE WHEN a.bid_count = 0 THEN a.start_price ELSE a.current_price + a.min_increment END next_min_bid,
  CONCAT(LEFT(c.username, 1), '***', RIGHT(c.username, 1)) leader_alias
FROM auction_session a JOIN product p ON p.id = a.product_id
LEFT JOIN customer c ON c.id = a.leader_customer_id WHERE p.id = {product}""",
    "lock_for_bid": "SELECT id, bid_count, current_price FROM auction_session WHERE product_id = {product} FOR UPDATE",
    "due_scan": "SELECT id FROM auction_session WHERE status = 'LIVE' AND ends_at <= '{now}' ORDER BY ends_at, id LIMIT 50",
    "recent_bids": "SELECT bid_seq, amount, bid_at FROM auction_bid WHERE auction_id = {auction} ORDER BY bid_seq DESC LIMIT 10",
    "customer_notifications": """SELECT id, notification_type, product_name_snapshot, final_price, read_at
FROM auction_notification WHERE recipient_customer_id = {customer} ORDER BY created_at DESC, id DESC LIMIT 20""",
    "seller_notifications": """SELECT id, notification_type, product_name_snapshot, final_price, read_at
FROM auction_notification WHERE recipient_role = 'SELLER' ORDER BY created_at DESC, id DESC LIMIT 20""",
    "winner_fulfilment": """SELECT a.id auction_id, a.status, a.current_price final_price, i.id intent_id, i.status intent_status,
  h.status history_status FROM auction_session a JOIN purchase_intent i ON i.id = a.winner_intent_id
LEFT JOIN order_history h ON h.intent_id = i.id WHERE a.id = {auction}""",
}


class AuctionVerification(Verification):
    def __init__(self, args):
        super().__init__(args)
        self.container = "oxstore-r5-auction-" + self.owner[:12]
        self.report["scope"] = ("Disposable MySQL: auction schema constraints, JPA validate, winner fulfilment via "
                                "existing trade API, V6 upgrade/repeat/resume/restore, restart")
        self.report["query_samples"] = {}

    def setup_database(self):
        super().setup_database(("fresh", "iteration2", "restored", "staged", "incomplete", "legacyonly"))

    def check(self, code, tasks, description, condition):
        self.verify(code, tasks, description, condition)

    def iteration2_db(self, name):
        db = DockerMySQL(self.container, name)
        db.sql(FIXTURE.read_text(encoding="utf-8-sig") + LEGACY_SEED)
        for migration in ("V4__iteration2_customer_inventory_catalog.sql", "V5__iteration2_database_contract.sql"):
            db.sql((MIGRATIONS / migration).read_text(encoding="utf-8"))
        return db

    def schema_checks(self):
        db = self.fresh
        self.check("S01", "P-A01,P-A02", "Fresh schema has 9 iteration-2 tables plus 3 auction tables",
                   db.tables() == TABLES and TABLES - ITERATION2_TABLES == {"auction_session", "auction_bid", "auction_notification"})
        types = db.query("SELECT CONCAT(table_name,'.',column_name,'=',column_type) FROM information_schema.columns "
                         "WHERE table_schema=DATABASE() AND data_type='decimal' ORDER BY 1").splitlines()
        self.check("S02", "P-A01,P-A02", "All money columns are DECIMAL(10,2)",
                   {tuple(t.split("=")[0].split(".")) for t in types} == MONEY_COLUMNS and
                   all(t.endswith("=decimal(10,2)") for t in types))
        present = set(tuple(row.split("\t")) for row in db.query(
            "SELECT DISTINCT table_name,index_name FROM information_schema.statistics WHERE table_schema=DATABASE()").splitlines())
        self.check("S03", "P-A01,P-A02", "Auction lookup, due-scan, bid history and reminder indexes exist", INDEXES <= present)
        self.check("S04", "P-A01", "Mode-immutability trigger is installed",
                   db.query("SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema=DATABASE() "
                            "AND trigger_name='trg_product_selling_mode_immutable'") == "1")

    def http_and_constraints(self):
        db = self.fresh
        self.seller = self.login("admin", seller=True)
        for name in ("auction_buyer_a", "auction_buyer_b"):
            self.request("POST", "/api/auth/register", {"username": name, "password": self.customer_password,
                         "phone": "13800000000"}, expected=201)
        self.a, self.b = self.login("auction_buyer_a"), self.login("auction_buyer_b")
        tree = self.request("GET", "/api/categories/tree")
        self.leaf = tree[0]["children"][0]["id"]
        fixed = self.publish("一口价回归商品", 2)["productId"]
        intent = self.request("POST", f"/api/products/{fixed}/intents", token=self.a)["intentId"]
        self.request("POST", f"/api/admin/intents/{intent}/start", token=self.seller)
        self.request("POST", f"/api/admin/intents/{intent}/success", token=self.seller)
        self.check("F01", "P-A01", "Products published by the existing API default to FIXED_PRICE and keep the intent flow",
                   db.query(f"SELECT CONCAT(selling_mode,':',stock,':',status) FROM product WHERE id={fixed}") == "FIXED_PRICE:1:ONLINE" and
                   db.query(f"SELECT status FROM order_history WHERE intent_id={intent}") == "SUCCESS")
        self.failed_sql(db, "F02", "P-A01", "Trigger refuses switching a published product to AUCTION",
                        f"UPDATE product SET selling_mode='AUCTION' WHERE id={fixed}", 1644)
        self.failed_sql(db, "F03", "P-A01", "Unknown selling modes are rejected",
                        f"INSERT INTO product(name,description,price,stock,category2_id,selling_mode,status,published_at) "
                        f"VALUES('x','',1,1,{self.leaf},'RENTAL','ONLINE',NOW(6))", 3819)
        self.failed_sql(db, "F04", "P-A01", "An auction product cannot hold more than one item",
                        f"INSERT INTO product(name,description,price,stock,category2_id,selling_mode,status,published_at) "
                        f"VALUES('x','',1,2,{self.leaf},'AUCTION','ONLINE',NOW(6))", 3819)

        customers = db.query("SELECT id FROM customer WHERE username LIKE 'auction_buyer_%' ORDER BY username").splitlines()
        ca, cb = customers
        db.sql(f"""INSERT INTO product(name,description,price,stock,category2_id,selling_mode,status,published_at,status_updated_at)
VALUES('拍卖专项商品','',10.00,1,{self.leaf},'AUCTION','ONLINE',NOW(6),NOW(6));
SET @p = LAST_INSERT_ID();
INSERT INTO auction_session(product_id,start_price,min_increment,status,starts_at,ends_at)
VALUES(@p,10.00,1.50,'LIVE',NOW(6),DATE_ADD(NOW(6), INTERVAL 1 DAY));""")
        product = db.query("SELECT id FROM product WHERE name='拍卖专项商品'")
        auction = db.query(f"SELECT id FROM auction_session WHERE product_id={product}")
        self.check("B01", "P-A01", "A live session starts without bids, price or leader",
                   db.query(f"SELECT CONCAT(bid_count,':',IFNULL(current_price,'-'),':',IFNULL(leader_customer_id,'-'),':',status) "
                            f"FROM auction_session WHERE id={auction}") == "0:-:-:LIVE")
        self.failed_sql(db, "B02", "P-A01", "A second session for the same product is rejected",
                        f"INSERT INTO auction_session(product_id,start_price,min_increment,status,starts_at,ends_at) "
                        f"VALUES({product},1,1,'LIVE',NOW(6),DATE_ADD(NOW(6), INTERVAL 1 DAY))", 1062)
        for code, description, statement in (
                ("B03", "Non-positive start price is rejected", f"UPDATE auction_session SET start_price=0 WHERE id={auction}"),
                ("B04", "Deadline not after start is rejected", f"UPDATE auction_session SET ends_at=starts_at WHERE id={auction}"),
                ("B05", "Unknown session status is rejected", f"UPDATE auction_session SET status='SCHEDULED' WHERE id={auction}"),
                ("B06", "Price without a recorded bid/leader is rejected", f"UPDATE auction_session SET current_price=10 WHERE id={auction}"),
                ("B07", "A counted bid without a current price is rejected",
                 f"UPDATE auction_session SET bid_count=1,leader_customer_id=(SELECT MIN(id) FROM customer) WHERE id={auction}"),
                ("B08", "ENDED_SOLD without a winner intent is rejected",
                 f"UPDATE auction_session SET status='ENDED_SOLD',settled_at=NOW(6) WHERE id={auction}")):
            self.failed_sql(db, code, "P-A01", description, statement, 3819)

        db.sql(f"""INSERT INTO auction_bid(auction_id,bid_seq,customer_id,amount,bid_at) VALUES({auction},1,{ca},10.00,NOW(6));
UPDATE auction_session SET bid_count=1,current_price=10.00,leader_customer_id={ca},version=version+1 WHERE id={auction};
INSERT INTO auction_bid(auction_id,bid_seq,customer_id,amount,bid_at) VALUES({auction},2,{cb},11.50,NOW(6));
UPDATE auction_session SET bid_count=2,current_price=11.50,leader_customer_id={cb},version=version+1 WHERE id={auction};""")
        self.check("G01", "P-A02", "Each accepted bid is traceable by sequence, buyer, amount and time",
                   db.query(f"SELECT GROUP_CONCAT(CONCAT(bid_seq,':',customer_id,':',amount) ORDER BY bid_seq) FROM auction_bid "
                            f"WHERE auction_id={auction}") == f"1:{ca}:10.00,2:{cb}:11.50")
        self.failed_sql(db, "G02", "P-A02", "A concurrent writer reusing a bid sequence is rejected",
                        f"INSERT INTO auction_bid(auction_id,bid_seq,customer_id,amount,bid_at) VALUES({auction},2,{ca},13.00,NOW(6))", 1062)
        self.failed_sql(db, "G03", "P-A02", "Two accepted bids with the same amount are rejected",
                        f"INSERT INTO auction_bid(auction_id,bid_seq,customer_id,amount,bid_at) VALUES({auction},3,{ca},11.50,NOW(6))", 1062)
        self.failed_sql(db, "G04", "P-A02", "Bids must reference an existing customer",
                        f"INSERT INTO auction_bid(auction_id,bid_seq,customer_id,amount,bid_at) VALUES({auction},3,999999,20.00,NOW(6))", 1452)

        # Simulate the P-A07 settlement transaction, then finish through the unchanged trade API.
        db.sql(f"""START TRANSACTION;
UPDATE product SET status='FROZEN',freeze_source='TRADE',status_updated_at=NOW(6) WHERE id={product};
INSERT INTO purchase_intent(product_id,customer_id,product_name_snapshot,buyer_name,buyer_phone,status,submitted_at,queue_seq,processed_at)
SELECT {product},id,'拍卖专项商品',username,phone,'IN_TRANSACTION',NOW(6),1,NOW(6) FROM customer WHERE id={cb};
SET @i = LAST_INSERT_ID();
INSERT INTO trade_attempt(intent_id,started_at) VALUES(@i,NOW(6));
INSERT INTO product_status_event(product_id,trade_attempt_id,event_type,from_status,to_status,freeze_source,occurred_at)
VALUES({product},LAST_INSERT_ID(),'TRADE_STARTED','ONLINE','FROZEN','TRADE',NOW(6));
UPDATE auction_session SET ends_at=DATE_ADD(starts_at, INTERVAL 1 SECOND),status='ENDED_SOLD',settled_at=NOW(6),
  winner_intent_id=@i,version=version+1 WHERE id={auction} AND status='LIVE';
INSERT INTO auction_notification(auction_id,notification_type,recipient_role,recipient_customer_id,product_name_snapshot,final_price,created_at)
VALUES({auction},'AUCTION_SOLD','SELLER',NULL,'拍卖专项商品',11.50,NOW(6)),
      ({auction},'AUCTION_WON','CUSTOMER',{cb},'拍卖专项商品',11.50,NOW(6));
COMMIT;""")
        winner = db.query(f"SELECT winner_intent_id FROM auction_session WHERE id={auction}")
        self.failed_sql(db, "N01", "P-A02", "Repeated settlement reminders for the same session/type are rejected",
                        f"INSERT INTO auction_notification(auction_id,notification_type,recipient_role,recipient_customer_id,"
                        f"product_name_snapshot,final_price,created_at) VALUES({auction},'AUCTION_WON','CUSTOMER',{cb},'x',11.50,NOW(6))", 1062)
        self.failed_sql(db, "N02", "P-A02", "Seller reminders cannot carry a customer recipient",
                        f"UPDATE auction_notification SET recipient_customer_id={ca} WHERE auction_id={auction} AND notification_type='AUCTION_SOLD'", 3819)
        self.failed_sql(db, "N03", "P-A02", "A sold reminder must carry the final price",
                        f"UPDATE auction_notification SET final_price=NULL WHERE auction_id={auction} AND notification_type='AUCTION_WON'", 3819)
        self.request("POST", f"/api/admin/intents/{winner}/success", token=self.seller)
        self.check("W01", "P-A01,P-A04", "Winner intent completes through the existing success API: stock 0, offline, SUCCESS history",
                   db.query(f"SELECT CONCAT(stock,':',status,':',selling_mode) FROM product WHERE id={product}") == "0:OFFLINE:AUCTION" and
                   db.query(f"SELECT status FROM order_history WHERE intent_id={winner}") == "SUCCESS" and
                   db.query(f"SELECT status FROM auction_session WHERE id={auction}") == "ENDED_SOLD")
        self.check("W02", "P-A02", "Reminders are listable per winner and for sellers",
                   db.query(f"SELECT COUNT(*) FROM auction_notification WHERE recipient_customer_id={cb}") == "1" and
                   db.query("SELECT COUNT(*) FROM auction_notification WHERE recipient_role='SELLER'") == "1")

        db.sql(f"""INSERT INTO product(name,description,price,stock,category2_id,selling_mode,status,published_at,status_updated_at)
VALUES('流拍专项商品','',5.00,1,{self.leaf},'AUCTION','ONLINE',NOW(6),NOW(6));
INSERT INTO auction_session(product_id,start_price,min_increment,status,starts_at,ends_at)
VALUES(LAST_INSERT_ID(),5.00,1.00,'LIVE',DATE_SUB(NOW(6), INTERVAL 2 MINUTE),DATE_SUB(NOW(6), INTERVAL 1 MINUTE));""")
        unsold = db.query("SELECT a.id FROM auction_session a JOIN product p ON p.id=a.product_id WHERE p.name='流拍专项商品'")
        now = db.query("SELECT NOW(6)")
        self.check("U01", "P-A01", "Due scan returns the expired LIVE session only",
                   db.query(QUERY_SAMPLES["due_scan"].format(now=now)) == unsold)
        settle = (f"UPDATE auction_session SET status='ENDED_UNSOLD',settled_at=NOW(6),version=version+1 "
                  f"WHERE id={unsold} AND status='LIVE' AND bid_count=0 AND ends_at<=NOW(6); SELECT ROW_COUNT();")
        first, second = db.query(settle), db.query(settle)
        self.check("U02", "P-A01", "Conditional settlement applies once; a repeated scan changes nothing", (first, second) == ("1", "0"))
        self.failed_sql(db, "U03", "P-A01", "An unsold session cannot link a winner intent",
                        f"UPDATE auction_session SET winner_intent_id={intent} WHERE id={unsold}", 3819)

        context = {"product": product, "auction": auction, "customer": cb, "now": now}
        for name, sql in QUERY_SAMPLES.items():
            text = sql.format(**context)
            self.report["query_samples"][name] = {"sql": text, "rows": db.query(text).splitlines()}
        self.check("Q01", "P-A01,P-A02", "Handoff query samples run and the snapshot masks the leader",
                   self.report["query_samples"]["public_snapshot"]["rows"][0].endswith("a***b") and
                   len(self.report["query_samples"]["recent_bids"]["rows"]) == 2)
        explain = db.query(f"EXPLAIN FORMAT=TRADITIONAL {QUERY_SAMPLES['due_scan'].format(now=now)}")
        self.report["due_scan_explain"] = explain
        self.check("Q02", "P-A01", "Due scan can use idx_auction_status_ends", "idx_auction_status_ends" in explain)

    def migrations(self, scratch):
        old = self.iteration2_db("iteration2")
        old.sql(f"INSERT INTO product(name,description,price,stock,category2_id,status,published_at) "
                f"SELECT '迭代2在售商品','',8.00,3,id,'ONLINE',NOW(6) FROM category WHERE parent_id IS NOT NULL LIMIT 1;")
        product_cols = "id,name,description,price,stock,category2_id,status,freeze_source,published_at,status_updated_at,sold_at"
        def legacy_view(db):
            body = db.query(f"SELECT {product_cols} FROM product ORDER BY id") + "\n" + "\n".join(
                t + "\n" + db.query(f"SELECT * FROM {t} ORDER BY id") for t in sorted(ITERATION2_TABLES - {"product"}))
            return hashlib.sha256(body.encode()).hexdigest()
        before, before_full = legacy_view(old), self.fingerprint(old)
        upgraded = old.upgrade(scratch / "backups")
        self.check("M01", "P-A01,P-A02", "Iteration-2 database is backed up, then receives V5/V6",
                   upgraded["phase_before"] == "iteration2" and upgraded["applied"] == ["V5", "V6"] and
                   Path(upgraded["backup"]).stat().st_size > 0)
        self.check("M02", "P-A01", "Every existing product becomes FIXED_PRICE and existing data is unchanged",
                   old.query("SELECT COUNT(*) FROM product WHERE selling_mode<>'FIXED_PRICE'") == "0" and
                   old.query("SELECT COUNT(*) FROM product") == "3" and legacy_view(old) == before and
                   old.query("SELECT COUNT(*) FROM auction_session") == "0")
        self.check("M03", "P-A01,P-A02", "Upgraded and fresh schemas agree on columns, constraints and indexes",
                   self.schema_signature(old) == self.schema_signature(self.fresh))
        after = self.fingerprint(old)
        repeat = old.upgrade(scratch / "backups")
        self.check("M04", "P-A01,P-A02", "Repeated upgrade is recognized as auction phase and changes no data",
                   repeat["phase_before"] == "auction" and repeat["applied"] == ["V5", "V6"] and self.fingerprint(old) == after)
        restored = DockerMySQL(self.container, "restored")
        restored.sql(Path(upgraded["backup"]).read_text(encoding="utf-8"))
        self.check("M05", "P-A01", "Backup restores the pre-V6 iteration-2 database exactly",
                   restored.tables() == ITERATION2_TABLES and self.fingerprint(restored) == before_full)
        staged = self.iteration2_db("staged")
        staged.sql("ALTER TABLE product ADD COLUMN selling_mode VARCHAR(20) NOT NULL DEFAULT 'FIXED_PRICE' AFTER category2_id;"
                   + (MIGRATIONS / "V6__auction_mode.sql").read_text(encoding="utf-8").split("CREATE TABLE IF NOT EXISTS auction_bid")[0])
        staged.sql((MIGRATIONS / "V5__iteration2_database_contract.sql").read_text(encoding="utf-8"))
        staged.sql((MIGRATIONS / "V6__auction_mode.sql").read_text(encoding="utf-8"))
        self.check("M06", "P-A01,P-A02", "V6 resumes after an interrupted run (procedure and session table done) and matches the fresh schema",
                   self.schema_signature(staged) == self.schema_signature(self.fresh))
        legacy_only = DockerMySQL(self.container, "legacyonly")
        legacy_only.sql(FIXTURE.read_text(encoding="utf-8-sig") + LEGACY_SEED)
        legacy_before = self.fingerprint(legacy_only)
        result = legacy_only.sql((MIGRATIONS / "V6__auction_mode.sql").read_text(encoding="utf-8"), check=False)
        self.check("M07", "P-A01", "Direct V6 on a pre-V5 database stops before any change",
                   result.returncode != 0 and self.fingerprint(legacy_only) == legacy_before and
                   "selling_mode" not in legacy_only.columns("product"))
        incomplete = DockerMySQL(self.container, "incomplete")
        incomplete.sql((DB_DIR / "schema.sql").read_text(encoding="utf-8"))
        incomplete.sql("ALTER TABLE auction_notification DROP CHECK chk_notification_recipient, DROP COLUMN recipient_role;")
        try:
            incomplete.upgrade(scratch / "backups")
        except RuntimeError:
            refused = True
        else:
            refused = False
        self.check("M08", "P-A02", "A twelve-table layout missing an auction column is refused", refused)
        self.report["backup_restore"] = {"backup_sha256": upgraded["backup_sha256"], "before_data_sha256": before_full,
                                         "restored_data_sha256": self.fingerprint(restored)}

    def restart(self, scratch):
        before = self.fingerprint(self.fresh)
        self.stop_app()
        self.command(["docker", "restart", self.container])
        self.wait_mysql()
        self.check("R01", "P-A01,P-A02", "MySQL restart preserves sessions, bids, reminders and the fulfilment link",
                   self.fingerprint(self.fresh) == before and
                   self.fresh.query("SELECT COUNT(*) FROM auction_session WHERE winner_intent_id IS NOT NULL") == "1" and
                   self.fresh.query("SELECT COUNT(*) FROM auction_bid") == "2" and
                   self.fresh.query("SELECT COUNT(*) FROM auction_notification") == "2")
        self.start_app("iteration2", scratch)
        self.check("R02", "P-A01,P-A02", "Backend starts with ddl-auto=validate on the V6-upgraded database",
                   bool(self.login("admin", seller=True)))
        self.stop_app()

    def save(self):
        for path in [*sorted((ROOT / "backend/src/main/resources/db").rglob("*.sql")),
                     *sorted((ROOT / "backend/src/main/java/com/team/shop").rglob("Auction*.java")),
                     ROOT / "backend/src/main/java/com/team/shop/entity/Product.java",
                     Path(__file__), ROOT / "scripts/migrate_iteration2.py", ROOT / "scripts/verify_iteration2_database.py",
                     self.args.jar]:
            self.report["source_sha256"][path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.report["finished_at"] = datetime.now().astimezone().isoformat()
        self.args.output.parent.mkdir(parents=True, exist_ok=True)
        self.args.output.write_text(json.dumps(self.report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


LEGACY_SEED = """
INSERT INTO seller(id,username,password_hash) VALUES(1,'legacy_admin','legacy-fixture-hash');
INSERT INTO product(id,name,description,image_path,price,status,published_at) VALUES
 (1,'旧商品中文','旧描述','/api/images/legacy.png',12.50,'ONLINE','2026-10-01 10:00:00'),
 (2,'历史售出商品','历史描述','/api/images/history.jpg',2.00,'SOLD','2026-09-30 10:00:00');
INSERT INTO purchase_intent(id,product_id,buyer_name,buyer_phone,token_hash,token_lookup,status,submitted_at,queue_seq) VALUES
 (1,2,'历史买家','13800000000','old-hash','old-lookup-1','SUCCESS','2026-10-01 09:00:00',1);
INSERT INTO trade_attempt(id,intent_id,started_at,finished_at,result) VALUES
 (1,1,'2026-10-01 09:10:00','2026-10-01 09:20:00','SUCCESS');
INSERT INTO product_status_event(product_id,event_type,from_status,to_status,occurred_at) VALUES
 (1,'PUBLISHED',NULL,'ONLINE','2026-10-01 10:00:00');
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="mysql:8.0.46")
    parser.add_argument("--java", default="java")
    parser.add_argument("--jar", type=Path, default=ROOT / "backend/target/shop-0.1.0.jar")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/test/evidence/r5-auction-db/mysql-results.json")
    args = parser.parse_args()
    run = AuctionVerification(args)
    run.report["java_version"] = run.command([args.java, "-version"]).stderr.decode("utf-8", errors="replace").strip()
    error = None
    try:
        with tempfile.TemporaryDirectory(prefix="oxstore-r5-auction-") as temp:
            scratch = Path(temp)
            run.setup_database()
            run.schema_checks()
            run.start_app("fresh", scratch)
            run.check("D03", "P-A01,P-A02", "Backend validates the auction tables with Hibernate ddl-auto=validate", True)
            run.http_and_constraints()
            run.migrations(scratch)
            run.restart(scratch)
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
