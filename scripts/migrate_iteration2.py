"""Backup-first V4/V5 upgrade for an explicitly selected Docker MySQL database.

Stop application writes first. The container must expose MYSQL_ROOT_PASSWORD to
its mysql client. Backups contain private data and default to the ignored .work/.
V4 is run only for the recognized five-table legacy layout; partial upgrades
are refused. A second invocation skips V4 and safely reapplies idempotent V5.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "backend/src/main/resources/db/migrations"
TABLES = {"seller", "customer", "category", "product", "product_image",
          "purchase_intent", "trade_attempt", "order_history", "product_status_event"}
LEGACY_TABLES = {"seller", "product", "purchase_intent", "trade_attempt", "product_status_event"}
ITERATION2_COLUMNS = {
    "product": {"stock", "category2_id"},
    "customer": {"username", "password_hash", "phone", "location", "registered_at"},
    "category": {"id", "parent_id", "name"},
    "product_image": {"product_id", "image_path", "sort_order"},
    "purchase_intent": {"customer_id", "product_name_snapshot", "queue_seq", "trading_product_id"},
    "order_history": {"intent_id", "customer_id", "product_name_snapshot", "submitted_at", "status", "transacted_at"},
}


class DockerMySQL:
    def __init__(self, container: str, database: str):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", container):
            raise ValueError("Invalid Docker container name")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", database) or database.lower() in {
            "mysql", "sys", "information_schema", "performance_schema"
        }:
            raise ValueError("Select an explicit non-system database")
        self.container, self.database = container, database

    def client(self, executable="mysql", options=(), payload=None, check=True):
        command = ['MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec ' + executable,
                   "-uroot", "--default-character-set=utf8mb4", *options, self.database]
        # Every variable substituted into this shell command is validated above;
        # SQL/data travels only over stdin, never through command interpolation.
        result = subprocess.run(["docker", "exec", "-i", self.container, "sh", "-c", " ".join(command)],
                                input=payload, capture_output=True, timeout=120)
        if check and result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace")[-1200:])
        return result

    def sql(self, statement, check=True):
        return self.client(options=("--batch", "--skip-column-names"),
                           payload=("SET NAMES utf8mb4;\n" + statement).encode("utf-8"), check=check)

    def query(self, statement):
        return self.sql(statement).stdout.decode("utf-8").strip()

    def tables(self):
        return set(filter(None, self.query("SHOW TABLES").splitlines()))

    def columns(self, table):
        if table not in TABLES:
            raise ValueError("Unknown application table")
        return set(self.query(f"SELECT column_name FROM information_schema.columns "
                              f"WHERE table_schema=DATABASE() AND table_name='{table}'").splitlines())

    def dump(self):
        return self.client("mysqldump", ("--single-transaction", "--routines", "--triggers",
                           "--no-tablespaces", "--set-gtid-purged=OFF", "--hex-blob")).stdout

    def upgrade(self, backup_dir: Path):
        tables = self.tables()
        columns = self.columns("product")
        if tables == LEGACY_TABLES and {"active_flag", "image_path"} <= columns:
            phase = "legacy"
        elif tables == TABLES and all(required <= self.columns(table)
                                     for table, required in ITERATION2_COLUMNS.items()):
            phase = "iteration2"
        else:
            raise RuntimeError("Unrecognized/partial schema; inspect it and restore the verified backup before retrying")
        if self.query("SELECT COUNT(*) FROM purchase_intent WHERE status='IN_TRANSACTION'") != "0":
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
                  "backup_sha256": hashlib.sha256(data).hexdigest(), "applied": []}
        if phase == "legacy":
            name = "V4__iteration2_customer_inventory_catalog.sql"
            self.sql((MIGRATIONS / name).read_text(encoding="utf-8"))
            result["applied"].append("V4")
        name = "V5__iteration2_database_contract.sql"
        self.sql((MIGRATIONS / name).read_text(encoding="utf-8"))
        result["applied"].append("V5")
        if self.tables() != TABLES or not {"content_type", "size_bytes"} <= self.columns("product_image"):
            raise RuntimeError("Post-upgrade schema is incomplete; keep the backup and inspect before restarting")
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--backup-dir", type=Path, default=ROOT / ".work/db-backups")
    args = parser.parse_args()
    try:
        print(json.dumps(DockerMySQL(args.container, args.database).upgrade(args.backup_dir),
                         ensure_ascii=False, indent=2))
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Upgrade stopped: {error}\n")


if __name__ == "__main__":
    main()
