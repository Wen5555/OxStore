#!/usr/bin/env python3
"""Shared helpers for B-033 (five-state / cancellation / restock) acceptance execution.

Reuses the B-030 fixture/HTTP/DB contract (scripts/b030_common.py, helpers_lib.py)
so B-033 executes the plan written by B-030 instead of re-deriving fixtures.

Safety:
- DB name must start with oxstore_b030_* / oxstore_test_* (enforced by b030_common).
- reset only touches b030_* customer rows and B030-* fixture products.
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

B033_ROOT = Path(__file__).resolve().parents[1]
B030_ROOT = next(p for p in B033_ROOT.parent.iterdir() if p.name.startswith("B-030-"))

sys.path.insert(0, str(B030_ROOT / "scripts"))
sys.path.insert(0, str(B033_ROOT / "scripts"))

from b030_common import (  # noqa: E402
    auth_headers,
    base_url,
    connect_mysql,
    http_json,
    load_env as b030_load_env,
    login_customer,
    login_seller,
)
from helpers_lib import cart_add, product_id  # noqa: E402
import reset_namespace  # noqa: E402

CST = timezone(timedelta(hours=8))
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
NAMESPACE_LIKE = "b030\\_%"


def load_b034_env() -> dict[str, str]:
    """B-034 env: its own runs/.env.local first, then B-030 runs/.env.local."""
    local = B033_ROOT / "runs" / ".env.local"
    if local.exists():
        for line in local.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            import os

            os.environ.setdefault(k.strip(), v.strip())
    return b030_load_env()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_cst() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def redact(value: Any) -> Any:
    """Strip bearer tokens / JWT strings from saved evidence."""
    if isinstance(value, str):
        return JWT_RE.sub("<jwt-redacted>", value)
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    return value


def jwt() -> str:
    return str(uuid.uuid4())


_FIXED = {
    "P-ON-10": {"stock": "10", "status": "ONLINE"},
    "P-ON-5": {"stock": "5", "status": "ONLINE"},
    "P-ON-1": {"stock": "1", "status": "ONLINE"},
    "P-OFF-M": {"stock": "5", "status": "OFFLINE"},
}


def reset(env: dict) -> None:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            for raw in reset_namespace.SQL_RESET.split(";"):
                # B-030's splitter skips any chunk whose first line is a comment, which
                # silently dropped the product-restore UPDATEs; strip comment lines first.
                cleaned = "\n".join(
                    ln for ln in raw.splitlines() if not ln.strip().startswith("--")
                ).strip()
                if cleaned:
                    cur.execute(cleaned)
    finally:
        conn.close()


def query(env: dict, sql: str, args: tuple = ()) -> list[dict]:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args if args else None)
            return list(cur.fetchall())
    finally:
        conn.close()


def execute(env: dict, sql: str, args: tuple = ()) -> int:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args if args else None)
            return cur.rowcount
    finally:
        conn.close()


def counts(env: dict) -> dict:
    row = query(
        env,
        """
        SELECT
          (SELECT COUNT(*) FROM cart_item ci JOIN customer c ON c.id=ci.customer_id
             WHERE c.username LIKE %s) AS cart,
          (SELECT COUNT(*) FROM favorite f JOIN customer c ON c.id=f.customer_id
             WHERE c.username LIKE %s) AS favorites,
          (SELECT COUNT(*) FROM shop_order so JOIN customer c ON c.id=so.customer_id
             WHERE c.username LIKE %s) AS orders,
          (SELECT COUNT(*) FROM cart_item_tombstone t JOIN customer c ON c.id=t.customer_id
             WHERE c.username LIKE %s) AS tombstones,
          (SELECT COUNT(*) FROM operation_receipt r JOIN customer c ON c.id=r.customer_id
             WHERE c.username LIKE %s) AS receipts
        """,
        (NAMESPACE_LIKE,) * 5,
    )[0]
    return {k: int(v) for k, v in row.items()}


def product_snapshot(env: dict) -> dict[str, dict]:
    rows = query(
        env,
        "SELECT name, stock, status, offline_reason FROM product WHERE name LIKE 'B030-%' ORDER BY name",
    )
    return {r["name"]: {"stock": str(r["stock"]), "status": r["status"],
                        "offline_reason": r["offline_reason"]} for r in rows}


def cart_rows(env: dict) -> list[dict]:
    return query(
        env,
        """
        SELECT ci.id, c.username, ci.product_id, p.name AS product_name, ci.quantity
          FROM cart_item ci
          JOIN customer c ON c.id=ci.customer_id
          JOIN product p ON p.id=ci.product_id
         WHERE c.username LIKE %s
         ORDER BY ci.id
        """,
        (NAMESPACE_LIKE,),
    )


def favorite_rows(env: dict) -> list[dict]:
    return query(
        env,
        """
        SELECT f.id, c.username, f.product_id, p.name AS product_name, f.created_at
          FROM favorite f
          JOIN customer c ON c.id=f.customer_id
          JOIN product p ON p.id=f.product_id
         WHERE c.username LIKE %s
         ORDER BY f.id
        """,
        (NAMESPACE_LIKE,),
    )


def move_receipts(env: dict) -> int:
    """MOVE_TO_FAVORITES receipts only; cart-add uses the same table for CART_ADD."""
    row = query(
        env,
        """
        SELECT COUNT(*) AS c FROM operation_receipt r
          JOIN customer c2 ON c2.id=r.customer_id
         WHERE c2.username LIKE %s AND r.operation_type='MOVE_TO_FAVORITES'
        """,
        (NAMESPACE_LIKE,),
    )[0]
    return int(row["c"])


def move(env: dict, token: str, cart_item_ids: list[str], key: str | None = None):
    key = key or jwt()
    http, body = http_json(
        "POST",
        f"{base_url(env)}/api/me/cart/move-to-favorites",
        {"cartItemIds": cart_item_ids},
        auth_headers(token, key),
    )
    return {"http": http, "body": body, "idempotencyKey": key}


def add_line(env: dict, token: str, product: str, qty: str = "1") -> str:
    return cart_add(env, token, product, qty)["cartItemId"]


def delete_line(env: dict, token: str, cart_item_id: str):
    return http_json(
        "DELETE", f"{base_url(env)}/api/me/cart/items/{cart_item_id}", headers=auth_headers(token)
    )


def set_stock(env: dict, seller: str, code: str, stock: str):
    pid = product_id(code)
    return http_json(
        "PATCH",
        f"{base_url(env)}/api/admin/products/{pid}",
        {"stock": stock},
        auth_headers(seller),
    )


def offline_product(env: dict, seller: str, code: str):
    pid = product_id(code)
    return http_json(
        "POST",
        f"{base_url(env)}/api/admin/products/{pid}/offline",
        headers=auth_headers(seller),
    )


def insert_missing_product_cart_row(env: dict, token: str, code: str = "P-ON-10") -> str:
    """Create a cart row whose product_id no longer exists.

    The product model has no hard delete, so a missing product is simulated with a
    foreign-key-off single UPDATE inside the isolated test DB. Cleanup deletes the row.
    """
    cid = add_line(env, token, code)
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS=0")
            cur.execute("UPDATE cart_item SET product_id=999999 WHERE id=%s", (cid,))
            cur.execute("SET FOREIGN_KEY_CHECKS=1")
    finally:
        conn.close()
    return cid


def cleanup_missing_row(env: dict, cid: str) -> None:
    execute(env, "DELETE FROM cart_item WHERE id=%s", (cid,))


def race(fn_a, fn_b) -> tuple[Any, Any]:
    import threading

    barrier = threading.Barrier(2)
    out: dict[str, Any] = {}

    def run(name, fn):
        try:
            barrier.wait(timeout=10)
            out[name] = fn()
        except Exception as e:  # noqa: BLE001 - race worker must never kill the run
            out[name] = {"exception": repr(e)}

    t1 = threading.Thread(target=run, args=("a", fn_a))
    t2 = threading.Thread(target=run, args=("b", fn_b))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    return out.get("a"), out.get("b")


def conjunct(name: str, passed: bool, expected: Any, actual: Any, disposition: str = "FAIL") -> dict:
    return {
        "name": name,
        "pass": bool(passed),
        "disposition_if_fail": disposition,
        "expected": redact(expected),
        "actual": redact(actual),
    }


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(redact(obj), ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


# ---------------------------------------------------------------- order helpers

from helpers_lib import advance_to as _advance_to, place_order as _place_order  # noqa: E402

STATUSES = ["PLACED", "CONFIRMED", "PREPARED", "SHIPPED", "COMPLETED"]


def place(env: dict, token: str, product: str = "P-ON-10", qty: str = "1") -> dict:
    return _place_order(env, token=token, product=product, qty=qty)


def advance(env: dict, order_id: str | int, status: str, seller: str) -> dict:
    return _advance_to(env, str(order_id), status, seller_token=seller)


def cancel(env: dict, token: str, order_id: str | int, expected: str = "PLACED",
           seller: bool = False, body: dict | None = None) -> tuple[int, Any]:
    path = f"/api/admin/orders/{order_id}/cancel" if seller else f"/api/me/orders/{order_id}/cancel"
    if body is None:
        body = {"expectedStatus": expected, "reason": "B033-test"}
    return http_json("POST", f"{base_url(env)}{path}", body, auth_headers(token))


def order_db(env: dict, order_id: str | int) -> dict:
    return query(
        env,
        "SELECT id, customer_id, status, cancelled_by, cancelled_at, cancel_reason, total_amount "
        "FROM shop_order WHERE id=%s",
        (order_id,),
    )[0]


def product_db(env: dict, name: str) -> dict:
    return query(env, "SELECT stock, status, offline_reason FROM product WHERE name=%s", (name,))[0]


def order_detail(env: dict, token: str, order_id: str | int, seller: bool = False):
    base = "/api/admin/orders" if seller else "/api/me/orders"
    return http_json("GET", f"{base_url(env)}{base}/{order_id}", headers=auth_headers(token))


def list_orders(env: dict, token: str, seller: bool = False, page: int = 1, size: int = 20):
    base = "/api/admin/orders" if seller else "/api/me/orders"
    return http_json("GET", f"{base_url(env)}{base}?page={page}&size={size}",
                     headers=auth_headers(token))


def allowed_actions(detail: tuple[int, Any]) -> list[str]:
    return list((detail[1] or {}).get("data", {}).get("allowedActions") or [])

