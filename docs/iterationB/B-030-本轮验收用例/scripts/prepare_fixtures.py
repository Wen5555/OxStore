#!/usr/bin/env python3
"""Prepare B030 namespace accounts + FIXED_PRICE products via real APIs.

Usage:
  B030_DB_NAME=oxstore_b030_local B030_SELLER_PASSWORD=... \\
    python3 prepare_fixtures.py [--dry-check]

Writes runs/fixture-ids.json with resolved productId / customer usernames.
Never touches products whose name does not start with B030-.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b030_common import (  # noqa: E402
    CATALOG,
    ROOT,
    auth_headers,
    base_url,
    http_json,
    load_env,
    login_customer,
    login_seller,
    require_test_db,
)


def ensure_customers(env: dict) -> dict[str, str]:
    tokens = {}
    for key in ("CUSTOMER_A", "CUSTOMER_B"):
        tokens[key] = login_customer(env, key)
    return tokens


def find_or_create_products(env: dict, seller_token: str) -> dict[str, str]:
    """Create FIXED_PRICE fixtures via admin API when possible; else record SQL seed hints."""
    # List existing admin products and reuse B030- names.
    code, body = http_json(
        "GET",
        f"{base_url(env)}/api/admin/products?page=1&size=100",
        headers=auth_headers(seller_token),
    )
    existing: dict[str, str] = {}
    if code == 200 and isinstance(body, dict):
        content = body.get("data", {}).get("content") or body.get("data", {}).get("items") or []
        if isinstance(body.get("data"), list):
            content = body["data"]
        for row in content or []:
            name = row.get("name") or row.get("title")
            pid = str(row.get("id") or row.get("productId") or "")
            if name and str(name).startswith("B030-") and pid:
                existing[str(name)] = pid

    resolved: dict[str, dict] = {}
    for code_key, spec in CATALOG["products"].items():
        if spec["selling_mode"] != "FIXED_PRICE":
            resolved[code_key] = {
                "status": "SKIP_AUCTION_MANUAL",
                "note": "拍卖商品需按拍卖发布流单独创建；B035 回归用",
                "spec": spec,
            }
            continue
        name = spec["name"]
        if name in existing:
            pid = existing[name]
            # Align stock/status
            http_json(
                "PATCH",
                f"{base_url(env)}/api/admin/products/{pid}",
                {"stock": spec["stock"]},
                headers=auth_headers(seller_token),
            )
            if spec["status"] == "OFFLINE" and spec.get("offline_reason") == "MANUAL":
                http_json(
                    "POST",
                    f"{base_url(env)}/api/admin/products/{pid}/offline",
                    headers=auth_headers(seller_token),
                )
            elif spec["status"] == "ONLINE":
                http_json(
                    "POST",
                    f"{base_url(env)}/api/admin/products/{pid}/online",
                    headers=auth_headers(seller_token),
                )
            resolved[code_key] = {"productId": pid, "name": name, "spec": spec, "source": "reused"}
            continue
        # Create — multipart form varies by env; record SQL fallback if create endpoint needs images.
        create = http_json(
            "POST",
            f"{base_url(env)}/api/admin/products",
            None,
            headers=auth_headers(seller_token),
        )
        resolved[code_key] = {
            "status": "NEEDS_MANUAL_OR_SQL_SEED",
            "name": name,
            "spec": spec,
            "hint": (
                "若 multipart 发布接口需要图片/类目，请用商家后台创建同名商品，"
                "或在允许的测试库执行 fixtures/sql/seed_products.sql 后重跑。"
            ),
            "probe_create_http": create[0],
        }
    return resolved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-check", action="store_true", help="Only validate env/DB name; no writes")
    args = ap.parse_args()
    env = load_env()
    db = env.get("B030_DB_NAME", "")
    try:
        require_test_db(db)
    except SystemExit as e:
        print("BLOCKED:", e)
        return 2
    print(f"DB OK: {db}")
    print(f"BASE: {base_url(env)}")
    print(f"SUT_SHA: {env.get('B030_SUT_SHA') or '(unset)'}")
    if args.dry_check:
        print("dry-check only; no API writes")
        return 0
    if not env.get("B030_SELLER_PASSWORD"):
        print("BLOCKED: B030_SELLER_PASSWORD unset — cannot prepare via API")
        (ROOT / "runs" / "fixture-ids.json").write_text(
            json.dumps({"blocked": "missing seller password", "db": db}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return 3
    try:
        seller = login_seller(env)
        tokens = ensure_customers(env)
        products = find_or_create_products(env, seller)
    except Exception as e:
        print("BLOCKED:", e)
        (ROOT / "runs" / "fixture-ids.json").write_text(
            json.dumps({"blocked": str(e), "db": db}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return 4
    out = {
        "db": db,
        "base_url": base_url(env),
        "sut_sha": env.get("B030_SUT_SHA"),
        "accounts_ready": list(tokens.keys()),
        "products": products,
    }
    path = ROOT / "runs" / "fixture-ids.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", path)
    missing = [k for k, v in products.items() if "productId" not in v]
    if missing:
        print("PARTIAL: products still needing seed:", ", ".join(missing))
        return 5
    print("PASS prepare")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
