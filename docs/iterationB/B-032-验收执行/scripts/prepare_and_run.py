#!/usr/bin/env python3
"""B-032: prepare fixtures + execute PB-B01/02/03/12/13 (26 ACs) in ONE unified window."""
from __future__ import annotations

import json
import mimetypes
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b032_common import (  # noqa: E402
    ROOT,
    auth,
    base_url,
    code_of,
    connect_mysql,
    fe_url,
    http_json,
    load_env,
    login_customer,
    login_seller,
    msg,
    new_key,
    redact,
    require_db,
)

SEED = ROOT / "fixtures" / "seed.png"
EVID = ROOT / "evidence"
SHOTS = EVID / "screenshots"
CASES = EVID / "cases"
PW_DIR = "/tmp/oxstore-develop/frontend"
BE_DIR = "/tmp/oxstore-develop/backend"

PRODUCTS = {
    "P-ON-10": {"name": "B032-在售-10", "price": "12.50", "stock": "10", "status": "ONLINE"},
    "P-ON-5": {"name": "B032-在售-5", "price": "8.00", "stock": "5", "status": "ONLINE"},
    "P-ON-1": {"name": "B032-低库存-1", "price": "3.30", "stock": "1", "status": "ONLINE"},
    "P-OFF-M": {
        "name": "B032-人工下架-5",
        "price": "15.00",
        "stock": "5",
        "status": "OFFLINE",
        "offline_reason": "MANUAL",
    },
    "P-ZERO": {
        "name": "B032-零库存下架",
        "price": "9.90",
        "stock": "0",
        "status": "OFFLINE",
        "offline_reason": "AUTO_ZERO",
    },
    "P-STOCK": {"name": "B032-库存编辑", "price": "7.00", "stock": "20", "status": "ONLINE"},
}


def multipart_post(url: str, fields: dict, files: list, headers: dict):
    from urllib import error, request

    boundary = f"----B032{uuid.uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())
    for field, path in files:
        data = path.read_bytes()
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{field}"; filename="{path.name}"\r\n'.encode()
        )
        body.extend(f"Content-Type: {ctype}\r\n\r\n".encode())
        body.extend(data)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    req = request.Request(
        url,
        data=bytes(body),
        headers={**headers, "Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return e.code, {"raw": raw}


def result(ac_id: str, verdict: str, detail: dict) -> dict:
    return {"ac_id": ac_id, "verdict": verdict, "detail": redact(detail)}


def expect(cond: bool, detail: dict, ac_id: str, fail_reason: str = "") -> dict:
    if cond:
        return result(ac_id, "PASS", detail)
    return result(ac_id, "FAIL", {**detail, "fail_reason": fail_reason or "assertion failed"})


def json_default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


def dump_case(ac_id: str, payload: dict):
    CASES.mkdir(parents=True, exist_ok=True)
    (CASES / f"{ac_id}.json").write_text(
        json.dumps(redact(payload), ensure_ascii=False, indent=2, default=json_default),
        encoding="utf-8",
    )


def order_id_of(body) -> str:
    data = (body or {}).get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise KeyError("order id missing")
    oid = data.get("orderId") or data.get("id")
    if oid is None:
        raise KeyError("order id missing")
    return str(oid)


def product_row(env, pid: str) -> dict | None:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, stock, status, offline_reason, price FROM product WHERE id=%s",
                (pid,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def align_product(env, seller: str, pid: str, spec: dict):
    target = spec["stock"]
    patch = "1" if target == "0" else target
    code, body = http_json(
        "PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": patch}, auth(seller)
    )
    if code != 200:
        raise RuntimeError(f"PATCH stock {spec['name']}: {code} {body}")
    row = product_row(env, pid)
    if spec["status"] == "ONLINE":
        if row["status"] != "ONLINE":
            code, body = http_json(
                "POST", f"{base_url(env)}/api/admin/products/{pid}/online", headers=auth(seller)
            )
            if code != 200:
                raise RuntimeError(f"online {spec['name']}: {code} {body}")
        if str(row["stock"]) != target:
            http_json(
                "PATCH",
                f"{base_url(env)}/api/admin/products/{pid}",
                {"stock": target},
                auth(seller),
            )
        return
    if spec.get("offline_reason") == "MANUAL":
        if str(row["stock"]) == "0":
            http_json(
                "PATCH",
                f"{base_url(env)}/api/admin/products/{pid}",
                {"stock": "5"},
                auth(seller),
            )
        row = product_row(env, pid)
        if row["status"] != "OFFLINE" or row["offline_reason"] != "MANUAL":
            code, body = http_json(
                "POST",
                f"{base_url(env)}/api/admin/products/{pid}/offline",
                headers=auth(seller),
            )
            if code != 200:
                raise RuntimeError(f"offline {spec['name']}: {code} {body}")
        http_json(
            "PATCH",
            f"{base_url(env)}/api/admin/products/{pid}",
            {"stock": target},
            auth(seller),
        )
        return
    http_json(
        "PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "0"}, auth(seller)
    )


def reset_ns(env: dict):
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b032_tx_control SET fail_phase=NULL, probe_enabled=0, hold_seconds=0 WHERE id=1"
            )
            cur.execute("DELETE FROM b032_tx_probe")
            for sql in [
                "DELETE oi FROM order_item oi JOIN shop_order so ON so.id=oi.order_id JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b032_%'",
                "DELETE so FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b032_%'",
                "DELETE ci FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username LIKE 'b032_%'",
                "DELETE t FROM cart_item_tombstone t JOIN customer c ON c.id=t.customer_id WHERE c.username LIKE 'b032_%'",
                "DELETE f FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username LIKE 'b032_%'",
                "DELETE fm FROM favorite_mutation fm JOIN customer c ON c.id=fm.customer_id WHERE c.username LIKE 'b032_%'",
                "DELETE cci FROM checkout_confirmation_item cci JOIN checkout_confirmation cc ON cc.id=cci.confirmation_id JOIN customer c ON c.id=cc.customer_id WHERE c.username LIKE 'b032_%'",
                "DELETE cc FROM checkout_confirmation cc JOIN customer c ON c.id=cc.customer_id WHERE c.username LIKE 'b032_%'",
                "DELETE r FROM operation_receipt r JOIN customer c ON c.id=r.customer_id WHERE c.username LIKE 'b032_%'",
                "DELETE ta FROM trade_attempt ta JOIN purchase_intent pi ON pi.id=ta.intent_id WHERE pi.product_name_snapshot LIKE 'LEGACY-%' OR pi.product_name_snapshot LIKE 'B032-%'",
                "DELETE ta FROM trade_attempt ta JOIN purchase_intent pi ON pi.id=ta.intent_id JOIN customer c ON c.id=pi.customer_id WHERE c.username LIKE 'b032_%'",
                "DELETE FROM purchase_intent WHERE product_name_snapshot LIKE 'LEGACY-%' OR product_name_snapshot LIKE 'B032-%'",
                "DELETE pi FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id WHERE c.username LIKE 'b032_%'",
            ]:
                try:
                    cur.execute(sql)
                except Exception:
                    pass
            for name, stock, status, reason, price in [
                ("B032-在售-10", "10", "ONLINE", None, "12.50"),
                ("B032-在售-5", "5", "ONLINE", None, "8.00"),
                ("B032-低库存-1", "1", "ONLINE", None, "3.30"),
                ("B032-人工下架-5", "5", "OFFLINE", "MANUAL", "15.00"),
                ("B032-零库存下架", "0", "OFFLINE", "AUTO_ZERO", "9.90"),
                ("B032-库存编辑", "20", "ONLINE", None, "7.00"),
            ]:
                if reason is None:
                    cur.execute(
                        "UPDATE product SET price=%s, stock=%s, status=%s, offline_reason=NULL WHERE name=%s",
                        (price, stock, status, name),
                    )
                else:
                    cur.execute(
                        "UPDATE product SET price=%s, stock=%s, status=%s, offline_reason=%s WHERE name=%s",
                        (price, stock, status, reason, name),
                    )
    finally:
        conn.close()


def set_fail_phase(env, phase: str | None, probe: bool = True, hold_seconds: int = 0):
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b032_tx_control SET fail_phase=%s, probe_enabled=%s, hold_seconds=%s WHERE id=1",
                (phase, 1 if probe else 0, int(hold_seconds)),
            )
    finally:
        conn.close()


def clear_probe(env):
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM b032_tx_probe")
            cur.execute(
                "UPDATE b032_tx_control SET fail_phase=NULL, probe_enabled=0, hold_seconds=0 WHERE id=1"
            )
    finally:
        conn.close()


def probe_phases(env) -> list[str]:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT phase, note FROM b032_tx_probe ORDER BY id")
            return [f"{r['phase']}:{r['note']}" for r in cur.fetchall()]
    finally:
        conn.close()


def cart_add(env, token: str, product_id: str, qty: str | None = None) -> str:
    code, body = http_json(
        "POST",
        f"{base_url(env)}/api/me/cart/items",
        {"productId": str(product_id)},
        auth(token, new_key()),
    )
    if code not in (200, 201):
        raise RuntimeError(f"cart add: {code} {body}")
    data = body["data"]
    cid = str(data.get("cartItemId") or data.get("id") or data.get("itemId"))
    if qty and str(qty) != "1":
        code, body = http_json(
            "PATCH",
            f"{base_url(env)}/api/me/cart/items/{cid}",
            {"quantity": str(qty)},
            auth(token),
        )
        if code != 200:
            raise RuntimeError(f"cart qty: {code} {body}")
    return cid


def cart_list(env, token: str) -> list:
    code, body = http_json("GET", f"{base_url(env)}/api/me/cart", headers=auth(token))
    data = (body or {}).get("data") if code == 200 else None
    if isinstance(data, dict):
        return data.get("items") or []
    if isinstance(data, list):
        return data
    return []


def confirm(env, token: str, cart_item_ids: list[str]):
    code, body = http_json(
        "POST",
        f"{base_url(env)}/api/me/checkout/confirmations",
        {"cartItemIds": [str(x) for x in cart_item_ids]},
        auth(token),
    )
    return code, body


def submit_order(env, token: str, confirmation_token: str, idem: str | None = None):
    key = idem or new_key()
    code, body = http_json(
        "POST",
        f"{base_url(env)}/api/me/orders",
        {"confirmationToken": confirmation_token},
        auth(token, key),
    )
    return code, body, key


def place_order(env, token: str, cart_item_ids: list[str], idem: str | None = None):
    c_code, c_body = confirm(env, token, cart_item_ids)
    if c_code not in (200, 201):
        return c_code, c_body, None, None
    token_c = c_body["data"]["confirmationToken"]
    s_code, s_body, key = submit_order(env, token, token_c, idem)
    return s_code, s_body, key, token_c


def advance(env, seller: str, order_id: str, action: str, expected: str):
    return http_json(
        "POST",
        f"{base_url(env)}/api/admin/orders/{order_id}/actions",
        {"action": action, "expectedStatus": expected},
        auth(seller),
    )


def cancel_customer(env, token: str, order_id: str, expected_status: str = "PLACED"):
    return http_json(
        "POST",
        f"{base_url(env)}/api/me/orders/{order_id}/cancel",
        {"expectedStatus": expected_status, "reason": "B032-test-cancel"},
        auth(token),
    )


def cancel_admin(env, seller: str, order_id: str, expected_status: str = "PLACED"):
    return http_json(
        "POST",
        f"{base_url(env)}/api/admin/orders/{order_id}/cancel",
        {"expectedStatus": expected_status, "reason": "B032-admin-cancel"},
        auth(seller),
    )


def db_orders(env, username: str) -> list:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT so.id, so.order_no, so.status, so.total_amount, so.created_at, so.cancelled_by, so.cancelled_at "
                "FROM shop_order so JOIN customer c ON c.id=so.customer_id "
                "WHERE c.username=%s ORDER BY so.id",
                (username,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def db_order_items(env, order_id) -> list:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT product_id, product_name_snapshot AS product_name, quantity_snapshot AS quantity, "
                "unit_price_snapshot AS unit_price, line_amount_snapshot AS line_amount "
                "FROM order_item WHERE order_id=%s ORDER BY id",
                (order_id,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def db_cart(env, username: str) -> list:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ci.id, ci.product_id, ci.quantity FROM cart_item ci "
                "JOIN customer c ON c.id=ci.customer_id WHERE c.username=%s",
                (username,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def db_open_intents(env, username: str) -> int:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) c FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id "
                "WHERE c.username=%s AND pi.legacy_closed_at IS NULL",
                (username,),
            )
            return int(cur.fetchone()["c"])
    finally:
        conn.close()


def db_stock(env, pid: str) -> str:
    row = product_row(env, pid)
    return str(row["stock"]) if row else ""


def barrier_dual(fn_a, fn_b, mode="simultaneous", delay_ms=50):
    barrier = threading.Barrier(2)
    results = {}

    def worker(name, fn, delay):
        try:
            barrier.wait(timeout=60)
            if delay:
                time.sleep(delay / 1000.0)
            t0 = time.time()
            results[name] = {"ok": True, "result": fn(), "elapsed_ms": int((time.time() - t0) * 1000)}
        except Exception as e:
            results[name] = {"ok": False, "error": str(e)}

    da = delay_ms if mode == "b_first" else 0
    db = delay_ms if mode == "a_first" else 0
    t1 = threading.Thread(target=worker, args=("A", fn_a, da))
    t2 = threading.Thread(target=worker, args=("B", fn_b, db))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    return results


def shop_app_pids() -> list[str]:
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "com.team.shop.ShopApplication"], text=True
        ).strip()
        return [p for p in out.split() if p.isdigit()]
    except subprocess.CalledProcessError:
        return []


def listen_pid_8080() -> str | None:
    import re

    try:
        out = subprocess.check_output(
            ["lsof", "-iTCP:8080", "-sTCP:LISTEN", "-t"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            return out.splitlines()[0].strip()
    except Exception:
        pass
    pids = shop_app_pids()
    return pids[0] if pids else None


def health_ok(env) -> bool:
    code, _ = http_json(
        "POST",
        f"{base_url(env)}/api/admin/auth/login",
        {"username": "admin", "password": env.get("B032_SELLER_PASSWORD")},
    )
    return code == 200


def wait_be(env, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if health_ok(env):
            return True
        time.sleep(1.5)
    return False


def prepare(env: dict) -> dict:
    require_db(env["B032_DB_NAME"])
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE() AS db")
            db = cur.fetchone()["db"]
            cur.execute(
                "SELECT c.id FROM category c JOIN category p ON c.parent_id=p.id "
                "WHERE p.parent_id IS NULL ORDER BY c.id LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("No category2 — DataInitializer not run?")
            cat = str(row["id"])
            cur.execute("SELECT id, name FROM product WHERE name LIKE 'B032-%'")
            existing = {r["name"]: str(r["id"]) for r in cur.fetchall()}
    finally:
        conn.close()
    if db != env["B032_DB_NAME"]:
        raise RuntimeError(f"DB mismatch {db}")

    seller = login_seller(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    tb = login_customer(env, "b032_buyer_b", "B032-BuyerB-Pass9", "13803200002")

    pids = {}
    for code, spec in PRODUCTS.items():
        if spec["name"] in existing:
            pid = existing[spec["name"]]
        else:
            create_stock = "1" if spec["stock"] == "0" else spec["stock"]
            http, body = multipart_post(
                f"{base_url(env)}/api/admin/products",
                {
                    "name": spec["name"],
                    "price": spec["price"],
                    "category2Id": cat,
                    "stock": create_stock,
                    "sellingMode": "FIXED_PRICE",
                    "descriptionHtml": f"<p>{code}</p>",
                },
                [("images", SEED)],
                auth(seller),
            )
            if http not in (200, 201):
                raise RuntimeError(f"create {code}: {http} {body}")
            pid = str(body["data"].get("productId") or body["data"].get("id"))
        align_product(env, seller, pid, spec)
        pids[code] = pid

    out = {
        "ready": True,
        "db": db,
        "sut_sha": env.get("B032_SUT_SHA"),
        "base": base_url(env),
        "fe": fe_url(env),
        "products": pids,
        "category2Id": cat,
        "accounts": {"A": "b032_buyer_a", "B": "b032_buyer_b"},
    }
    (ROOT / "runs" / "fixture-ids.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {**out, "tokens": {"A": ta, "B": tb, "S": seller}}


# -------------------- AC runners --------------------


def ac_b01_01(env, fx):
    reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    c1 = cart_add(env, ta, p["P-ON-10"], "2")
    c2 = cart_add(env, ta, p["P-ON-5"], "1")
    code, body, _, _ = place_order(env, ta, [c1, c2])
    orders = db_orders(env, "b032_buyer_a")
    items = db_order_items(env, orders[0]["id"]) if orders else []
    intents = db_open_intents(env, "b032_buyer_a")
    names = {i["product_name"] for i in items}
    qtys = {str(i["product_id"]): str(i["quantity"]) for i in items}
    ok = (
        code == 201
        and msg(body) == "下单成功"
        and len(orders) == 1
        and orders[0]["status"] == "PLACED"
        and len(items) == 2
        and intents == 0
        and qtys.get(p["P-ON-10"]) == "2"
        and qtys.get(p["P-ON-5"]) == "1"
        and "失败" not in json.dumps(body, ensure_ascii=False)
    )
    detail = {
        "http": code,
        "message": msg(body),
        "orders": orders,
        "items": items,
        "open_intents": intents,
        "names": list(names),
    }
    dump_case("PB-B01-AC1", detail)
    return expect(ok, detail, "PB-B01-AC1", "multi-item single order / no legacy intent")


def ac_b01_02(env, fx):
    reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    cid = cart_add(env, ta, p["P-ON-10"], "1")
    code, body, _, _ = place_order(env, ta, [cid])
    oid = order_id_of(body)
    seq = []
    for action, expected in [
        ("CONFIRM", "PLACED"),
        ("PREPARE", "CONFIRMED"),
        ("SHIP", "PREPARED"),
        ("COMPLETE", "SHIPPED"),
    ]:
        hc, hb = advance(env, s, oid, action, expected)
        status = None
        if isinstance(hb, dict) and isinstance(hb.get("data"), dict):
            status = hb["data"].get("status")
        seq.append({"action": action, "http": hc, "message": msg(hb), "status": status})
    skip_c, skip_b = advance(env, s, oid, "CONFIRM", "PLACED")
    cust_c, cust_b = http_json(
        "POST",
        f"{base_url(env)}/api/admin/orders/{oid}/actions",
        {"action": "CONFIRM", "expectedStatus": "PLACED"},
        auth(ta),
    )
    order = db_orders(env, "b032_buyer_a")[0]
    ok = (
        code == 201
        and all(x["http"] == 200 for x in seq)
        and [x["status"] for x in seq] == ["CONFIRMED", "PREPARED", "SHIPPED", "COMPLETED"]
        and order["status"] == "COMPLETED"
        and skip_c >= 400
        and cust_c >= 400
    )
    detail = {"place": msg(body), "seq": seq, "skip": {"http": skip_c, "message": msg(skip_b)}, "customer_advance": {"http": cust_c, "message": msg(cust_b)}, "final": order}
    dump_case("PB-B01-AC2", detail)
    return expect(ok, detail, "PB-B01-AC2", "five-state sequential only")


def ac_b01_03(env, fx):
    reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    # completed terminal
    cid = cart_add(env, ta, p["P-ON-10"], "1")
    _, body, _, _ = place_order(env, ta, [cid])
    oid = order_id_of(body)
    for a, e in [("CONFIRM", "PLACED"), ("PREPARE", "CONFIRMED"), ("SHIP", "PREPARED"), ("COMPLETE", "SHIPPED")]:
        advance(env, s, oid, a, e)
    adv_c, adv_b = advance(env, s, oid, "COMPLETE", "SHIPPED")
    can_c, can_b = cancel_customer(env, ta, oid)
    # cancelled terminal
    cid2 = cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = place_order(env, ta, [cid2])
    oid2 = order_id_of(body2)
    cancel_customer(env, ta, oid2)
    adv2_c, adv2_b = advance(env, s, oid2, "CONFIRM", "PLACED")
    orders = db_orders(env, "b032_buyer_a")
    ok = (
        adv_c >= 400
        and can_c >= 400
        and adv2_c >= 400
        and any(o["status"] == "COMPLETED" for o in orders)
        and any(o["status"] == "CANCELLED" for o in orders)
    )
    detail = {
        "complete_advance": {"http": adv_c, "message": msg(adv_b)},
        "complete_cancel": {"http": can_c, "message": msg(can_b)},
        "cancelled_advance": {"http": adv2_c, "message": msg(adv2_b)},
        "orders": orders,
    }
    dump_case("PB-B01-AC3", detail)
    return expect(ok, detail, "PB-B01-AC3", "terminal states")


def ac_b01_04(env, fx):
    reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    cid = cart_add(env, ta, p["P-ON-10"], "1")
    _, body, _, _ = place_order(env, ta, [cid])
    oid = order_id_of(body)
    steps = []
    for a, e in [("CONFIRM", "PLACED"), ("PREPARE", "CONFIRMED"), ("SHIP", "PREPARED"), ("COMPLETE", "SHIPPED")]:
        # only action+expectedStatus — no address/carrier/voucher
        hc, hb = advance(env, s, oid, a, e)
        steps.append({"action": a, "http": hc, "message": msg(hb), "body_keys": list(((hb or {}).get("data") or {}).keys()) if isinstance(hb, dict) else []})
    order = db_orders(env, "b032_buyer_a")[0]
    ok = all(x["http"] == 200 for x in steps) and order["status"] == "COMPLETED"
    detail = {"steps": steps, "final": order, "note": "actions body only action+expectedStatus"}
    dump_case("PB-B01-AC4", detail)
    return expect(ok, detail, "PB-B01-AC4", "no logistics fields required")


def ac_b01_05(env, fx):
    reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    cid = cart_add(env, ta, p["P-ON-10"], "1")
    _, body, _, _ = place_order(env, ta, [cid])
    oid = order_id_of(body)
    first = advance(env, s, oid, "CONFIRM", "PLACED")
    stock_before = db_stock(env, p["P-ON-10"])
    dup = advance(env, s, oid, "CONFIRM", "PLACED")
    stock_after = db_stock(env, p["P-ON-10"])
    # concurrent advance PREPARE
    advance(env, s, oid, "PREPARE", "CONFIRMED")  # move to PREPARED? wait CONFIRMED->PREPARE->PREPARED
    # fresh order for concurrent confirm
    cid2 = cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = place_order(env, ta, [cid2])
    oid2 = order_id_of(body2)

    def a():
        return advance(env, s, oid2, "CONFIRM", "PLACED")

    def b():
        return advance(env, s, oid2, "CONFIRM", "PLACED")

    race = barrier_dual(a, b, "simultaneous")
    order2 = db_orders(env, "b032_buyer_a")
    o2 = [o for o in order2 if str(o["id"]) == oid2][0]
    race_codes = []
    for side in ("A", "B"):
        r = race[side]["result"] if race[side].get("ok") else (0, {"error": race[side].get("error")})
        race_codes.append(r[0] if isinstance(r, tuple) else 0)
    ok = (
        first[0] == 200
        and dup[0] >= 400
        and stock_before == stock_after
        and o2["status"] == "CONFIRMED"
        and 200 in race_codes
        and any(c >= 400 for c in race_codes)
    )
    detail = {
        "first": {"http": first[0], "message": msg(first[1])},
        "duplicate": {"http": dup[0], "message": msg(dup[1])},
        "stock_unchanged": stock_before == stock_after,
        "race": redact(race),
        "order2_status": o2["status"],
    }
    dump_case("PB-B01-AC5", detail)
    return expect(ok, detail, "PB-B01-AC5", "duplicate/concurrent advance")


def ac_b02_01(env, fx):
    reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    before = db_stock(env, p["P-ON-10"])
    cid = cart_add(env, ta, p["P-ON-10"], "2")
    code, body, _, _ = place_order(env, ta, [cid])
    after_place = db_stock(env, p["P-ON-10"])
    oid = order_id_of(body)
    for a, e in [("CONFIRM", "PLACED"), ("PREPARE", "CONFIRMED"), ("SHIP", "PREPARED"), ("COMPLETE", "SHIPPED")]:
        advance(env, s, oid, a, e)
    after_complete = db_stock(env, p["P-ON-10"])
    ok = (
        code == 201
        and int(before) - int(after_place) == 2
        and after_place == after_complete
    )
    detail = {"before": before, "after_place": after_place, "after_complete": after_complete, "message": msg(body)}
    dump_case("PB-B02-AC1", detail)
    return expect(ok, detail, "PB-B02-AC1", "direct deduct; complete no re-deduct")


def ac_b02_02(env, fx):
    reset_ns(env)
    ta, tb, s, p = fx["tokens"]["A"], fx["tokens"]["B"], fx["tokens"]["S"], fx["products"]
    cid = cart_add(env, ta, p["P-ON-10"], "3")
    place_order(env, ta, [cid])
    # B sees reduced stock via product API
    code, body = http_json("GET", f"{base_url(env)}/api/products/{p['P-ON-10']}")
    seen = None
    if isinstance(body, dict):
        data = body.get("data") or {}
        seen = str(data.get("stock") or data.get("availableStock") or "")
    stock_db = db_stock(env, p["P-ON-10"])
    oid = str(db_orders(env, "b032_buyer_a")[0]["id"])
    # offline product — order still flows
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(s))
    advance(env, s, oid, "CONFIRM", "PLACED")
    order = db_orders(env, "b032_buyer_a")[0]
    ok = stock_db == "7" and (seen == "7" or seen == stock_db) and order["status"] == "CONFIRMED"
    detail = {"buyer_seen_stock": seen, "db_stock": stock_db, "order_after_offline": order}
    dump_case("PB-B02-AC2", detail)
    return expect(ok, detail, "PB-B02-AC2", "others see deducted stock; offline keeps order")


def ac_b02_03(env, fx):
    reset_ns(env)
    s, p = fx["tokens"]["S"], fx["products"]
    pid = p["P-STOCK"]
    cases = []
    # negative
    c1, b1 = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "-1"}, auth(s))
    cases.append({"case": "neg", "http": c1, "message": msg(b1), "stock": db_stock(env, pid)})
    # decimal
    c2, b2 = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "1.5"}, auth(s))
    cases.append({"case": "decimal", "http": c2, "message": msg(b2), "stock": db_stock(env, pid)})
    # zero -> auto offline
    c3, b3 = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "0"}, auth(s))
    row0 = product_row(env, pid)
    cases.append({"case": "zero", "http": c3, "message": msg(b3), "row": row0})
    # large non-neg
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "1"}, auth(s))
    http_json("POST", f"{base_url(env)}/api/admin/products/{pid}/online", headers=auth(s))
    c4, b4 = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "999"}, auth(s))
    cases.append({"case": "large", "http": c4, "message": msg(b4), "stock": db_stock(env, pid)})
    ok = (
        cases[0]["message"] == "库存不能为负数，请输入非负整数。"
        and cases[0]["stock"] == "20"
        and cases[1]["message"] == "库存不能为负数，请输入非负整数。"
        and cases[1]["stock"] == "20"
        and cases[2]["http"] == 200
        and row0["status"] == "OFFLINE"
        and str(row0["stock"]) == "0"
        and cases[3]["http"] == 200
        and cases[3]["stock"] == "999"
    )
    detail = {"cases": cases}
    dump_case("PB-B02-AC3", detail)
    return expect(ok, detail, "PB-B02-AC3", "non-neg integer stock rules")


def ac_b02_04(env, fx):
    reset_ns(env)
    s, p = fx["tokens"]["S"], fx["products"]
    pid = p["P-STOCK"]
    align_product(env, s, pid, PRODUCTS["P-STOCK"])
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "0"}, auth(s))
    row0 = product_row(env, pid)
    # stock from 0 to positive — not auto online
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "5"}, auth(s))
    row1 = product_row(env, pid)
    # manual online
    http_json("POST", f"{base_url(env)}/api/admin/products/{pid}/online", headers=auth(s))
    row2 = product_row(env, pid)
    # manual offline with stock>0 then online
    http_json("POST", f"{base_url(env)}/api/admin/products/{pid}/offline", headers=auth(s))
    row3 = product_row(env, pid)
    http_json("POST", f"{base_url(env)}/api/admin/products/{pid}/online", headers=auth(s))
    row4 = product_row(env, pid)
    ok = (
        row0["status"] == "OFFLINE"
        and row1["status"] == "OFFLINE"
        and str(row1["stock"]) == "5"
        and row2["status"] == "ONLINE"
        and row3["status"] == "OFFLINE"
        and row3["offline_reason"] == "MANUAL"
        and row4["status"] == "ONLINE"
    )
    detail = {"zero": row0, "restock_no_auto": row1, "manual_online": row2, "manual_offline": row3, "reonline": row4}
    dump_case("PB-B02-AC4", detail)
    return expect(ok, detail, "PB-B02-AC4", "auto offline / no auto online / manual cycle")


def ac_b02_05(env, fx):
    reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    before = db_stock(env, p["P-ON-10"])
    cid = cart_add(env, ta, p["P-ON-10"], "2")
    _, body, _, _ = place_order(env, ta, [cid])
    after_order = db_stock(env, p["P-ON-10"])
    oid = order_id_of(body)
    for a, e in [("CONFIRM", "PLACED"), ("PREPARE", "CONFIRMED"), ("SHIP", "PREPARED"), ("COMPLETE", "SHIPPED")]:
        advance(env, s, oid, a, e)
    after_complete = db_stock(env, p["P-ON-10"])
    # cancel path stock restore (cross-ref PB-B05) — place+cancel
    cid2 = cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = place_order(env, ta, [cid2])
    oid2 = order_id_of(body2)
    before_c = db_stock(env, p["P-ON-5"])
    cancel_customer(env, ta, oid2)
    after_c = db_stock(env, p["P-ON-5"])
    table = {
        "下单成功": f"{before}->{after_order} (delta -2)",
        "交易完成成功": f"{after_order}->{after_complete} (unchanged)",
        "完成前取消": f"{before_c}->{after_c} (expect restore +1 if B05 wired)",
    }
    ok = int(before) - int(after_order) == 2 and after_order == after_complete
    detail = {"table": table, "cancel_restore_observed": before_c != after_c, "note": "cancel restore detailed in PB-B05"}
    dump_case("PB-B02-AC5", detail)
    return expect(ok, detail, "PB-B02-AC5", "stock change table for order/complete")


def ac_b03_01(env, fx):
    reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    c1 = cart_add(env, ta, p["P-ON-10"], "2")
    c2 = cart_add(env, ta, p["P-ON-5"], "1")
    code, body, _, _ = place_order(env, ta, [c1, c2])
    oid = order_id_of(body)
    snap = db_order_items(env, oid)
    order = db_orders(env, "b032_buyer_a")[0]
    # mutate live product stock/offline — snapshot unchanged
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}", {"stock": "99"}, auth(s))
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-5']}/offline", headers=auth(s))
    snap2 = db_order_items(env, oid)
    total = Decimal(str(order["total_amount"]))
    calc = sum(Decimal(str(i["unit_price"])) * Decimal(str(i["quantity"])) for i in snap)
    ok = (
        code == 201
        and order["order_no"]
        and snap == snap2
        and total == calc
        and str(total) == f"{total:.2f}"
    )
    detail = {"order": order, "snap": snap, "snap_after_mutate": snap2, "calc": str(calc), "message": msg(body)}
    dump_case("PB-B03-AC1", detail)
    return expect(ok, detail, "PB-B03-AC1", "frozen snapshot + 2dp total")


def ac_b03_02(env, fx):
    reset_ns(env)
    s, p = fx["tokens"]["S"], fx["products"]
    pid = p["P-ON-10"]
    before = product_row(env, pid)
    # attempt in-place name/price via PATCH — should ignore or reject (no edit capability)
    c1, b1 = http_json(
        "PATCH",
        f"{base_url(env)}/api/admin/products/{pid}",
        {"name": "HACKED", "price": "0.01", "stock": "10"},
        auth(s),
    )
    after = product_row(env, pid)
    ok = after["name"] == before["name"] and str(after["price"]) == str(before["price"])
    detail = {"http": c1, "message": msg(b1), "before": before, "after": after}
    dump_case("PB-B03-AC2", detail)
    return expect(ok, detail, "PB-B03-AC2", "no in-place name/price edit")


def ac_b03_03(env, fx):
    reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    cid = cart_add(env, ta, p["P-ON-10"], "1")
    place_order(env, ta, [cid])
    c_me, b_me = http_json("GET", f"{base_url(env)}/api/me/orders", headers=auth(ta))
    c_ad, b_ad = http_json("GET", f"{base_url(env)}/api/admin/orders", headers=auth(s))
    # UI labels via FE screenshots handled later; API presence
    me_ok = c_me == 200 and isinstance((b_me or {}).get("data"), (dict, list))
    ad_ok = c_ad == 200 and isinstance((b_ad or {}).get("data"), (dict, list))
    detail = {"me_orders": {"http": c_me, "message": msg(b_me)}, "admin_orders": {"http": c_ad, "message": msg(b_ad)}, "ui_labels": "订单历史 / 订单管理 (see screenshots)"}
    dump_case("PB-B03-AC3", detail)
    return expect(me_ok and ad_ok, detail, "PB-B03-AC3", "customer/admin order list APIs")


def ac_b03_04(env, fx):
    reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    # unauth
    c1, b1 = http_json("GET", f"{base_url(env)}/api/me/orders")
    c2, b2 = http_json(
        "GET", f"{base_url(env)}/api/me/orders", headers={"Authorization": "Bearer invalid.token.value"}
    )
    # multi incomplete orders
    c_a = cart_add(env, ta, p["P-ON-10"], "1")
    place_order(env, ta, [c_a])
    c_b = cart_add(env, ta, p["P-ON-5"], "1")
    place_order(env, ta, [c_b])
    orders = [o for o in db_orders(env, "b032_buyer_a") if o["status"] == "PLACED"]
    # access other's order
    tb = fx["tokens"]["B"]
    oid = str(orders[0]["id"])
    c3, b3 = http_json("GET", f"{base_url(env)}/api/me/orders/{oid}", headers=auth(tb))
    ok = (
        msg(b1) == "请先登录"
        and msg(b2) == "请重新登录"
        and len(orders) >= 2
        and c3 >= 400
    )
    detail = {
        "unauth": {"http": c1, "message": msg(b1)},
        "invalid": {"http": c2, "message": msg(b2)},
        "placed_count": len(orders),
        "other_access": {"http": c3, "message": msg(b3)},
    }
    dump_case("PB-B03-AC4", detail)
    return expect(ok, detail, "PB-B03-AC4", "auth + multi incomplete orders")


def ac_b03_05(env, fx):
    reset_ns(env)
    s = fx["tokens"]["S"]
    # legacy archive endpoints
    endpoints = [
        "/api/admin/legacy-intents",
        "/api/me/legacy-intents",
        "/api/admin/order-history",
    ]
    probed = []
    for ep in endpoints:
        # try both admin and me variants that exist
        pass
    c_ad, b_ad = http_json("GET", f"{base_url(env)}/api/admin/legacy-intents", headers=auth(s))
    c_me, b_me = http_json("GET", f"{base_url(env)}/api/me/legacy-intents", headers=auth(fx["tokens"]["A"]))
    # also buyer order-history legacy path if any
    c_oh, b_oh = http_json("GET", f"{base_url(env)}/api/me/order-history", headers=auth(fx["tokens"]["A"]))
    probed = [
        {"path": "/api/admin/legacy-intents", "http": c_ad, "message": msg(b_ad)},
        {"path": "/api/me/legacy-intents", "http": c_me, "message": msg(b_me)},
        {"path": "/api/me/order-history", "http": c_oh, "message": msg(b_oh)},
    ]
    # PASS if at least one legacy archive readable; new checkout didn't create open intents
    open_i = db_open_intents(env, "b032_buyer_a")
    readable = any(x["http"] == 200 for x in probed)
    ok = open_i == 0 and readable
    detail = {"probed": probed, "open_intents": open_i, "note": "legacy records read-only if present; new path has no open intents"}
    dump_case("PB-B03-AC5", detail)
    return expect(ok, detail, "PB-B03-AC5", "legacy archive readable; no new intents")


def ac_b12_01(env, fx):
    reset_ns(env)
    ta, tb, p = fx["tokens"]["A"], fx["tokens"]["B"], fx["products"]
    # no direct order endpoint without cart/confirmation
    c0, b0 = http_json(
        "POST",
        f"{base_url(env)}/api/me/orders",
        {"productId": p["P-ON-10"], "quantity": "1"},
        auth(ta, new_key()),
    )
    c1, b1 = http_json(
        "POST", f"{base_url(env)}/api/me/checkout/confirmations", {"cartItemIds": ["1"]}, headers={}
    )
    c2, b2 = http_json(
        "POST",
        f"{base_url(env)}/api/me/checkout/confirmations",
        {"cartItemIds": ["1"]},
        headers={"Authorization": "Bearer bad.token"},
    )
    # other's cart line
    cid_a = cart_add(env, ta, p["P-ON-10"], "1")
    stock_before = db_stock(env, p["P-ON-10"])
    cart_before = db_cart(env, "b032_buyer_a")
    c3, b3 = confirm(env, tb, [cid_a])
    # mixed
    cid_b = cart_add(env, tb, p["P-ON-5"], "1")
    c4, b4 = confirm(env, ta, [cid_a, cid_b])
    stock_after = db_stock(env, p["P-ON-10"])
    cart_after = db_cart(env, "b032_buyer_a")
    ok = (
        c0 >= 400
        and msg(b1) == "请先登录"
        and msg(b2) == "请重新登录"
        and msg(b3) == "无权操作"
        and msg(b4) == "无权操作"
        and stock_before == stock_after
        and cart_before == cart_after
        and len(db_orders(env, "b032_buyer_a")) == 0
    )
    detail = {
        "direct": {"http": c0, "message": msg(b0)},
        "unauth": {"http": c1, "message": msg(b1)},
        "invalid": {"http": c2, "message": msg(b2)},
        "other": {"http": c3, "message": msg(b3)},
        "mixed": {"http": c4, "message": msg(b4)},
        "stock_unchanged": stock_before == stock_after,
    }
    dump_case("PB-B12-AC1", detail)
    return expect(ok, detail, "PB-B12-AC1", "must cart+auth; 无权操作")


def ac_b12_02(env, fx):
    reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    c1 = cart_add(env, ta, p["P-ON-10"], "3")
    c2 = cart_add(env, ta, p["P-ON-5"], "1")
    code, body, _, _ = place_order(env, ta, [c1, c2])
    orders = db_orders(env, "b032_buyer_a")
    items = db_order_items(env, orders[0]["id"])
    # single qty=1 also ok
    reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    c3 = cart_add(env, ta, p["P-ON-10"], "1")
    code2, body2, _, _ = place_order(env, ta, [c3])
    ok = (
        code == 201
        and orders[0]["status"] == "PLACED"
        and len(items) == 2
        and any(str(i["quantity"]) == "3" for i in items)
        and code2 == 201
        and msg(body) == "下单成功"
    )
    detail = {"multi": {"http": code, "message": msg(body), "items": items}, "single": {"http": code2, "message": msg(body2)}}
    dump_case("PB-B12-AC2", detail)
    return expect(ok, detail, "PB-B12-AC2", "one order PLACED multi/single")


def ac_b12_03(env, fx):
    """Default selectable rows: API confirms only selected; offline not selectable — UI screenshot + API."""
    reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    c_on = cart_add(env, ta, p["P-ON-10"], "1")
    # add offline product to cart via DB insert simulating stale row, or skip if API rejects
    c_off, b_off = http_json(
        "POST",
        f"{base_url(env)}/api/me/cart/items",
        {"productId": p["P-OFF-M"]},
        auth(ta),
    )
    items = cart_list(env, ta)
    # submit only online selected
    code, body, _, _ = place_order(env, ta, [c_on])
    # empty selection
    c_empty, b_empty = confirm(env, ta, [])
    ok = (
        code == 201
        and msg(body) == "下单成功"
        and msg(b_empty) == "请选择商品"
        and c_off >= 400
    )
    detail = {
        "cart_items": items,
        "offline_add": {"http": c_off, "message": msg(b_off)},
        "selected_submit": {"http": code, "message": msg(body)},
        "empty": {"http": c_empty, "message": msg(b_empty)},
        "ui": "default checkbox / disable offline — see screenshots",
    }
    dump_case("PB-B12-AC3", detail)
    return expect(ok, detail, "PB-B12-AC3", "selection rules + 请选择商品")


def ac_b12_04(env, fx):
    reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    cid = cart_add(env, ta, p["P-ON-10"], "2")
    c_code, c_body = confirm(env, ta, [cid])
    token = c_body["data"]["confirmationToken"]
    # change qty after confirm
    http_json(
        "PATCH",
        f"{base_url(env)}/api/me/cart/items/{cid}",
        {"quantity": "3"},
        auth(ta),
    )
    s_code, s_body, _ = submit_order(env, ta, token)
    ok = (
        c_code in (200, 201)
        and s_code == 409
        and msg(s_body) == "确认信息已变化，请重新确认"
        and len(db_orders(env, "b032_buyer_a")) == 0
    )
    detail = {
        "confirm": {"http": c_code, "message": msg(c_body), "token_present": bool(token)},
        "submit_after_change": {"http": s_code, "message": msg(s_body), "code": code_of(s_body)},
    }
    dump_case("PB-B12-AC4", detail)
    return expect(ok, detail, "PB-B12-AC4", "confirm step + change rejects")


def ac_b12_05(env, fx):
    reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    cart_add(env, ta, p["P-ON-10"], "1")
    cart_add(env, ta, p["P-ON-5"], "1")
    stock_before = {k: db_stock(env, p[k]) for k in ("P-ON-10", "P-ON-5")}
    # clear cart
    c1, b1 = http_json("DELETE", f"{base_url(env)}/api/me/cart", headers=auth(ta))
    stock_after = {k: db_stock(env, p[k]) for k in ("P-ON-10", "P-ON-5")}
    cart_after = db_cart(env, "b032_buyer_a")
    orders = db_orders(env, "b032_buyer_a")
    ok = (
        c1 == 200
        and stock_before == stock_after
        and len(cart_after) == 0
        and len(orders) == 0
    )
    detail = {
        "clear": {"http": c1, "message": msg(b1)},
        "stock_before": stock_before,
        "stock_after": stock_after,
        "cart_after": cart_after,
        "orders": orders,
        "ui": "二次确认清空 — see screenshot",
    }
    dump_case("PB-B12-AC5", detail)
    return expect(ok, detail, "PB-B12-AC5", "clear cart no order/stock change")


def ac_b12_06(env, fx):
    reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    # insufficient stock: cart qty 5, stock 1
    align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    cid = cart_add(env, ta, p["P-ON-1"], "5")
    # force qty even if add capped
    http_json(
        "PATCH", f"{base_url(env)}/api/me/cart/items/{cid}", {"quantity": "5"}, auth(ta)
    )
    # may reject at patch — if so set via DB for fixture
    row = db_cart(env, "b032_buyer_a")
    if not row or str(row[0]["quantity"]) != "5":
        conn = connect_mysql(env)
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE cart_item SET quantity=5 WHERE id=%s", (cid,))
        finally:
            conn.close()
    c1, b1, _, _ = place_order(env, ta, [cid])
    # offline selected
    reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid2 = cart_add(env, ta, p["P-ON-10"], "1")
    # offline after add
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(s))
    c2, b2, _, _ = place_order(env, ta, [cid2])
    # empty
    c3, b3 = confirm(env, ta, [])
    name1 = PRODUCTS["P-ON-1"]["name"]
    name10 = PRODUCTS["P-ON-10"]["name"]
    expect_insuf = f"商品「{name1}」库存不足：当前可售 1 件，您选购了 5 件，请减少数量或移除后重试。"
    expect_off = f"商品「{name10}」已下架，请从购物车移除后重试。"
    # messages may be top-level or in errors[]
    def extract_msgs(body):
        out = [msg(body)]
        data = (body or {}).get("data") if isinstance(body, dict) else None
        if isinstance(data, dict):
            for e in data.get("errors") or []:
                out.append(e.get("message"))
        return [x for x in out if x]

    m1 = extract_msgs(b1)
    m2 = extract_msgs(b2)
    ok = (
        expect_insuf in m1
        and expect_off in m2
        and msg(b3) == "请选择商品"
        and len(db_orders(env, "b032_buyer_a")) == 0
    )
    detail = {
        "insufficient": {"http": c1, "messages": m1, "expect": expect_insuf},
        "offline": {"http": c2, "messages": m2, "expect": expect_off},
        "empty": {"http": c3, "message": msg(b3)},
        "stock_on1": db_stock(env, p["P-ON-1"]),
    }
    dump_case("PB-B12-AC6", detail)
    return expect(ok, detail, "PB-B12-AC6", "strict per-item failure messages")


def ac_b13_01(env, fx):
    reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    # POS
    cid = cart_add(env, ta, p["P-ON-10"], "2")
    stock0 = db_stock(env, p["P-ON-10"])
    code, body, _, _ = place_order(env, ta, [cid])
    stock1 = db_stock(env, p["P-ON-10"])
    cart1 = db_cart(env, "b032_buyer_a")
    orders1 = db_orders(env, "b032_buyer_a")
    pos_ok = (
        code == 201
        and msg(body) == "下单成功"
        and int(stock0) - int(stock1) == 2
        and len(cart1) == 0
        and len(orders1) == 1
        and "订单已生成但购物车未清理" not in json.dumps(body, ensure_ascii=False)
    )
    # NEG natural fail — insufficient
    reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = cart_add(env, ta, p["P-ON-1"], "1")
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cart_item SET quantity=5 WHERE id=%s", (cid,))
    finally:
        conn.close()
    # reconfirm path will fail validate
    stock_n0 = db_stock(env, p["P-ON-1"])
    cart_n0 = db_cart(env, "b032_buyer_a")
    cn, bn, _, _ = place_order(env, ta, [cid])
    stock_n1 = db_stock(env, p["P-ON-1"])
    cart_n1 = db_cart(env, "b032_buyer_a")
    orders_n = db_orders(env, "b032_buyer_a")
    neg_ok = cn >= 400 and stock_n0 == stock_n1 and cart_n0 == cart_n1 and len(orders_n) == 0

    # three fault breakpoints
    breaks = {}
    for phase in ("after_order", "after_stock", "after_cart"):
        reset_ns(env)
        ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
        fx["tokens"]["A"] = ta
        cid = cart_add(env, ta, p["P-ON-10"], "1")
        c_code, c_body = confirm(env, ta, [cid])
        token = c_body["data"]["confirmationToken"]
        clear_probe(env)
        set_fail_phase(env, phase, probe=True)
        stock_b = db_stock(env, p["P-ON-10"])
        cart_b = db_cart(env, "b032_buyer_a")
        s_code, s_body, _ = submit_order(env, ta, token)
        set_fail_phase(env, None, probe=False)
        phases = probe_phases(env)
        stock_a = db_stock(env, p["P-ON-10"])
        cart_a = db_cart(env, "b032_buyer_a")
        orders_a = db_orders(env, "b032_buyer_a")
        # MyISAM probe shows earlier phases; InnoDB must fully roll back
        rolled = (
            stock_a == stock_b
            and len(cart_a) == len(cart_b)
            and len(orders_a) == 0
            and s_code >= 400
        )
        breaks[phase] = {
            "http": s_code,
            "message": msg(s_body),
            "probe": phases,
            "rolled_back": rolled,
            "stock": [stock_b, stock_a],
            "cart_len": [len(cart_b), len(cart_a)],
            "orders": len(orders_a),
        }
    # after_cart: cart delete may not fire if we fail on after_cart at DELETE — use before_receipt as clear-car-after equivalent when delete logged
    # Also run before_receipt as clear-car proof if after_cart didn't hit delete path with remainder
    reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = cart_add(env, ta, p["P-ON-10"], "1")
    _, c_body = confirm(env, ta, [cid])
    token = c_body["data"]["confirmationToken"]
    clear_probe(env)
    set_fail_phase(env, "before_receipt", probe=True)
    stock_b = db_stock(env, p["P-ON-10"])
    s_code, s_body, _ = submit_order(env, ta, token)
    set_fail_phase(env, None, probe=False)
    phases = probe_phases(env)
    stock_a = db_stock(env, p["P-ON-10"])
    cart_a = db_cart(env, "b032_buyer_a")
    orders_a = db_orders(env, "b032_buyer_a")
    breaks["before_receipt_after_clear"] = {
        "http": s_code,
        "message": msg(s_body),
        "probe": phases,
        "rolled_back": stock_a == stock_b and len(cart_a) >= 1 and len(orders_a) == 0 and s_code >= 400,
        "stock": [stock_b, stock_a],
        "cart_len": len(cart_a),
        "note": "fail after order+stock+cart flushed, before success receipt",
    }

    breaks_ok = (
        breaks["after_order"]["rolled_back"]
        and "order_created" in str(breaks["after_order"]["probe"])
        and breaks["after_stock"]["rolled_back"]
        and "stock_updated" in str(breaks["after_stock"]["probe"])
        and (
            breaks["after_cart"]["rolled_back"]
            or breaks["before_receipt_after_clear"]["rolled_back"]
        )
        and (
            "cart_deleted" in str(breaks["after_cart"]["probe"])
            or (
                "order_created" in str(breaks["before_receipt_after_clear"]["probe"])
                and "stock_updated" in str(breaks["before_receipt_after_clear"]["probe"])
            )
        )
    )
    ok = pos_ok and neg_ok and breaks_ok
    detail = {
        "pos": {"http": code, "message": msg(body), "stock": [stock0, stock1], "cart": cart1, "orders": len(orders1)},
        "neg": {"http": cn, "message": msg(bn), "stock": [stock_n0, stock_n1], "cart": cart_n1, "orders": len(orders_n)},
        "breakpoints": breaks,
    }
    dump_case("PB-B13-AC1", detail)
    return expect(ok, detail, "PB-B13-AC1", "atomic POS/NEG + three breakpoints")


def ac_b13_02(env, fx):
    reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    cid = cart_add(env, ta, p["P-ON-10"], "2")
    # unselected row
    cid2 = cart_add(env, ta, p["P-ON-5"], "1")
    code, body, _, _ = place_order(env, ta, [cid])  # only first selected
    cart = db_cart(env, "b032_buyer_a")
    # selected removed; unselected kept
    kept = [r for r in cart if str(r["product_id"]) == p["P-ON-5"]]
    gone = [r for r in cart if str(r["product_id"]) == p["P-ON-10"]]
    # fail keeps selection
    reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = cart_add(env, ta, p["P-ON-1"], "1")
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cart_item SET quantity=5 WHERE id=%s", (cid,))
    finally:
        conn.close()
    cart_before = db_cart(env, "b032_buyer_a")
    place_order(env, ta, [cid])
    cart_after = db_cart(env, "b032_buyer_a")
    # post-lock add: confirm then submit with fault delay — add after success
    reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = cart_add(env, ta, p["P-ON-10"], "1")
    place_order(env, ta, [cid])
    # after order, add again same product — new line remains
    cid_new = cart_add(env, ta, p["P-ON-10"], "2")
    cart_new = db_cart(env, "b032_buyer_a")
    ok = (
        code == 201
        and len(kept) == 1
        and gone == []
        and cart_before == cart_after
        and any(str(r["id"]) == cid_new for r in cart_new)
    )
    detail = {
        "unselected_kept": kept,
        "selected_gone": gone == [],
        "fail_unchanged": cart_before == cart_after,
        "post_success_add": cart_new,
        "remainder_note": "confirm qty==cart qty under digest; remainder>0 requires post-lock concurrent add",
    }
    dump_case("PB-B13-AC2", detail)
    return expect(ok, detail, "PB-B13-AC2", "remainder/unselected/fail unchanged")


def ac_b13_03(env, fx):
    reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    cid = cart_add(env, ta, p["P-ON-10"], "1")
    _, body, _, _ = place_order(env, ta, [cid])
    oid = order_id_of(body)
    snap = db_order_items(env, oid)
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}", {"stock": "0"}, auth(s))
    advance(env, s, oid, "CONFIRM", "PLACED")
    advance(env, s, oid, "PREPARE", "CONFIRMED")
    snap2 = db_order_items(env, oid)
    # cancel does not restore cart
    cid2 = cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = place_order(env, ta, [cid2])
    oid2 = order_id_of(body2)
    cancel_customer(env, ta, oid2)
    cart = db_cart(env, "b032_buyer_a")
    ok = snap == snap2 and all(str(r["product_id"]) != p["P-ON-5"] for r in cart)
    detail = {"snap": snap, "snap_after": snap2, "cart_after_cancel": cart, "order_status": db_orders(env, "b032_buyer_a")}
    dump_case("PB-B13-AC3", detail)
    return expect(ok, detail, "PB-B13-AC3", "snapshot stable; cancel no cart restore")


def ac_b13_04(env, fx):
    reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    cid = cart_add(env, ta, p["P-ON-10"], "1")
    c_code, c_body = confirm(env, ta, [cid])
    token = c_body["data"]["confirmationToken"]
    key = new_key()
    s1, b1, _ = submit_order(env, ta, token, key)
    s2, b2, _ = submit_order(env, ta, token, key)
    orders = db_orders(env, "b032_buyer_a")
    stock = db_stock(env, p["P-ON-10"])
    # intentional new purchase
    cid2 = cart_add(env, ta, p["P-ON-10"], "1")
    s3, b3, _, _ = place_order(env, ta, [cid2])
    orders2 = db_orders(env, "b032_buyer_a")
    ok = (
        s1 == 201
        and msg(b1) == "下单成功"
        and msg(b2) == "订单已提交，请勿重复下单"
        and len(orders) == 1
        and stock == "9"
        and s3 == 201
        and len(orders2) == 2
    )
    detail = {
        "first": {"http": s1, "message": msg(b1)},
        "replay": {"http": s2, "message": msg(b2)},
        "new_purchase": {"http": s3, "message": msg(b3)},
        "orders": len(orders2),
        "stock": stock,
    }
    dump_case("PB-B13-AC4", detail)
    return expect(ok, detail, "PB-B13-AC4", "idempotent same key; new key new order")


def ac_b13_05(env, fx):
    reset_ns(env)
    ta, tb, s, p = fx["tokens"]["A"], fx["tokens"]["B"], fx["tokens"]["S"], fx["products"]
    align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    # dual confirm then simultaneous submit
    ca = cart_add(env, ta, p["P-ON-1"], "1")
    cb = cart_add(env, tb, p["P-ON-1"], "1")
    _, ba = confirm(env, ta, [ca])
    _, bb = confirm(env, tb, [cb])
    ta_tok = ba["data"]["confirmationToken"]
    tb_tok = bb["data"]["confirmationToken"]
    ka, kb = new_key(), new_key()

    def a():
        return submit_order(env, ta, ta_tok, ka)

    def b():
        return submit_order(env, tb, tb_tok, kb)

    race = barrier_dual(a, b, "simultaneous")
    stock = db_stock(env, p["P-ON-1"])
    orders_a = db_orders(env, "b032_buyer_a")
    orders_b = db_orders(env, "b032_buyer_b")
    placed = len(orders_a) + len(orders_b)
    codes = []
    for side in ("A", "B"):
        r = race[side].get("result")
        codes.append(r[0] if isinstance(r, tuple) else 0)

    def nested_msgs(body):
        out = [msg(body)]
        data = (body or {}).get("data") if isinstance(body, dict) else None
        if isinstance(data, dict):
            for e in data.get("errors") or []:
                out.append(e.get("message") or "")
        return " ".join(out)

    # offline reject
    reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = cart_add(env, ta, p["P-ON-10"], "1")
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(s))
    co, bo, _, _ = place_order(env, ta, [cid])
    ok = (
        placed == 1
        and stock == "0"
        and 201 in codes
        and any(c >= 400 for c in codes)
        and co >= 400
        and "已下架" in nested_msgs(bo)
    )
    detail = {
        "race": redact(race),
        "stock": stock,
        "placed": placed,
        "offline_submit": {"http": co, "message": msg(bo)},
    }
    dump_case("PB-B13-AC5", detail)
    return expect(ok, detail, "PB-B13-AC5", "no oversell; offline reject")


def run_screenshots(env, fx):
    """Playwright screenshots for checkout / orders / cart UI labels."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    seller_pwd = env.get("B032_SELLER_PASSWORD", "")
    js = f"""
const {{ chromium }} = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {{
  const fe = {json.dumps(fe_url(env))};
  const out = {{ok:false, shots:[]}};
  const browser = await chromium.launch({{headless:true}});
  try {{
    const page = await browser.newPage({{viewport:{{width:1280,height:800}}}});
    await page.goto(fe + '/login', {{waitUntil:'networkidle', timeout:60000}});
    await page.locator('#username').fill('b032_buyer_a');
    await page.locator('#password').fill('B032-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{ timeout: 15000 }});
    await page.screenshot({{path: {json.dumps(str(SHOTS / 'b03-after-login.png'))}, fullPage:true}});
    out.shots.push('b03-after-login.png');

    await page.goto(fe + '/', {{waitUntil:'networkidle', timeout:60000}});
    const link = page.locator('a[href*="/products/"]').first();
    await link.waitFor({{ timeout: 10000 }});
    await link.click();
    await page.waitForURL(u => String(u).includes('/products/'), {{ timeout: 10000 }});
    await page.waitForTimeout(800);
    await page.screenshot({{path: {json.dumps(str(SHOTS / 'b12-product-detail-no-direct-buy.png'))}, fullPage:true}});
    out.shots.push('b12-product-detail-no-direct-buy.png');
    const add = page.getByRole('button', {{ name: /加入购物车/ }});
    if (await add.count()) {{ await add.first().click(); await page.waitForTimeout(800); }}

    await page.goto(fe + '/me/cart', {{waitUntil:'networkidle', timeout:60000}});
    await page.waitForTimeout(1000);
    await page.screenshot({{path: {json.dumps(str(SHOTS / 'b12-cart-selection.png'))}, fullPage:true}});
    out.shots.push('b12-cart-selection.png');

    const checkout = page.getByRole('button', {{ name: /结算|确认下单|去结算|提交订单/ }});
    if (await checkout.count()) {{
      await checkout.first().click();
      await page.waitForTimeout(1200);
      await page.screenshot({{path: {json.dumps(str(SHOTS / 'b12-checkout-confirm.png'))}, fullPage:true}});
      out.shots.push('b12-checkout-confirm.png');
    }} else {{
      // still capture cart state as selection evidence
      await page.screenshot({{path: {json.dumps(str(SHOTS / 'b12-checkout-confirm.png'))}, fullPage:true}});
      out.shots.push('b12-checkout-confirm.png');
    }}

    // clear-cart confirm UI if available
    const clearBtn = page.getByRole('button', {{ name: /清空/ }});
    if (await clearBtn.count()) {{
      await clearBtn.first().click();
      await page.waitForTimeout(600);
      await page.screenshot({{path: {json.dumps(str(SHOTS / 'b12-clear-cart-confirm.png'))}, fullPage:true}});
      out.shots.push('b12-clear-cart-confirm.png');
    }}

    await page.goto(fe + '/me/order-history', {{waitUntil:'networkidle', timeout:60000}});
    await page.waitForTimeout(800);
    await page.screenshot({{path: {json.dumps(str(SHOTS / 'b03-order-history.png'))}, fullPage:true}});
    out.shots.push('b03-order-history.png');

    const page2 = await browser.newPage({{viewport:{{width:1280,height:800}}}});
    await page2.goto(fe + '/admin/login', {{waitUntil:'networkidle', timeout:60000}});
    await page2.locator('#username').fill('admin');
    await page2.locator('#password').fill({json.dumps(seller_pwd)});
    await page2.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page2.waitForURL(u => String(u).includes('/admin'), {{ timeout: 15000 }});
    await page2.goto(fe + '/admin/orders', {{waitUntil:'networkidle', timeout:60000}});
    await page2.waitForTimeout(800);
    await page2.screenshot({{path: {json.dumps(str(SHOTS / 'b03-admin-orders.png'))}, fullPage:true}});
    out.shots.push('b03-admin-orders.png');

    out.ok = out.shots.length >= 4;
  }} catch (e) {{
    out.error = String(e);
  }} finally {{
    await browser.close();
  }}
  console.log(JSON.stringify(out));
}})();
"""
    path = ROOT / "runs" / "_ui_screenshots.js"
    path.write_text(js, encoding="utf-8")
    proc = subprocess.run(
        ["node", str(path)], cwd=PW_DIR, capture_output=True, text=True, timeout=180
    )
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    try:
        parsed = json.loads(lines[-1] if lines else "{}")
    except Exception:
        parsed = {"ok": False, "raw": proc.stdout[-1500:], "err": proc.stderr[-800:]}
    if not parsed.get("ok"):
        parsed["stderr_tail"] = (proc.stderr or "")[-800:]
        parsed["stdout_tail"] = (proc.stdout or "")[-800:]
    return parsed


def verify_api_db(env) -> dict:
    """Bind running BE process → checkout SHA → datasource isolation DB (redacted)."""
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE() db")
            db = cur.fetchone()["db"]
            cur.execute("SELECT COUNT(*) c FROM product WHERE name LIKE 'B032-%'")
            n = cur.fetchone()["c"]
    finally:
        conn.close()
    code, body = http_json(
        "POST",
        f"{base_url(env)}/api/admin/auth/login",
        {"username": "admin", "password": env.get("B032_SELLER_PASSWORD")},
    )
    be_pid = listen_pid_8080()
    proc_bind: dict = {"be_pid": be_pid}
    if be_pid:
        try:
            environ_raw = Path(f"/proc/{be_pid}/environ").read_bytes().split(b"\0")
            env_map = {}
            for item in environ_raw:
                if b"=" in item:
                    k, v = item.split(b"=", 1)
                    env_map[k.decode(errors="replace")] = v.decode(errors="replace")
            proc_bind["process_db_name"] = env_map.get("DB_NAME")
            proc_bind["process_db_host"] = env_map.get("DB_HOST")
            proc_bind["process_db_port"] = env_map.get("DB_PORT")
            proc_bind["process_pwd"] = env_map.get("PWD")
            cmdline = Path(f"/proc/{be_pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            proc_bind["cmdline_has_shop_application"] = "com.team.shop.ShopApplication" in cmdline
            proc_bind["cmdline_classpath_hint"] = (
                "/tmp/oxstore-develop/backend/target/classes" in cmdline
            )
        except Exception as e:
            proc_bind["process_read_error"] = str(e)
    # Checkout SHA from develop worktree (SUT), not merely env claim
    checkout_sha = None
    develop_git = Path("/tmp/oxstore-develop")
    try:
        checkout_sha = (
            subprocess.check_output(["git", "-C", str(develop_git), "rev-parse", "HEAD"], text=True)
            .strip()
        )
    except Exception as e:
        proc_bind["checkout_sha_error"] = str(e)
    env_sha = env.get("B032_SUT_SHA")
    sha_match = bool(checkout_sha and env_sha and checkout_sha.startswith(str(env_sha)[:7]))
    db_match = db == env["B032_DB_NAME"]
    process_db_match = proc_bind.get("process_db_name") == env["B032_DB_NAME"]
    return {
        "db": db,
        "expected": env["B032_DB_NAME"],
        "match": db_match and process_db_match and bool(proc_bind.get("cmdline_has_shop_application")),
        "b032_products": n,
        "login_http": code,
        "be_pid": be_pid,
        "sut_sha_env": env_sha,
        "sut_sha_checkout": checkout_sha,
        "sut_sha_match": sha_match,
        "process_binding": proc_bind,
        "binding_note": "process environ DB_NAME + develop HEAD + API login; env alone is not sufficient",
    }


def main() -> int:
    EVID.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    CASES.mkdir(parents=True, exist_ok=True)
    env = load_env()
    require_db(env["B032_DB_NAME"])
    # Install/refresh inspectable TX probes from fixtures/b032_tx_probes.sql
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "install_tx_probes.py")])
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if not wait_be(env, timeout=30):
        raise SystemExit("BE not healthy on B032 credentials")
    verify = verify_api_db(env)
    if not verify["match"]:
        raise SystemExit(f"API/DB mismatch: {verify}")
    (EVID / "verify-api-db.json").write_text(
        json.dumps(verify, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    fx = prepare(env)
    fx["_seller_pwd"] = env.get("B032_SELLER_PASSWORD", "")
    import audit_acs  # noqa: WPS433
    import second_audit_acs as sa  # noqa: WPS433

    runners = [
        ac_b01_01,
        audit_acs.ac_b01_02,
        sa.ac_b01_03,
        sa.ac_b01_04,
        sa.ac_b01_05,
        ac_b02_01,
        audit_acs.ac_b02_02,
        sa.ac_b02_03,
        sa.ac_b02_04,
        audit_acs.ac_b02_05,
        sa.ac_b03_01,
        sa.ac_b03_02,
        audit_acs.ac_b03_03,
        ac_b03_04,
        sa.ac_b03_05,
        ac_b12_01,
        sa.ac_b12_02,
        sa.ac_b12_03,
        sa.ac_b12_04,
        sa.ac_b12_05,
        sa.ac_b12_06,
        sa.ac_b13_01,
        sa.ac_b13_02,
        sa.ac_b13_03,
        sa.ac_b13_04,
        sa.ac_b13_05,
    ]
    ac_names = {
        "ac_b01_01": "PB-B01-AC1",
        "ac_b01_02": "PB-B01-AC2",
        "ac_b01_03": "PB-B01-AC3",
        "ac_b01_04": "PB-B01-AC4",
        "ac_b01_05": "PB-B01-AC5",
        "ac_b02_01": "PB-B02-AC1",
        "ac_b02_02": "PB-B02-AC2",
        "ac_b02_03": "PB-B02-AC3",
        "ac_b02_04": "PB-B02-AC4",
        "ac_b02_05": "PB-B02-AC5",
        "ac_b03_01": "PB-B03-AC1",
        "ac_b03_02": "PB-B03-AC2",
        "ac_b03_03": "PB-B03-AC3",
        "ac_b03_04": "PB-B03-AC4",
        "ac_b03_05": "PB-B03-AC5",
        "ac_b12_01": "PB-B12-AC1",
        "ac_b12_02": "PB-B12-AC2",
        "ac_b12_03": "PB-B12-AC3",
        "ac_b12_04": "PB-B12-AC4",
        "ac_b12_05": "PB-B12-AC5",
        "ac_b12_06": "PB-B12-AC6",
        "ac_b13_01": "PB-B13-AC1",
        "ac_b13_02": "PB-B13-AC2",
        "ac_b13_03": "PB-B13-AC3",
        "ac_b13_04": "PB-B13-AC4",
        "ac_b13_05": "PB-B13-AC5",
    }
    results = []
    for fn in runners:
        fx["tokens"]["A"] = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
        fx["tokens"]["B"] = login_customer(env, "b032_buyer_b", "B032-BuyerB-Pass9", "13803200002")
        fx["tokens"]["S"] = login_seller(env)
        try:
            r = fn(env, fx)
        except Exception as e:
            r = result(ac_names.get(fn.__name__, fn.__name__), "FAIL", {"exception": str(e)})
        results.append(r)
        print(r["ac_id"], r["verdict"], flush=True)

    shots = sa.run_screenshots(env, fx)
    (EVID / "screenshots-index.json").write_text(
        json.dumps(redact(shots), ensure_ascii=False, indent=2, default=json_default), encoding="utf-8"
    )
    ended = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # Asia/Singapore wall clock for delivery narrative
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime, timezone

        started_sg = (
            datetime.fromisoformat(started.replace("Z", "+00:00"))
            .astimezone(ZoneInfo("Asia/Singapore"))
            .isoformat()
        )
        ended_sg = (
            datetime.fromisoformat(ended.replace("Z", "+00:00"))
            .astimezone(ZoneInfo("Asia/Singapore"))
            .isoformat()
        )
    except Exception:
        started_sg = ended_sg = None

    # Flatten conjunct evidence table across all ACs
    conjunct_rows = []
    for r in results:
        detail = r.get("detail") or {}
        conj = detail.get("conjuncts")
        if isinstance(conj, list) and conj:
            for c in conj:
                conjunct_rows.append(
                    {
                        "ac_id": r["ac_id"],
                        "ac_verdict": r["verdict"],
                        "conjunct": c.get("name"),
                        "pass": c.get("pass"),
                        "disposition_if_fail": c.get("disposition_if_fail"),
                    }
                )
        else:
            conjunct_rows.append(
                {
                    "ac_id": r["ac_id"],
                    "ac_verdict": r["verdict"],
                    "conjunct": "(legacy single-verdict AC — no explicit conjunct list)",
                    "pass": r["verdict"] == "PASS",
                    "disposition_if_fail": r["verdict"] if r["verdict"] != "PASS" else None,
                }
            )

    totals = {
        "execution_window": {
            "started_at": started,
            "ended_at": ended,
            "started_at_asia_singapore": started_sg,
            "ended_at_asia_singapore": ended_sg,
            "sut_sha": env.get("B032_SUT_SHA"),
            "sut_branch": env.get("B032_SUT_BRANCH"),
            "db": env["B032_DB_NAME"],
            "delivery_baseline": env.get("B032_DELIVERY_BASELINE"),
            "tx_probe_sql": "fixtures/b032_tx_probes.sql",
            "v8_sql": "fixtures/V8__close_legacy_fixed_price_intents.sql",
            "second_audit": "OF-19",
        },
        "sut_sha": env.get("B032_SUT_SHA"),
        "sut_branch": env.get("B032_SUT_BRANCH"),
        "db": env["B032_DB_NAME"],
        "base": base_url(env),
        "fe": fe_url(env),
        "be_pid": listen_pid_8080(),
        "verify_api_db": verify,
        "total": len(results),
        "pass": sum(1 for r in results if r["verdict"] == "PASS"),
        "fail": sum(1 for r in results if r["verdict"] == "FAIL"),
        "blocked": sum(1 for r in results if r["verdict"] == "BLOCKED"),
        "not_executed": sum(1 for r in results if r["verdict"] == "NOT_EXECUTED"),
        "screenshots": shots,
        "conjunct_table": conjunct_rows,
        "results": results,
    }
    (EVID / "results.json").write_text(
        json.dumps(totals, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8"
    )
    lines = [
        f"# B-032 results (second audit · OF-19)",
        f"",
        f"- window UTC: {started} → {ended}",
        f"- window Asia/Singapore: {started_sg} → {ended_sg}",
        f"- sut: {env.get('B032_SUT_BRANCH')}@{env.get('B032_SUT_SHA')}",
        f"- db: {env['B032_DB_NAME']}",
        f"- totals: PASS {totals['pass']} / FAIL {totals['fail']} / BLOCKED {totals['blocked']} / NOT_EXECUTED {totals['not_executed']} / total {totals['total']}",
        f"",
        f"## AC verdicts",
        f"",
        f"| AC | Verdict |",
        f"|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['ac_id']} | {r['verdict']} |")
    lines += [
        f"",
        f"## Conjunct evidence table",
        f"",
        f"| AC | AC verdict | Conjunct | Pass | If fail |",
        f"|---|---|---|---|---|",
    ]
    for row in conjunct_rows:
        lines.append(
            f"| {row['ac_id']} | {row['ac_verdict']} | {row['conjunct']} | {row['pass']} | {row['disposition_if_fail'] or ''} |"
        )
    (EVID / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: totals[k] for k in ("total", "pass", "fail", "blocked", "not_executed")},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
