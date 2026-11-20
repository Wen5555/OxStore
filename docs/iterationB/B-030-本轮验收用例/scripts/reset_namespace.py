#!/usr/bin/env python3
"""Reset B030 namespace data for a case (or all B030 rows).

Safety gates:
- DB name must match oxstore_b030_* / oxstore_test_*
- Only deletes rows tied to B030- product names or b030_ usernames
- Never DROP DATABASE / TRUNCATE whole tables
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b030_common import connect_mysql, load_env, require_test_db  # noqa: E402


SQL_RESET = r"""
-- Resolve B030 customers and products
SET @ns := 'B030';

DELETE oi FROM order_item oi
  JOIN shop_order so ON so.id = oi.order_id
  JOIN customer c ON c.id = so.customer_id
 WHERE c.username LIKE 'b030\_%';

DELETE so FROM shop_order so
  JOIN customer c ON c.id = so.customer_id
 WHERE c.username LIKE 'b030\_%';

DELETE ci FROM cart_item ci
  JOIN customer c ON c.id = ci.customer_id
 WHERE c.username LIKE 'b030\_%';

DELETE t FROM cart_item_tombstone t
  JOIN customer c ON c.id = t.customer_id
 WHERE c.username LIKE 'b030\_%';

DELETE f FROM favorite f
  JOIN customer c ON c.id = f.customer_id
 WHERE c.username LIKE 'b030\_%';

DELETE fm FROM favorite_mutation fm
  JOIN customer c ON c.id = fm.customer_id
 WHERE c.username LIKE 'b030\_%';

DELETE cc FROM checkout_confirmation cc
  JOIN customer c ON c.id = cc.customer_id
 WHERE c.username LIKE 'b030\_%';

DELETE r FROM operation_receipt r
  JOIN customer c ON c.id = r.customer_id
 WHERE c.username LIKE 'b030\_%';

-- Restore product fixtures by name (stock/status from catalog applied by prepare)
UPDATE product SET stock = '10', status = 'ONLINE', offline_reason = NULL
 WHERE name = 'B030-在售足库存-10';
UPDATE product SET stock = '5', status = 'ONLINE', offline_reason = NULL
 WHERE name = 'B030-在售足库存-5';
UPDATE product SET stock = '1', status = 'ONLINE', offline_reason = NULL
 WHERE name = 'B030-低库存-1';
UPDATE product SET stock = '0', status = 'OFFLINE', offline_reason = 'AUTO_ZERO'
 WHERE name = 'B030-零库存自动下架';
UPDATE product SET stock = '5', status = 'OFFLINE', offline_reason = 'MANUAL'
 WHERE name = 'B030-人工下架-库存5';
UPDATE product SET stock = '9007199254740993', status = 'ONLINE', offline_reason = NULL
 WHERE name = 'B030-大整数库存';
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-id", default="", help="Recorded in runs for audit; filter reserved")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    env = load_env()
    try:
        require_test_db(env.get("B030_DB_NAME", ""))
    except SystemExit as e:
        print("BLOCKED:", e)
        return 2
    if args.dry_run:
        print("Would execute namespace reset SQL on", env["B030_DB_NAME"], "case=", args.case_id or "*")
        print(SQL_RESET[:400], "...")
        return 0
    try:
        conn = connect_mysql(env)
    except SystemExit as e:
        print("BLOCKED:", e)
        return 2
    except Exception as e:
        print("BLOCKED: cannot connect MySQL:", e)
        return 3
    try:
        with conn.cursor() as cur:
            for stmt in [s.strip() for s in SQL_RESET.split(";") if s.strip() and not s.strip().startswith("--")]:
                if stmt.upper().startswith("SET "):
                    cur.execute(stmt)
                    continue
                cur.execute(stmt)
                print(f"ok rows={cur.rowcount}: {stmt.split()[0:4]}")
    finally:
        conn.close()
    print("PASS reset", args.case_id or "ALL_B030")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
