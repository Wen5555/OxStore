#!/usr/bin/env python3
"""Prove the live API is bound to the configured isolated test DB.

Method: create a uniquely named product via API, then SELECT it from B030_DB_NAME.
Fail if missing or if DATABASE() != B030_DB_NAME.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b030_common import (  # noqa: E402
    ROOT,
    auth_headers,
    base_url,
    connect_mysql,
    load_env,
    login_seller,
    require_test_db,
)
from prepare_fixtures import SEED_PNG, multipart_post, pick_category2  # noqa: E402


def main() -> int:
    env = load_env()
    db = require_test_db(env.get("B030_DB_NAME", ""))
    seller = login_seller(env)
    cat = pick_category2(env, seller)
    name = f"B030-CANARY-{uuid.uuid4().hex[:8]}"
    code, body = multipart_post(
        f"{base_url(env)}/api/admin/products",
        {
            "name": name,
            "price": "1.00",
            "category2Id": cat,
            "stock": "1",
            "sellingMode": "FIXED_PRICE",
            "descriptionHtml": "<p>canary</p>",
        },
        [("images", SEED_PNG)],
        auth_headers(seller),
    )
    if code not in (200, 201):
        print("FAIL API create", code, body)
        return 1
    pid = str(body["data"].get("productId") or body["data"].get("id"))
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE() AS db")
            got_db = cur.fetchone()["db"]
            cur.execute("SELECT id, name FROM product WHERE id=%s", (pid,))
            row = cur.fetchone()
    finally:
        conn.close()
    report = {
        "configured_db": db,
        "connection_database": got_db,
        "api_product_id": pid,
        "api_product_name": name,
        "row_in_db": row,
        "ok": got_db == db and row is not None and row["name"] == name,
        "sut_sha": env.get("B030_SUT_SHA"),
        "base_url": base_url(env),
        "ts": time.time(),
    }
    out = ROOT / "runs" / "verify-api-db.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
