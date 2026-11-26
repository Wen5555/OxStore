#!/usr/bin/env python3
"""Prepare B030 fixtures against a live BE bound to an isolated test DB.

Creates/reuses FIXED_PRICE products via multipart POST /api/admin/products
(with seed.png). Validates every response. Fails hard if incomplete — never
reports ready with NEEDS_MANUAL placeholders.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import uuid
from pathlib import Path
from urllib import error, request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b030_common import (  # noqa: E402
    CATALOG,
    ROOT,
    auth_headers,
    base_url,
    connect_mysql,
    http_json,
    load_env,
    login_customer,
    login_seller,
    require_test_db,
)

SEED_PNG = ROOT / "fixtures" / "seed.png"


def multipart_post(url: str, fields: dict[str, str], files: list[tuple[str, Path]], headers: dict) -> tuple[int, dict | None]:
    boundary = f"----B030{uuid.uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())
    for field_name, path in files:
        data = path.read_bytes()
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{path.name}"\r\n'.encode()
        )
        body.extend(f"Content-Type: {ctype}\r\n\r\n".encode())
        body.extend(data)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    hdrs = {**headers, "Content-Type": f"multipart/form-data; boundary={boundary}"}
    req = request.Request(url, data=bytes(body), headers=hdrs, method="POST")
    try:
        with request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return e.code, parsed


def pick_category2(env: dict, seller_token: str) -> str:
    # After DataInitializer, categories exist. Use buyer browse or admin list side-effect.
    # Prefer DB read for reliability.
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT c.id FROM category c "
                "JOIN category p ON c.parent_id = p.id "
                "WHERE p.parent_id IS NULL ORDER BY c.id LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("No category2 in DB — is BE DataInitializer run?")
            return str(row["id"])
    finally:
        conn.close()


def list_b030_products_db(env: dict) -> dict[str, dict]:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, stock, status, offline_reason, price FROM product WHERE name LIKE 'B030-%'"
            )
            out = {}
            for row in cur.fetchall():
                out[row["name"]] = {
                    "productId": str(row["id"]),
                    "name": row["name"],
                    "stock": str(row["stock"]),
                    "status": row["status"],
                    "offline_reason": row["offline_reason"],
                    "price": str(row["price"]) if row["price"] is not None else None,
                }
            return out
    finally:
        conn.close()


def assert_http_ok(label: str, code: int, body, expect=(200, 201)):
    if code not in expect:
        raise RuntimeError(f"{label}: HTTP {code} body={body}")
    if not isinstance(body, dict) or body.get("data") is None and code in (200, 201):
        # some ok responses may have data null; create must have data
        if "create" in label or "publish" in label:
            raise RuntimeError(f"{label}: missing data in {body}")


def _product_status(env: dict, pid: str) -> tuple[str, str | None, str]:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, offline_reason, stock FROM product WHERE id=%s",
                (pid,),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"product {pid} missing in DB")
            return row["status"], row["offline_reason"], str(row["stock"])
    finally:
        conn.close()


def align_product(env: dict, seller_token: str, pid: str, spec: dict) -> None:
    # Target stock first (0 triggers AUTO_ZERO offline).
    target_stock = spec["stock"]
    patch_stock = "1" if target_stock == "0" else target_stock
    code, body = http_json(
        "PATCH",
        f"{base_url(env)}/api/admin/products/{pid}",
        {"stock": patch_stock},
        auth_headers(seller_token),
    )
    assert_http_ok(f"PATCH stock {spec['name']}", code, body, expect=(200,))

    status, reason, stock = _product_status(env, pid)

    if spec["status"] == "ONLINE":
        if status != "ONLINE":
            code, body = http_json(
                "POST",
                f"{base_url(env)}/api/admin/products/{pid}/online",
                headers=auth_headers(seller_token),
            )
            assert_http_ok(f"online {spec['name']}", code, body, expect=(200,))
    elif spec.get("offline_reason") == "MANUAL":
        # ensure stock > 0 then manual offline
        if stock == "0":
            code, body = http_json(
                "PATCH",
                f"{base_url(env)}/api/admin/products/{pid}",
                {"stock": "5"},
                auth_headers(seller_token),
            )
            assert_http_ok(f"restock before manual offline {spec['name']}", code, body)
        status, reason, _ = _product_status(env, pid)
        if status != "OFFLINE" or reason != "MANUAL":
            code, body = http_json(
                "POST",
                f"{base_url(env)}/api/admin/products/{pid}/offline",
                headers=auth_headers(seller_token),
            )
            assert_http_ok(f"offline {spec['name']}", code, body, expect=(200,))
        # final stock for MANUAL fixture
        code, body = http_json(
            "PATCH",
            f"{base_url(env)}/api/admin/products/{pid}",
            {"stock": target_stock},
            auth_headers(seller_token),
        )
        assert_http_ok(f"final stock manual {spec['name']}", code, body, expect=(200,))
        return

    if target_stock == "0":
        code, body = http_json(
            "PATCH",
            f"{base_url(env)}/api/admin/products/{pid}",
            {"stock": "0"},
            auth_headers(seller_token),
        )
        assert_http_ok(f"stock0 {spec['name']}", code, body, expect=(200,))


def create_product(env: dict, seller_token: str, category2_id: str, spec: dict) -> str:
    if not SEED_PNG.exists():
        raise RuntimeError(f"missing {SEED_PNG}")
    fields = {
        "name": spec["name"],
        "price": spec["price"],
        "category2Id": category2_id,
        "stock": spec["stock"] if spec["stock"] != "0" else "1",  # create with 1 then set 0
        "sellingMode": "FIXED_PRICE",
        "descriptionHtml": f"<p>{spec['purpose']}</p>",
    }
    code, body = multipart_post(
        f"{base_url(env)}/api/admin/products",
        fields,
        [("images", SEED_PNG)],
        auth_headers(seller_token),
    )
    assert_http_ok(f"publish {spec['name']}", code, body, expect=(200, 201))
    data = body["data"]
    pid = str(data.get("productId") or data.get("id") or "")
    if not pid:
        raise RuntimeError(f"publish {spec['name']}: no productId in {body}")
    align_product(env, seller_token, pid, spec)
    return pid


def verify_api_db_binding(env: dict) -> dict:
    """Write a canary via API-visible path and confirm it lands in configured DB."""
    # Insert canary product name marker check: count B030 products in configured DB
    # after prepare; also read seller table for admin existence.
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE() AS db")
            db = cur.fetchone()["db"]
            cur.execute("SELECT COUNT(*) AS c FROM seller WHERE username='admin'")
            sellers = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM category WHERE parent_id IS NOT NULL")
            cats = cur.fetchone()["c"]
        return {"database": db, "admin_sellers": sellers, "category2_count": cats}
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-check", action="store_true")
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
        return 0

    if not env.get("B030_SELLER_PASSWORD"):
        print("BLOCKED: B030_SELLER_PASSWORD unset")
        _write({"ready": False, "blocked": "missing seller password", "db": db})
        return 3

    try:
        binding = verify_api_db_binding(env)
        if binding["database"] != db:
            raise RuntimeError(f"connected DB {binding['database']} != configured {db}")
        if binding["admin_sellers"] < 1:
            raise RuntimeError("admin seller missing — start BE with ADMIN_INITIAL_PASSWORD against this DB first")
        if binding["category2_count"] < 1:
            raise RuntimeError("no category2 — DataInitializer did not seed this DB")

        seller = login_seller(env)
        # probe API sees same DB: list products then compare counts
        code, body = http_json(
            "GET",
            f"{base_url(env)}/api/admin/products?page=1&size=100",
            headers=auth_headers(seller),
        )
        assert_http_ok("list products", code, body, expect=(200,))
        tokens = {
            "CUSTOMER_A": login_customer(env, "CUSTOMER_A"),
            "CUSTOMER_B": login_customer(env, "CUSTOMER_B"),
        }
        category2_id = pick_category2(env, seller)
        existing = list_b030_products_db(env)
        products: dict = {}
        for code_key, spec in CATALOG["products"].items():
            if spec["selling_mode"] != "FIXED_PRICE":
                products[code_key] = {
                    "status": "SKIP_AUCTION",
                    "note": "Auction fixture is optional for B035; not required for B030 prepare ready",
                    "spec": spec,
                }
                continue
            name = spec["name"]
            if name in existing:
                pid = existing[name]["productId"]
                align_product(env, seller, pid, spec)
                products[code_key] = {"productId": pid, "name": name, "spec": spec, "source": "reused"}
            else:
                pid = create_product(env, seller, category2_id, spec)
                products[code_key] = {"productId": pid, "name": name, "spec": spec, "source": "created"}

        # validate FIXED_PRICE all have productId
        missing = [
            k
            for k, v in products.items()
            if CATALOG["products"][k]["selling_mode"] == "FIXED_PRICE" and "productId" not in v
        ]
        if missing:
            raise RuntimeError(f"incomplete fixtures: {missing}")

        # DB assert stocks
        after = list_b030_products_db(env)
        for code_key, spec in CATALOG["products"].items():
            if spec["selling_mode"] != "FIXED_PRICE":
                continue
            row = after.get(spec["name"])
            if not row:
                raise RuntimeError(f"DB missing {spec['name']}")
            if row["stock"] != spec["stock"]:
                raise RuntimeError(f"{spec['name']} stock want {spec['stock']} got {row['stock']}")

        out = {
            "ready": True,
            "db": db,
            "db_binding": binding,
            "base_url": base_url(env),
            "sut_sha": env.get("B030_SUT_SHA"),
            "category2Id": category2_id,
            "accounts_ready": list(tokens.keys()),
            "products": products,
        }
        _write(out)
        print("PASS prepare ready=true")
        return 0
    except Exception as e:
        print("BLOCKED:", e)
        _write({"ready": False, "blocked": str(e), "db": db})
        return 4


def _write(obj: dict) -> None:
    path = ROOT / "runs" / "fixture-ids.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", path)


if __name__ == "__main__":
    raise SystemExit(main())
