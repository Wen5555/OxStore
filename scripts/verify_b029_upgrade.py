"""R5 B-029: upgrade rehearsal, repeat run, interruption and restart persistence for the challenge-B schema.

Drives scripts/migrate_challenge_b.py (the delivered upgrade tool) against disposable databases inside one
disposable mysql container created and removed by this run. No installed MySQL, existing container or real
business database is touched. Backups taken by the tool stay in a temp directory that is deleted afterwards
and never enter the evidence file. This is R5's data-layer rehearsal, not R2's independent acceptance (B-035).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile
import time
import traceback

from migrate_challenge_b import ChallengeBUpgrade, UpgradeFailed, CHALLENGE_B_TABLES
from migrate_iteration2 import ROOT
from verify_auction_database import LEGACY_SEED
from verify_challenge_b_database import ChallengeBVerification, V, CATEGORY
from verify_iteration2_database import DB_DIR, FIXTURE

INTENT = "id,product_id,customer_id,product_name_snapshot,status,submitted_at,queue_seq"
ATTEMPT = "id,intent_id,started_at,finished_at,result,fail_action"
PRODUCT = "id,name,price,stock,status,freeze_source,selling_mode,published_at"
UNCHANGED = ("seller", "customer", "category", "product_image", "order_history", "product_status_event",
             "auction_session", "auction_bid", "auction_notification")
EXTRA_LEGACY = ("INSERT INTO purchase_intent(id,product_id,buyer_name,buyer_phone,token_hash,token_lookup,status,submitted_at,queue_seq) "
                "VALUES (2,1,'排队买家','13800000009','h2','lookup-2','QUEUING','2026-10-02 09:00:00',1);")


class B029(ChallengeBVerification):
    def __init__(self, args):
        super().__init__(args)
        self.report["scope"] = "Upgrade rehearsal with the delivered tool on disposable databases (MySQL container)"
        self.backups = Path(tempfile.mkdtemp(prefix="oxstore-b029-backups-"))
        self.results = {}
        self.report["scenario_errors"] = []

    def new_db(self, name):
        self.admin_sql(f"CREATE DATABASE {name} CHARACTER SET utf8mb4;")
        return ChallengeBUpgrade(self.container, name)

    def rows(self, db, tables=UNCHANGED):
        return {t: db.query(f"SELECT * FROM `{t}` ORDER BY 1") for t in tables}

    def core(self, db):
        return {"product": db.query(f"SELECT {PRODUCT} FROM product ORDER BY id"),
                "intent": db.query(f"SELECT {INTENT} FROM purchase_intent ORDER BY id"),
                "attempt": db.query(f"SELECT {ATTEMPT} FROM trade_attempt ORDER BY id"), **self.rows(db)}

    def upgrade(self, db):
        return db.upgrade_to_challenge_b(self.backups)

    def restore(self, backup, name):
        target = self.new_db(name)
        target.sql(Path(backup).read_text(encoding="utf-8"))
        return target

    def public(self, result):
        keep = ("phase_before", "phase_after", "applied", "v8_counts", "backup_bytes", "failed_at")
        return {k: result[k] for k in keep if k in result} | {"backup_sha256_prefix": result["backup_sha256"][:12]}

    # ---- scenarios -------------------------------------------------------------------------------
    def fresh_reference(self):
        self.fresh = self.db["fresh"]
        self.fresh.sql((DB_DIR / "schema.sql").read_text(encoding="utf-8"))
        self.fresh_signature = self.signature(self.fresh)

    def p1_legacy(self):
        db = self.new_db("p1_legacy")
        db.sql(FIXTURE.read_text(encoding="utf-8-sig") + LEGACY_SEED + EXTRA_LEGACY)
        before = {"intents": db.query("SELECT COUNT(*) FROM purchase_intent"), "products": db.query("SELECT COUNT(*) FROM product"),
                  "history": db.query("SELECT COUNT(*) FROM order_history") if "order_history" in db.tables() else None,
                  "name": db.query("SELECT name FROM product WHERE id=1"), "success": db.query("SELECT status FROM purchase_intent WHERE id=1 OR id=2 ORDER BY id")}
        result = self.upgrade(db)
        self.results["p1"] = self.public(result)
        self.verify("P1a", "B-029", "An iteration-1 database is classified 'legacy' and upgraded through V4,V5,V6,V7,V8 by the tool",
                    result["phase_before"] == "legacy" and result["applied"] == ["V4", "V5", "V6", "V7", "V8"] and result["phase_after"] == "challenge_b")
        self.verify("P1b", "B-029", "No product or intent row is lost and Chinese text survives",
                    db.query("SELECT COUNT(*) FROM product") == before["products"] and db.query("SELECT COUNT(*) FROM purchase_intent") == before["intents"]
                    and db.query("SELECT name FROM product WHERE id=1") == before["name"])
        self.verify("P1c", "B-029", "Upgraded legacy schema equals the fresh challenge-B schema", self.signature(db) == self.fresh_signature)
        self.verify("P1d", "B-029", "Legacy products (stock never persisted) end OFFLINE with offline_reason AUTO_ZERO and stock 0",
                    db.query("SELECT COUNT(DISTINCT CONCAT(status,':',stock,':',IFNULL(offline_reason,'-'))) FROM product") == "1" and
                    db.query("SELECT CONCAT(status,':',stock,':',offline_reason) FROM product LIMIT 1") == "OFFLINE:0:AUTO_ZERO")
        self.p1 = db

    def p2_auction_data(self):
        db = self.new_db("p2_auction")
        self.build_v6(db)
        before = self.core(db)
        status_counts = db.query("SELECT status,COUNT(*) FROM purchase_intent GROUP BY status ORDER BY status")
        result = self.upgrade(db)
        self.results["p2"] = self.public(result)
        self.verify("P2a", "B-029,B-004", "An iteration-2+auction database is classified 'auction' and gets V7,V8 only",
                    result["phase_before"] == "auction" and result["applied"] == ["V7", "V8"])
        self.verify("P2b", "B-004", "V8 reports 3 closed intents, 1 closed attempt, 1 unfrozen and 1 paused fixed-price product",
                    result["v8_counts"] == {"closed_intents": 3, "closed_attempts": 1, "unfrozen_products": 1, "paused_products": 1})
        after = self.core(db)
        self.verify("P2c", "B-029,B-004", "Auction rows and old SUCCESS/FAILED history are unchanged; no intent was turned into CANCELLED/FAILED",
                    all(after[k] == before[k] for k in UNCHANGED) and
                    db.query("SELECT status,COUNT(*) FROM purchase_intent GROUP BY status ORDER BY status") == status_counts and
                    db.query("SELECT COUNT(*) FROM purchase_intent WHERE id IN (24,25,26) AND legacy_closed_at IS NOT NULL") == "0")
        self.verify("P2d", "B-029,B-004", "Original intent status and snapshots of the closed fixed-price intents are kept",
                    db.query("SELECT id,status,product_name_snapshot FROM purchase_intent WHERE id IN (21,22,23) ORDER BY id") ==
                    "21\tIN_TRANSACTION\t交易冻结一口价\n22\tQUEUING\t排队中一口价\n23\tQUEUING\t排队中一口价")
        self.verify("P2e", "B-029", "Upgraded schema equals the fresh challenge-B schema", self.signature(db) == self.fresh_signature)
        self.p2, self.p2_before, self.p2_result = db, before, result

    def p2b_from_iteration2(self):
        db = self.new_db("p2b_iter2")
        db.sql(FIXTURE.read_text(encoding="utf-8-sig") + LEGACY_SEED + V["V4"] + V["V5"])
        result = self.upgrade(db)
        self.results["p2b"] = self.public(result)
        self.verify("P2f", "B-029", "A database stopped at iteration 2 is classified 'iteration2' and gets V5,V6,V7,V8",
                    result["phase_before"] == "iteration2" and result["applied"] == ["V5", "V6", "V7", "V8"] and self.signature(db) == self.fresh_signature)

    def p3_repeat(self):
        db = self.p2
        before = self.fingerprint(db)
        result = self.upgrade(db)
        self.results["p3"] = self.public(result)
        self.verify("P3", "B-029,B-004", "Running the tool again classifies 'challenge_b', V8 reports four zeros and every row of every table is identical "
                    "(no second unfreeze, no duplicated or re-closed records)",
                    result["phase_before"] == "challenge_b" and result["v8_counts"] == dict.fromkeys(
                        ("closed_intents", "closed_attempts", "unfrozen_products", "paused_products"), 0) and self.fingerprint(db) == before)

    def p4_interrupted(self):
        db = self.new_db("p4_interrupted")
        self.build_v6(db)
        db.sql(V["V7"])
        for table in ("order_item", "shop_order", "favorite_mutation", "favorite", "cart_item_tombstone", "cart_item",
                      "checkout_confirmation_item", "checkout_confirmation", "operation_receipt"):
            db.sql(f"DROP TABLE {table}")
        self.verify("P4a", "B-029", "Simulated interruption after V7's column changes (new tables missing) is still classified 'auction'",
                    db.classify() == "auction")
        result = self.upgrade(db)
        self.results["p4"] = self.public(result)
        self.verify("P4b", "B-029", "Re-running the tool completes the upgrade and the schema equals the fresh schema",
                    result["phase_after"] == "challenge_b" and self.signature(db) == self.fresh_signature and
                    db.query("SELECT COUNT(*) FROM purchase_intent WHERE legacy_closed_at IS NOT NULL") == "3")
        partial = self.new_db("p4_partial")
        partial.sql((DB_DIR / "schema.sql").read_text(encoding="utf-8"))
        partial.sql("DROP TABLE auction_notification")
        marker = self.fingerprint(partial)
        refused = False
        try:
            self.upgrade(partial)
        except RuntimeError:
            refused = True
        self.verify("P4c", "B-029", "A layout missing a table is refused before any backup or change",
                    refused and self.fingerprint(partial) == marker and not any(self.backups.glob("p4_partial-*")))

    def p5_abnormal_and_restore(self):
        db = self.new_db("p5_abnormal")
        self.build_v6(db)
        db.sql(f"INSERT INTO product(id,name,description,price,stock,category2_id,selling_mode,status,freeze_source,published_at) "
               f"VALUES (30,'冻结且零库存','',1.00,0,{CATEGORY},'FIXED_PRICE','FROZEN','TRADE','2026-11-01 10:00:00')")
        before = self.core(db)
        failed = None
        try:
            self.upgrade(db)
        except UpgradeFailed as error:
            failed = error.result
        self.results["p5"] = {k: failed[k] for k in ("phase_before", "applied", "failed_at") if failed and k in failed}
        self.verify("P5a", "B-029,B-004", "A frozen product with stock 0 stops the upgrade at V8 with a recovery instruction and a kept backup",
                    bool(failed) and failed["failed_at"] == "V8" and "stock 0" in failed["error"] and "recovery" in failed and Path(failed["backup"]).exists())
        self.verify("P5b", "B-004", "V8 changed no data before stopping (V7 DDL stays, as documented)",
                    self.core(db) == before and db.query("SELECT COUNT(*) FROM purchase_intent WHERE legacy_closed_at IS NOT NULL") == "0")
        restored = self.restore(failed["backup"], "p5_restored")
        self.verify("P5c", "B-029", "The pre-upgrade backup restores into a scratch database with identical data and no challenge-B tables",
                    self.core(restored) == before and not (CHALLENGE_B_TABLES & restored.tables()))
        restored2 = self.restore(self.p2_result["backup"], "p2_restored")
        self.verify("P5d", "B-029", "The backup taken for the successful upgrade also restores to the pre-upgrade data",
                    self.core(restored2) == self.p2_before)

    def p6_restart(self):
        before = {n: self.fingerprint(getattr(self, n)) for n in ("p1", "p2")}
        self.command(["docker", "restart", self.container])
        self.wait_ready()
        after = {n: self.fingerprint(getattr(self, n)) for n in ("p1", "p2")}
        self.verify("P6", "B-029", "After restarting the MySQL container every upgraded database is byte-identical and still classified 'challenge_b'",
                    before == after and self.p1.classify() == "challenge_b" and self.p2.classify() == "challenge_b")

    def wait_ready(self):
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            r = self.command(["docker", "exec", self.container, "sh", "-c",
                              'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -h127.0.0.1 --protocol=TCP -uroot -N -e "SELECT 1"'], check=False)
            if r.returncode == 0 and r.stdout.strip() == b"1":
                return
            time.sleep(1)
        raise TimeoutError("MySQL did not come back after restart")

    def save(self):
        self.report["tool_results"] = self.results
        super().save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="mysql:8.0.46")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/test/evidence/r5-challenge-b-db/b029-results.json")
    args = parser.parse_args()
    run = B029(args)
    fatal = None
    try:
        run.start()
        run.fresh_reference()
        for name in ("p1_legacy", "p2_auction_data", "p2b_from_iteration2", "p3_repeat", "p4_interrupted",
                     "p5_abnormal_and_restore", "p6_restart"):
            try:
                getattr(run, name)()
            except Exception as exc:
                run.report["scenario_errors"].append({"scenario": name, "error": str(exc)[:500]})
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
        shutil.rmtree(run.backups, ignore_errors=True)
        run.save()
    summary = run.report["summary"]
    return 1 if fatal or summary["fail"] or run.report["scenario_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
