"""Backup-first upgrade of an explicitly selected Docker MySQL database to the challenge-B schema (V7 + V8).

Stop application writes first. The container must expose MYSQL_ROOT_PASSWORD to its mysql client (the stock
mysql image does). The database is classified before anything runs; an unrecognised or partial layout is refused
with no change. A verified, non-empty backup is written first (it contains private data and defaults to the
ignored .work/). DDL commits implicitly, so a failure is never rolled back automatically: keep the backup,
inspect, and restore it into a scratch database before retrying.

  legacy      (iteration 1, 5 tables)        -> V4, V5, V6, V7, V8
  iteration2  (9 tables)                     -> V5, V6, V7, V8
  auction     (12 tables, after V6)          -> V7, V8
  challenge_b (21 tables, already upgraded)  -> V7, V8 again (both are repeatable and change nothing)

V8 closes the legacy fixed-price intent flow without rewriting any intent status; it stops by itself with a
message when it meets data it must not guess about (see backend/src/main/resources/db/migrations/V8__*.sql).
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import uuid

from migrate_iteration2 import (AUCTION_COLUMNS, DockerMySQL, ITERATION2_COLUMNS, ITERATION2_TABLES, LEGACY_TABLES,
                                MIGRATION_FILES, MIGRATIONS, ROOT, TABLES)

CHALLENGE_B_TABLES = {"shop_order", "order_item", "favorite", "favorite_mutation", "cart_item", "cart_item_tombstone",
                      "checkout_confirmation", "checkout_confirmation_item", "operation_receipt"}
ALL_TABLES = TABLES | CHALLENGE_B_TABLES
CHALLENGE_B_COLUMNS = {
    "product": {"offline_reason"},
    "purchase_intent": {"legacy_closed_at", "legacy_close_reason"},
    "trade_attempt": {"legacy_closed_at"},
    "shop_order": {"order_no", "status", "total_amount", "cancelled_by", "cancelled_at"},
    "operation_receipt": {"customer_id", "operation_type", "request_key", "request_hash", "result_payload"},
}
FILES = dict(MIGRATION_FILES, V7="V7__challenge_b_order_cart_favorite.sql", V8="V8__close_legacy_fixed_price_intents.sql")
PLAN = {"legacy": ["V4", "V5", "V6", "V7", "V8"], "iteration2": ["V5", "V6", "V7", "V8"],
        "auction": ["V7", "V8"], "challenge_b": ["V7", "V8"]}


class ChallengeBUpgrade(DockerMySQL):
    def columns_of(self, table):
        return set(self.query(f"SELECT column_name FROM information_schema.columns "
                              f"WHERE table_schema=DATABASE() AND table_name='{table}'").splitlines())

    def has(self, expected):
        return all(required <= self.columns_of(table) for table, required in expected.items())

    def classify(self):
        tables = self.tables()
        if tables == LEGACY_TABLES and {"active_flag", "image_path"} <= self.columns_of("product"):
            return "legacy"
        if tables == ITERATION2_TABLES and self.has(ITERATION2_COLUMNS):
            return "iteration2"
        if tables == TABLES and self.has(ITERATION2_COLUMNS) and self.has(AUCTION_COLUMNS):
            return "auction"
        if tables == ALL_TABLES and self.has(ITERATION2_COLUMNS) and self.has(AUCTION_COLUMNS) and self.has(CHALLENGE_B_COLUMNS):
            return "challenge_b"
        raise RuntimeError("Unrecognised or partial schema (tables: %s); inspect it and restore a verified backup "
                           "into a scratch database instead of forcing a migration" % ", ".join(sorted(tables)))

    def upgrade_to_challenge_b(self, backup_dir: Path):
        phase = self.classify()
        if phase == "legacy" and self.query("SELECT COUNT(*) FROM purchase_intent WHERE status='IN_TRANSACTION'") != "0":
            raise RuntimeError("Finish all in-progress trades and stop application writes before upgrading")
        backup_dir = backup_dir.resolve()
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"{self.database}-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.sql"
        data = self.dump()
        if not data:
            raise RuntimeError("Backup was empty; no migration executed")
        with backup.open("xb") as stream:
            stream.write(data)
        result = {"database": self.database, "phase_before": phase, "backup": str(backup),
                  "backup_bytes": len(data), "backup_sha256": hashlib.sha256(data).hexdigest(), "applied": [],
                  "v8_counts": None}
        for version in PLAN[phase]:
            try:
                out = self.sql((MIGRATIONS / FILES[version]).read_text(encoding="utf-8"))
            except RuntimeError as error:
                result["failed_at"] = version
                result["error"] = str(error).strip()[-600:]
                result["recovery"] = (f"Stop writes, keep {backup}, restore it into a scratch database to compare, "
                                      f"fix the reported data and re-run. DDL already applied is not rolled back.")
                raise UpgradeFailed(result) from error
            result["applied"].append(version)
            if version == "V8":
                counts = out.stdout.decode("utf-8", errors="replace").split()
                if len(counts) == 4:
                    result["v8_counts"] = dict(zip(("closed_intents", "closed_attempts", "unfrozen_products", "paused_products"),
                                                   map(int, counts)))
        if self.classify() != "challenge_b":
            raise UpgradeFailed(dict(result, error="Post-upgrade schema is not the challenge-B layout; keep the backup"))
        result["phase_after"] = "challenge_b"
        return result


class UpgradeFailed(RuntimeError):
    def __init__(self, result):
        super().__init__(json.dumps(result, ensure_ascii=False))
        self.result = result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--container", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--backup-dir", type=Path, default=ROOT / ".work/db-backups")
    args = parser.parse_args()
    try:
        print(json.dumps(ChallengeBUpgrade(args.container, args.database).upgrade_to_challenge_b(args.backup_dir),
                         ensure_ascii=False, indent=2))
    except UpgradeFailed as error:
        print(json.dumps(error.result, ensure_ascii=False, indent=2))
        parser.exit(1, "Upgrade stopped; see the JSON above. The backup was kept.\n")
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Upgrade refused: {error}\n")


if __name__ == "__main__":
    main()
