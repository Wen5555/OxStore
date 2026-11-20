#!/usr/bin/env python3
"""Install B-032 TX probe tables/triggers into the isolated test DB (sudo mysql)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b032_common import load_env, require_db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "fixtures" / "b032_tx_probes.sql"


def main() -> int:
    env = load_env()
    db = require_db(env["B032_DB_NAME"])
    sql = SQL.read_text(encoding="utf-8")
    # Strip DELIMITER directives for mysql CLI client mode that still needs them via sudo mysql
    proc = subprocess.run(
        ["sudo", "mysql", db],
        input=sql,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit(f"install_tx_probes failed for {db}: {proc.returncode}")
    print(f"installed TX probes into {db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
