#!/usr/bin/env python3
"""Runnable helpers used by cases and by run_case.py.

Every former ``helper:*`` reference expands to these functions — no dangling refs.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from b030_common import (
    ROOT,
    auth_headers,
    base_url,
    http_json,
    load_env,
    login_customer,
    login_seller,
    new_idem_key,
)

FIXTURE_IDS = ROOT / "runs" / "fixture-ids.json"


def load_fixtures() -> dict:
    if not FIXTURE_IDS.exists():
        raise RuntimeError(
            f"Missing {FIXTURE_IDS}. Run: python3 scripts/prepare_fixtures.py"
        )
    data = json.loads(FIXTURE_IDS.read_text(encoding="utf-8"))
    if data.get("blocked") or data.get("ready") is False:
        raise RuntimeError(f"Fixtures not ready: {data.get('blocked') or data}")
    return data


def product_id(code: str, fixtures: dict | None = None) -> str:
    fx = fixtures or load_fixtures()
    p = fx["products"].get(code) or {}
    pid = p.get("productId")
    if not pid:
        raise RuntimeError(f"Product {code} has no productId in fixture-ids.json: {p}")
    return str(pid)


def ensure_tokens(env: dict) -> dict[str, str]:
    return {
        "A": login_customer(env, "CUSTOMER_A"),
        "B": login_customer(env, "CUSTOMER_B"),
        "S": login_seller(env),
    }


def require_ok(label: str, code: int, body: Any, expect_http=(200, 201)) -> Any:
    if code not in expect_http:
        raise RuntimeError(f"{label} failed HTTP {code}: {body}")
    if isinstance(body, dict) and "code" in body and body["code"] not in (0, 200, None):
        # ApiResponse business code: 0 means ok in this project typically
        if body.get("code") not in (0,):
            # some endpoints use code==0 for success
            if body.get("message") and code in expect_http and body.get("data") is not None:
                return body
            if body.get("code") != 0:
                raise RuntimeError(f"{label} business code={body.get('code')}: {body}")
    return body


def cart_add(env: dict, token: str, product_code: str, qty: str = "1") -> dict:
    pid = product_id(product_code)
    code, body = http_json(
        "POST",
        f"{base_url(env)}/api/me/cart/items",
        {"productId": pid},
        auth_headers(token, new_idem_key()),
    )
    require_ok(f"cart_add {product_code}", code, body)
    cart_item_id = body["data"]["cartItemId"]
    if str(qty) != "1":
        code2, body2 = http_json(
            "PATCH",
            f"{base_url(env)}/api/me/cart/items/{cart_item_id}",
            {"quantity": str(qty)},
            auth_headers(token),
        )
        require_ok(f"cart_qty {product_code}->{qty}", code2, body2)
        return {"cartItemId": cart_item_id, "quantity": str(qty), "response": body2}
    return {"cartItemId": cart_item_id, "quantity": "1", "response": body}


def cart_qty(env: dict, token: str, product: str = "P-ON-10", qty: str = "1") -> dict:
    """helper:cart_qty — clear is caller's job via reset; add+set quantity."""
    return cart_add(env, token, product, qty)


def checkout_confirm(env: dict, token: str, cart_item_ids: list[str]) -> dict:
    code, body = http_json(
        "POST",
        f"{base_url(env)}/api/me/checkout/confirmations",
        {"cartItemIds": cart_item_ids},
        auth_headers(token),
    )
    require_ok("checkout_confirm", code, body)
    return {
        "confirmationToken": body["data"]["confirmationToken"],
        "response": body,
    }


def checkout_submit(
    env: dict,
    token: str,
    confirmation_token: str | None = None,
    cart_item_ids: list[str] | None = None,
    idem: str | None = None,
) -> dict:
    """helper:checkout_submit — confirm if needed then POST /api/me/orders."""
    if confirmation_token is None:
        if not cart_item_ids:
            raise RuntimeError("checkout_submit needs confirmation_token or cart_item_ids")
        confirmation_token = checkout_confirm(env, token, cart_item_ids)["confirmationToken"]
    key = idem or new_idem_key()
    code, body = http_json(
        "POST",
        f"{base_url(env)}/api/me/orders",
        {"confirmationToken": confirmation_token},
        auth_headers(token, key),
    )
    return {
        "http": code,
        "body": body,
        "idempotencyKey": key,
        "confirmationToken": confirmation_token,
        "orderId": (
            ((body or {}).get("data") or {}).get("orderId")
            or ((body or {}).get("data") or {}).get("id")
        )
        if isinstance(body, dict)
        else None,
        "orderNo": ((body or {}).get("data") or {}).get("orderNo") if isinstance(body, dict) else None,
        "message": (body or {}).get("message") if isinstance(body, dict) else None,
    }


def place_order(
    env: dict,
    token: str | None = None,
    product: str = "P-ON-10",
    qty: str = "1",
    account: str = "CUSTOMER_A",
) -> dict:
    """helper:place_order"""
    env = env or load_env()
    token = token or login_customer(env, account)
    cart = cart_add(env, token, product, qty)
    result = checkout_submit(env, token, cart_item_ids=[cart["cartItemId"]])
    if result["http"] not in (200, 201):
        raise RuntimeError(f"place_order failed: {result}")
    return {**result, "token": token, "cartItemId": cart["cartItemId"], "product": product, "qty": qty}


def dual_confirm(env: dict, product: str = "P-ON-1", qty: str = "1") -> dict:
    """helper:dual_confirm — A and B each confirm qty on same product (for SEQ-01)."""
    ta = login_customer(env, "CUSTOMER_A")
    tb = login_customer(env, "CUSTOMER_B")
    ca = cart_add(env, ta, product, qty)
    cb = cart_add(env, tb, product, qty)
    conf_a = checkout_confirm(env, ta, [ca["cartItemId"]])
    conf_b = checkout_confirm(env, tb, [cb["cartItemId"]])
    return {
        "A": {"token": ta, "cartItemId": ca["cartItemId"], "confirmationToken": conf_a["confirmationToken"], "idem": new_idem_key()},
        "B": {"token": tb, "cartItemId": cb["cartItemId"], "confirmationToken": conf_b["confirmationToken"], "idem": new_idem_key()},
        "productId": product_id(product),
    }


def advance_to(env: dict, order_id: str, status: str, seller_token: str | None = None) -> dict:
    """helper:advance_to — walk PLACED→…→target via admin actions."""
    token = seller_token or login_seller(env)
    chain = ["PLACED", "CONFIRMED", "PREPARED", "SHIPPED", "COMPLETED"]
    actions = {
        "CONFIRMED": ("CONFIRM", "PLACED"),
        "PREPARED": ("PREPARE", "CONFIRMED"),
        "SHIPPED": ("SHIP", "PREPARED"),
        "COMPLETED": ("COMPLETE", "SHIPPED"),
    }
    if status not in chain:
        raise RuntimeError(f"unsupported target status {status}")
    # read current
    code, body = http_json(
        "GET",
        f"{base_url(env)}/api/admin/orders/{order_id}",
        headers=auth_headers(token),
    )
    require_ok("get order", code, body)
    current = body["data"]["status"]
    target_idx = chain.index(status)
    cur_idx = chain.index(current)
    if cur_idx > target_idx:
        raise RuntimeError(f"order already {current}, cannot advance to {status}")
    for step_status in chain[cur_idx + 1 : target_idx + 1]:
        action, expected = actions[step_status]
        code, body = http_json(
            "POST",
            f"{base_url(env)}/api/admin/orders/{order_id}/actions",
            {"action": action, "expectedStatus": expected},
            auth_headers(token),
        )
        require_ok(f"advance {action}", code, body)
        current = body["data"]["status"]
    return {"orderId": order_id, "status": current, "tokenS": token}


def order_in_status(env: dict, status: str = "PLACED", product: str = "P-ON-10", qty: str = "1") -> dict:
    """helper:order_in_status"""
    placed = place_order(env, product=product, qty=qty)
    if status == "PLACED":
        return placed
    adv = advance_to(env, str(placed["orderId"]), status)
    return {**placed, **adv}


def cancel_order(env: dict, order_id: str, expected_status: str, as_seller: bool = False, token: str | None = None) -> dict:
    """helper:cancel"""
    if as_seller:
        token = token or login_seller(env)
        path = f"/api/admin/orders/{order_id}/cancel"
    else:
        token = token or login_customer(env, "CUSTOMER_A")
        path = f"/api/me/orders/{order_id}/cancel"
    code, body = http_json(
        "POST",
        f"{base_url(env)}{path}",
        {"expectedStatus": expected_status, "reason": "B030-test"},
        auth_headers(token),
    )
    return {"http": code, "body": body, "message": (body or {}).get("message")}


def seed_terminal_orders(env: dict) -> dict:
    """helper:seed_terminal_orders — one COMPLETED and one CANCELLED."""
    completed = order_in_status(env, "COMPLETED", "P-ON-10", "1")
    cancelled = order_in_status(env, "PLACED", "P-ON-5", "1")
    c = cancel_order(env, str(cancelled["orderId"]), "PLACED", as_seller=False, token=cancelled["token"])
    return {
        "completedId": completed["orderId"],
        "cancelledId": cancelled["orderId"],
        "tokenA": completed["token"],
        "tokenS": login_seller(env),
        "cancel_result": c,
    }


def mutate_product(env: dict, product: str = "P-ON-10") -> dict:
    """helper:mutate_product — change stock after order to prove snapshot immutability."""
    token = login_seller(env)
    pid = product_id(product)
    code, body = http_json(
        "PATCH",
        f"{base_url(env)}/api/admin/products/{pid}",
        {"stock": "99"},
        auth_headers(token),
    )
    require_ok("mutate stock", code, body)
    return {"productId": pid, "newStock": "99", "response": body}


def favorite_then_offline(env: dict, product: str = "P-ON-10") -> dict:
    """helper:favorite_then_offline"""
    ta = login_customer(env, "CUSTOMER_A")
    ts = login_seller(env)
    pid = product_id(product)
    code, body = http_json("PUT", f"{base_url(env)}/api/me/favorites/{pid}", headers=auth_headers(ta))
    require_ok("favorite", code, body)
    code2, body2 = http_json(
        "POST", f"{base_url(env)}/api/admin/products/{pid}/offline", headers=auth_headers(ts)
    )
    require_ok("offline", code2, body2)
    return {"tokenA": ta, "tokenS": ts, "productId": pid}


def cart_two_lines(env: dict) -> dict:
    """helper:cart_two_lines"""
    ta = login_customer(env, "CUSTOMER_A")
    c1 = cart_add(env, ta, "P-ON-10", "1")
    c2 = cart_add(env, ta, "P-ON-5", "1")
    return {"tokenA": ta, "c1": c1["cartItemId"], "c2": c2["cartItemId"]}


def cancel_restock_matrix(env: dict) -> dict:
    """helper:cancel_restock_matrix — order that zeros AUTO_ZERO product path + MANUAL offline product context."""
    # Use P-ON-1 (stock 1): order qty 1 → stock 0 AUTO_ZERO; cancel should restock+online
    # And ensure P-OFF-M stays MANUAL offline
    placed = place_order(env, product="P-ON-1", qty="1")
    return {
        "autoZeroOrderId": placed["orderId"],
        "tokenA": placed["token"],
        "productAuto": product_id("P-ON-1"),
        "productManual": product_id("P-OFF-M"),
    }


def confirm(env: dict, token: str, cart_item_id: str) -> dict:
    return checkout_confirm(env, token, [cart_item_id])


def submit(env: dict, token: str, confirmation_token: str, idem: str | None = None) -> dict:
    return checkout_submit(env, token, confirmation_token=confirmation_token, idem=idem)


HELPERS = {
    "place_order": place_order,
    "cart_qty": cart_qty,
    "checkout_submit": checkout_submit,
    "dual_confirm": dual_confirm,
    "advance_to": advance_to,
    "order_in_status": order_in_status,
    "cancel": cancel_order,
    "seed_terminal_orders": seed_terminal_orders,
    "mutate_product": mutate_product,
    "favorite_then_offline": favorite_then_offline,
    "cart_two_lines": cart_two_lines,
    "cancel_restock_matrix": cancel_restock_matrix,
    "confirm": confirm,
    "submit": submit,
}
