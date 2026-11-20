#!/usr/bin/env python3
"""Audit-hardened AC runners for B-032 independent-review gaps.

Import helpers from prepare_and_run; override only the ACs that were over-claimed.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import threading
import time
from pathlib import Path

import prepare_and_run as m
from b032_common import (
    auth,
    base_url,
    code_of,
    connect_mysql,
    fe_url,
    http_json,
    login_customer,
    msg,
    new_key,
    redact,
)

SHOTS = m.SHOTS
PW_DIR = m.PW_DIR
PRODUCTS = m.PRODUCTS


def expect(cond: bool, detail: dict, ac_id: str, fail_reason: str = "", *, verdict_if_false: str = "FAIL"):
    if cond:
        return m.result(ac_id, "PASS", detail)
    return m.result(ac_id, verdict_if_false, {**detail, "fail_reason": fail_reason or "assertion failed"})


def set_control(env, *, fail_phase=None, probe=True, hold_seconds=0):
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE b032_tx_control SET fail_phase=%s, probe_enabled=%s, hold_seconds=%s WHERE id=1",
                (fail_phase, 1 if probe else 0, int(hold_seconds)),
            )
    finally:
        conn.close()


def nested_msgs(body) -> str:
    out = [msg(body)]
    data = (body or {}).get("data") if isinstance(body, dict) else None
    if isinstance(data, dict):
        for e in data.get("errors") or []:
            out.append(e.get("message") or "")
    return " ".join(x for x in out if x)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def run_node(js: str, name: str) -> dict:
    path = m.ROOT / "runs" / f"_{name}.js"
    path.write_text(js, encoding="utf-8")
    proc = subprocess.run(
        ["node", str(path)], cwd=PW_DIR, capture_output=True, text=True, timeout=240
    )
    lines = [ln for ln in (proc.stdout or "").strip().splitlines() if ln.strip()]
    try:
        parsed = json.loads(lines[-1] if lines else "{}")
    except Exception:
        parsed = {"ok": False}
    parsed["stderr_tail"] = (proc.stderr or "")[-800:]
    parsed["stdout_tail"] = (proc.stdout or "")[-800:]
    return parsed


def advance_full(env, seller, oid):
    steps = []
    for action, expected in [
        ("CONFIRM", "PLACED"),
        ("PREPARE", "CONFIRMED"),
        ("SHIP", "PREPARED"),
        ("COMPLETE", "SHIPPED"),
    ]:
        hc, hb = m.advance(env, seller, oid, action, expected)
        status = (hb or {}).get("data", {}).get("status") if isinstance(hb, dict) else None
        steps.append({"action": action, "http": hc, "message": msg(hb), "status": status})
    return steps


# -------------------- over-claimed ACs --------------------


def ac_b01_02(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    code, body, _, _ = m.place_order(env, ta, [cid])
    oid = m.order_id_of(body)
    seq = advance_full(env, s, oid)
    # skip from PLACED: fresh order, try SHIP without CONFIRM
    cid2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = m.place_order(env, ta, [cid2])
    oid2 = m.order_id_of(body2)
    skip_c, skip_b = m.advance(env, s, oid2, "SHIP", "PLACED")
    # rollback attempt: CONFIRMED then try CONFIRM again / go back to PLACED
    m.advance(env, s, oid2, "CONFIRM", "PLACED")
    back_c, back_b = m.advance(env, s, oid2, "CONFIRM", "PLACED")
    # customer tip must be 角色无权访问 (security filter) when hitting admin route
    cust_c, cust_b = http_json(
        "POST",
        f"{base_url(env)}/api/admin/orders/{oid}/actions",
        {"action": "CONFIRM", "expectedStatus": "PLACED"},
        auth(ta),
    )
    # no auto-transition: wait briefly, status unchanged
    time.sleep(1.5)
    mid = [o for o in m.db_orders(env, "b032_buyer_a") if str(o["id"]) == oid2][0]
    order = m.db_orders(env, "b032_buyer_a")[0]
    ok = (
        code == 201
        and [x["status"] for x in seq] == ["CONFIRMED", "PREPARED", "SHIPPED", "COMPLETED"]
        and skip_c >= 400
        and "跳步" in msg(skip_b) or "不允许" in msg(skip_b)
        and back_c >= 400
        and msg(cust_b) == "角色无权访问"
        and mid["status"] == "CONFIRMED"
        and order["status"] == "COMPLETED"
    )
    # fix operator precedence
    ok = (
        code == 201
        and [x["status"] for x in seq] == ["CONFIRMED", "PREPARED", "SHIPPED", "COMPLETED"]
        and skip_c >= 400
        and ("跳步" in msg(skip_b) or "不允许" in msg(skip_b))
        and back_c >= 400
        and msg(cust_b) == "角色无权访问"
        and mid["status"] == "CONFIRMED"
        and order["status"] == "COMPLETED"
    )
    detail = {
        "seq": seq,
        "skip_from_placed": {"http": skip_c, "message": msg(skip_b)},
        "no_rollback": {"http": back_c, "message": msg(back_b)},
        "customer_advance": {"http": cust_c, "message": msg(cust_b)},
        "no_auto_after_wait": mid,
    }
    m.dump_case("PB-B01-AC2", detail)
    return expect(ok, detail, "PB-B01-AC2", "five-state + skip/rollback/auto/customer tip")


def ac_b01_03(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, body, _, _ = m.place_order(env, ta, [cid])
    oid = m.order_id_of(body)
    advance_full(env, s, oid)
    adv_c, adv_b = m.advance(env, s, oid, "COMPLETE", "SHIPPED")
    can_c, can_b = m.cancel_customer(env, ta, oid, "COMPLETED")
    cid2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = m.place_order(env, ta, [cid2])
    oid2 = m.order_id_of(body2)
    m.cancel_customer(env, ta, oid2, "PLACED")
    adv2_c, adv2_b = m.advance(env, s, oid2, "CONFIRM", "PLACED")
    # no timeout auto-cancel: placed order waits, still PLACED
    cid3 = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, body3, _, _ = m.place_order(env, ta, [cid3])
    oid3 = m.order_id_of(body3)
    time.sleep(2.0)
    still = [o for o in m.db_orders(env, "b032_buyer_a") if str(o["id"]) == oid3][0]
    # Check no scheduled cancel job evidence in schema (honest: short wait + no timer API)
    orders = m.db_orders(env, "b032_buyer_a")
    ok = (
        adv_c >= 400
        and can_c >= 400
        and adv2_c >= 400
        and still["status"] == "PLACED"
        and any(o["status"] == "COMPLETED" for o in orders)
        and any(o["status"] == "CANCELLED" for o in orders)
    )
    detail = {
        "complete_advance": {"http": adv_c, "message": msg(adv_b)},
        "complete_cancel": {"http": can_c, "message": msg(can_b)},
        "cancelled_advance": {"http": adv2_c, "message": msg(adv2_b)},
        "no_timeout_auto_cancel": {
            "wait_sec": 2,
            "status_after_wait": still["status"],
            "note": "no cancel-timer API; short wait shows status stayed PLACED",
        },
        "orders": orders,
    }
    m.dump_case("PB-B01-AC3", detail)
    return expect(ok, detail, "PB-B01-AC3", "terminals + no auto timeout cancel")


def ac_b02_02(env, fx):
    m.reset_ns(env)
    ta, tb, s, p = fx["tokens"]["A"], fx["tokens"]["B"], fx["tokens"]["S"], fx["products"]
    cid = m.cart_add(env, ta, p["P-ON-10"], "3")
    _, body, _, _ = m.place_order(env, ta, [cid])
    oid = m.order_id_of(body)
    code, body_p = http_json("GET", f"{base_url(env)}/api/products/{p['P-ON-10']}")
    seen = str(((body_p or {}).get("data") or {}).get("stock") or "")
    stock_db = m.db_stock(env, p["P-ON-10"])
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(s))
    steps = advance_full(env, s, oid)
    order = [o for o in m.db_orders(env, "b032_buyer_a") if str(o["id"]) == oid][0]
    # new orders refused while offline — add may fail, or DB-seed cart then submit
    add_c, add_b = http_json(
        "POST",
        f"{base_url(env)}/api/me/cart/items",
        {"productId": p["P-ON-10"]},
        auth(tb, new_key()),
    )
    if add_c in (200, 201):
        cid_b = str((add_b.get("data") or {}).get("cartItemId") or (add_b.get("data") or {}).get("id"))
        rej_c, rej_b, _, _ = m.place_order(env, tb, [cid_b])
    else:
        conn = connect_mysql(env)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM customer WHERE username='b032_buyer_b'")
                bid = cur.fetchone()["id"]
                cur.execute(
                    "INSERT INTO cart_item(customer_id, product_id, quantity, updated_at) "
                    "VALUES (%s,%s,1,NOW(6))",
                    (bid, p["P-ON-10"]),
                )
                cid_b = str(cur.lastrowid)
        finally:
            conn.close()
        rej_c, rej_b, _, _ = m.place_order(env, tb, [cid_b])
    ok = (
        stock_db == "7"
        and (seen == "7" or seen == stock_db)
        and order["status"] == "COMPLETED"
        and all(x["http"] == 200 for x in steps)
        and rej_c >= 400
        and "已下架" in nested_msgs(rej_b)
    )
    detail = {
        "buyer_seen_stock": seen,
        "db_stock": stock_db,
        "flow_after_offline": steps,
        "final_order": order,
        "new_order_refused": {"http": rej_c, "message": msg(rej_b), "nested": nested_msgs(rej_b)},
        "offline_add": {"http": add_c, "message": msg(add_b)},
    }
    m.dump_case("PB-B02-AC2", detail)
    return expect(ok, detail, "PB-B02-AC2", "deduct visible; offline keeps order to complete; new refuse")


def ac_b02_04(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    pid = p["P-STOCK"]
    m.align_product(env, s, pid, PRODUCTS["P-STOCK"])
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "0"}, auth(s))
    row0 = m.product_row(env, pid)
    # buyer invisible / cannot open detail / cannot add
    list_c, list_b = http_json("GET", f"{base_url(env)}/api/products")
    detail_c, detail_b = http_json("GET", f"{base_url(env)}/api/products/{pid}")
    add_c, add_b = http_json(
        "POST",
        f"{base_url(env)}/api/me/cart/items",
        {"productId": pid},
        auth(ta, new_key()),
    )
    ids_in_list = []
    data = (list_b or {}).get("data")
    items = data.get("items") or data.get("content") or data if isinstance(data, (dict, list)) else []
    if isinstance(data, dict):
        items = data.get("items") or data.get("content") or []
    if isinstance(items, list):
        for it in items:
            ids_in_list.append(str(it.get("productId") or it.get("id") or ""))
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "5"}, auth(s))
    row1 = m.product_row(env, pid)
    http_json("POST", f"{base_url(env)}/api/admin/products/{pid}/online", headers=auth(s))
    row2 = m.product_row(env, pid)
    http_json("POST", f"{base_url(env)}/api/admin/products/{pid}/offline", headers=auth(s))
    row3 = m.product_row(env, pid)
    http_json("POST", f"{base_url(env)}/api/admin/products/{pid}/online", headers=auth(s))
    row4 = m.product_row(env, pid)
    ok = (
        row0["status"] == "OFFLINE"
        and pid not in ids_in_list
        and detail_c >= 400
        and add_c >= 400
        and row1["status"] == "OFFLINE"
        and str(row1["stock"]) == "5"
        and row2["status"] == "ONLINE"
        and row3["status"] == "OFFLINE"
        and row3["offline_reason"] == "MANUAL"
        and row4["status"] == "ONLINE"
    )
    detail = {
        "zero": row0,
        "list_has_product": pid in ids_in_list,
        "detail": {"http": detail_c, "message": msg(detail_b)},
        "add": {"http": add_c, "message": msg(add_b)},
        "restock_no_auto": row1,
        "manual_online": row2,
        "manual_offline": row3,
        "reonline": row4,
    }
    m.dump_case("PB-B02-AC4", detail)
    return expect(ok, detail, "PB-B02-AC4", "buyer invisible/detail/add + offline cycles")


def ac_b02_05(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    before = m.db_stock(env, p["P-ON-10"])
    cid = m.cart_add(env, ta, p["P-ON-10"], "2")
    _, body, _, _ = m.place_order(env, ta, [cid])
    after_order = m.db_stock(env, p["P-ON-10"])
    oid = m.order_id_of(body)
    advance_full(env, s, oid)
    after_complete = m.db_stock(env, p["P-ON-10"])
    # cancel restore
    cid2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = m.place_order(env, ta, [cid2])
    oid2 = m.order_id_of(body2)
    before_c = m.db_stock(env, p["P-ON-5"])
    m.cancel_customer(env, ta, oid2, "PLACED")
    after_c = m.db_stock(env, p["P-ON-5"])
    # 0-stock auto-offline then cancel restores 在售
    m.align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    cid3 = m.cart_add(env, ta, p["P-ON-1"], "1")
    _, body3, _, _ = m.place_order(env, ta, [cid3])
    oid3 = m.order_id_of(body3)
    row_zero = m.product_row(env, p["P-ON-1"])
    m.cancel_customer(env, ta, oid3, "PLACED")
    row_restored = m.product_row(env, p["P-ON-1"])
    # manual offline cancel stays offline
    m.align_product(env, s, p["P-OFF-M"], PRODUCTS["P-OFF-M"])
    # need an order on a product then manual offline — place on P-ON-5 then offline that product
    m.align_product(env, s, p["P-ON-5"], PRODUCTS["P-ON-5"])
    cid4 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body4, _, _ = m.place_order(env, ta, [cid4])
    oid4 = m.order_id_of(body4)
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-5']}/offline", headers=auth(s))
    row_man_before = m.product_row(env, p["P-ON-5"])
    m.cancel_customer(env, ta, oid4, "PLACED")
    row_man_after = m.product_row(env, p["P-ON-5"])
    ok = (
        int(before) - int(after_order) == 2
        and after_order == after_complete
        and int(after_c) == int(before_c) + 1
        and row_zero["status"] == "OFFLINE"
        and str(row_zero["stock"]) == "0"
        and row_restored["status"] == "ONLINE"
        and str(row_restored["stock"]) == "1"
        and row_man_before["offline_reason"] == "MANUAL"
        and row_man_after["status"] == "OFFLINE"
        and row_man_after["offline_reason"] == "MANUAL"
    )
    detail = {
        "table": {
            "下单成功": f"{before}->{after_order}",
            "交易完成成功": f"{after_order}->{after_complete}",
            "完成前取消": f"{before_c}->{after_c}",
            "零库存自动下架后取消恢复在售": {"before": row_zero, "after": row_restored},
            "人工下架后取消保持下架": {"before": row_man_before, "after": row_man_after},
        }
    }
    m.dump_case("PB-B02-AC5", detail)
    return expect(ok, detail, "PB-B02-AC5", "stock change table including cancel restore rules")


def ac_b03_03(env, fx):
    """Customer 订单历史 + merchant 订单管理 with real five-state data + screenshots."""
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    # create 5 orders and advance to different states + one cancelled
    states_wanted = []
    for i, (qty, target) in enumerate(
        [("1", "PLACED"), ("1", "CONFIRMED"), ("1", "PREPARED"), ("1", "SHIPPED"), ("1", "COMPLETED")]
    ):
        # refresh stock
        m.align_product(env, s, p["P-ON-10"], {"name": PRODUCTS["P-ON-10"]["name"], "price": "12.50", "stock": "10", "status": "ONLINE"})
        cid = m.cart_add(env, ta, p["P-ON-10"], qty)
        _, body, _, _ = m.place_order(env, ta, [cid])
        oid = m.order_id_of(body)
        if target == "CONFIRMED":
            m.advance(env, s, oid, "CONFIRM", "PLACED")
        elif target == "PREPARED":
            m.advance(env, s, oid, "CONFIRM", "PLACED")
            m.advance(env, s, oid, "PREPARE", "CONFIRMED")
        elif target == "SHIPPED":
            m.advance(env, s, oid, "CONFIRM", "PLACED")
            m.advance(env, s, oid, "PREPARE", "CONFIRMED")
            m.advance(env, s, oid, "SHIP", "PREPARED")
        elif target == "COMPLETED":
            advance_full(env, s, oid)
        states_wanted.append(target)
    # cancelled with metadata
    m.align_product(env, s, p["P-ON-5"], PRODUCTS["P-ON-5"])
    cid = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body, _, _ = m.place_order(env, ta, [cid])
    oid_c = m.order_id_of(body)
    m.cancel_customer(env, ta, oid_c, "PLACED")
    # API lists + pagination
    c_me, b_me = http_json("GET", f"{base_url(env)}/api/me/orders?page=1&size=2", headers=auth(ta))
    c_me2, b_me2 = http_json("GET", f"{base_url(env)}/api/me/orders?page=2&size=2", headers=auth(ta))
    c_ad, b_ad = http_json("GET", f"{base_url(env)}/api/admin/orders?page=1&size=5", headers=auth(s))
    orders = m.db_orders(env, "b032_buyer_a")
    cancelled = [o for o in orders if o["status"] == "CANCELLED"]
    # screenshots while data present
    shot = run_node(
        f"""
const {{ chromium }} = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {{
  const fe = {json.dumps(fe_url(env))};
  const out = {{ok:false, shots:[]}};
  const browser = await chromium.launch({{headless:true}});
  try {{
    const page = await browser.newPage({{viewport:{{width:1280,height:900}}}});
    await page.goto(fe + '/login', {{waitUntil:'networkidle'}});
    await page.locator('#username').fill('b032_buyer_a');
    await page.locator('#password').fill('B032-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{timeout:15000}});
    await page.goto(fe + '/me/order-history', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(1000);
    const title = await page.locator('text=订单历史').first().isVisible().catch(()=>false);
    const empty = await page.locator('text=暂无订单').count();
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b03-order-history.png'))}, fullPage:true}});
    out.shots.push('b03-order-history.png');
    out.customer = {{title, empty}};

    const page2 = await browser.newPage({{viewport:{{width:1280,height:900}}}});
    await page2.goto(fe + '/admin/login', {{waitUntil:'networkidle'}});
    await page2.locator('#username').fill('admin');
    await page2.locator('#password').fill({json.dumps(fx.get('_seller_pwd') or '')});
    await page2.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page2.waitForURL(u => /\\/admin(\\/|$)/.test(String(u)) && !String(u).includes('/login'), {{timeout:20000}});
    await page2.goto(fe + '/admin/orders', {{waitUntil:'networkidle'}});
    await page2.waitForTimeout(1200);
    if (page2.url().includes('/login')) throw new Error('still on admin login: '+page2.url());
    const adminTitle = await page2.locator('text=订单管理').first().isVisible().catch(()=>false);
    await page2.screenshot({{path: {json.dumps(str(SHOTS/'b03-admin-orders.png'))}, fullPage:true}});
    out.shots.push('b03-admin-orders.png');
    out.admin = {{title: adminTitle, url: page2.url()}};
    out.ok = title && empty === 0 && adminTitle && !page2.url().includes('/login');
  }} catch(e) {{ out.error = String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b03_ac3",
    )
    me_data = (b_me or {}).get("data") if isinstance(b_me, dict) else None
    page0_count = 0
    if isinstance(me_data, dict):
        page0_count = len(me_data.get("items") or me_data.get("content") or [])
    elif isinstance(me_data, list):
        page0_count = len(me_data)
    ok = (
        c_me == 200
        and c_ad == 200
        and len(orders) >= 6
        and len({o["status"] for o in orders}) >= 5
        and cancelled
        and cancelled[0].get("cancelled_by")
        and cancelled[0].get("cancelled_at")
        and shot.get("ok") is True
        and page0_count >= 1
        and c_me2 == 200
    )
    detail = {
        "db_statuses": sorted({o["status"] for o in orders}),
        "cancelled": cancelled,
        "me_page0": {"http": c_me, "count": page0_count},
        "me_page1": {"http": c_me2},
        "admin": {"http": c_ad, "message": msg(b_ad)},
        "screenshots": shot,
    }
    m.dump_case("PB-B03-AC3", detail)
    return expect(ok, detail, "PB-B03-AC3", "订单历史/订单管理 with five states + shots")


def ac_b03_05(env, fx):
    """Legacy close/unfreeze — seed fixtures or BLOCKED."""
    m.reset_ns(env)
    s, ta, p = fx["tokens"]["S"], fx["tokens"]["A"], fx["products"]
    conn = connect_mysql(env)
    before = 0
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM purchase_intent WHERE product_name_snapshot LIKE 'LEGACY-%'")
            cur.execute("SELECT COUNT(*) c FROM purchase_intent")
            before = int(cur.fetchone()["c"])
            cur.execute("SELECT id FROM customer WHERE username='b032_buyer_a'")
            cid = cur.fetchone()["id"]
            pid = int(p["P-ON-10"])
            now = "NOW(6)"
            cur.execute(
                f"""
                INSERT INTO purchase_intent
                (product_id, customer_id, product_name_snapshot, buyer_name, buyer_phone, status,
                 submitted_at, queue_seq, updated_at, processed_at, legacy_closed_at, legacy_close_reason)
                VALUES
                (%s,%s,'LEGACY-SUCCESS','b032_buyer_a','13803200001','SUCCESS',{now},101,{now},{now},NULL,NULL),
                (%s,%s,'LEGACY-FAILED','b032_buyer_a','13803200001','FAILED',{now},102,{now},{now},NULL,NULL),
                (%s,%s,'LEGACY-QUEUING','b032_buyer_a','13803200001','QUEUING',{now},103,{now},NULL,NULL,NULL),
                (%s,%s,'LEGACY-IN-TX','b032_buyer_a','13803200001','IN_TRANSACTION',{now},104,{now},NULL,NULL,NULL)
                """,
                (pid, cid, pid, cid, pid, cid, pid, cid),
            )
    except Exception as e:
        m.dump_case("PB-B03-AC5", {"seed_error": str(e), "before": before})
        return m.result(
            "PB-B03-AC5",
            "BLOCKED",
            {"reason": "cannot seed legacy purchase_intent", "error": str(e)},
        )
    finally:
        conn.close()

    # Probe archive endpoints — mutate attempt should fail
    c_ad, b_ad = http_json("GET", f"{base_url(env)}/api/admin/legacy-intents", headers=auth(s))
    c_me, b_me = http_json("GET", f"{base_url(env)}/api/me/legacy-intents", headers=auth(ta))
    # Attempt close via known migration endpoint if any
    close_c, close_b = http_json(
        "POST", f"{base_url(env)}/api/admin/legacy-intents/close", {}, auth(s)
    )
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status, legacy_closed_at, legacy_close_reason, product_name_snapshot "
                "FROM purchase_intent WHERE product_name_snapshot LIKE 'LEGACY-%' ORDER BY id"
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    # Without a working close endpoint that unfreezes, cannot claim full AC.
    has_close = close_c in (200, 201) or any(r.get("legacy_closed_at") for r in rows)
    success_failed_readonly = any(r["status"] == "SUCCESS" for r in rows) and any(
        r["status"] == "FAILED" for r in rows
    )
    if not has_close:
        detail = {
            "archive_get": {
                "admin": {"http": c_ad, "message": msg(b_ad)},
                "me": {"http": c_me, "message": msg(b_me)},
            },
            "close_attempt": {"http": close_c, "message": msg(close_b)},
            "seeded_rows": rows,
            "note": "seeded legacy rows exist; no close/unfreeze API succeeded — cannot prove close/unfreeze/restore",
        }
        m.dump_case("PB-B03-AC5", detail)
        return m.result("PB-B03-AC5", "BLOCKED", detail)

    ok = success_failed_readonly and has_close
    detail = {"rows": rows, "close": {"http": close_c, "message": msg(close_b)}}
    m.dump_case("PB-B03-AC5", detail)
    return expect(ok, detail, "PB-B03-AC5", "legacy archive close/unfreeze")


def ac_b12_03(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    c_on = m.cart_add(env, ta, p["P-ON-10"], "1")
    # insufficient stock row: online but stock < qty — should remain selectable (not 失效)
    m.align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    c_low = m.cart_add(env, ta, p["P-ON-1"], "1")
    http_json("PATCH", f"{base_url(env)}/api/me/cart/items/{c_low}", {"quantity": "5"}, auth(ta))
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cart_item SET quantity=5 WHERE id=%s", (c_low,))
    finally:
        conn.close()
    # offline add
    c_off, b_off = http_json(
        "POST",
        f"{base_url(env)}/api/me/cart/items",
        {"productId": p["P-OFF-M"]},
        auth(ta, new_key()),
    )
    # UI: default selection / disabled offline / insufficient not labeled 失效
    shot = run_node(
        f"""
const {{ chromium }} = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {{
  const fe = {json.dumps(fe_url(env))};
  const out = {{ok:false}};
  const browser = await chromium.launch({{headless:true}});
  try {{
    const page = await browser.newPage({{viewport:{{width:1280,height:900}}}});
    await page.goto(fe + '/login', {{waitUntil:'networkidle'}});
    await page.locator('#username').fill('b032_buyer_a');
    await page.locator('#password').fill('B032-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{timeout:15000}});
    await page.goto(fe + '/me/cart', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(1200);
    const allLabel = await page.locator('text=全选可下单商品').count();
    const disabled = await page.locator('input[type=checkbox][disabled], .ant-checkbox-disabled').count();
    const invalidTag = await page.locator('text=已下架').count();
    const insufHint = await page.locator('text=当前库存').count();
    const checked = await page.locator('.ant-checkbox-checked').count();
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-cart-selection.png'))}, fullPage:true}});
    out.shots = ['b12-cart-selection.png'];
    out.ui = {{allLabel, disabled, invalidTag, insufHint, checked}};
    out.ok = allLabel > 0 && checked > 0;
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b12_ac3",
    )
    code, body, _, _ = m.place_order(env, ta, [c_on])  # only online selected
    c_empty, b_empty = m.confirm(env, ta, [])
    ok = (
        code == 201
        and msg(b_empty) == "请选择商品"
        and c_off >= 400
        and shot.get("ok") is True
        and (shot.get("ui") or {}).get("insufHint", 0) >= 1
    )
    detail = {
        "offline_add": {"http": c_off, "message": msg(b_off)},
        "selected_submit": {"http": code, "message": msg(body)},
        "empty": {"http": c_empty, "message": msg(b_empty)},
        "ui": shot,
    }
    m.dump_case("PB-B12-AC3", detail)
    return expect(ok, detail, "PB-B12-AC3", "selection defaults + offline reject + UI")


def ac_b12_04(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    cid = m.cart_add(env, ta, p["P-ON-10"], "2")
    c_code, c_body = m.confirm(env, ta, [cid])
    token = c_body["data"]["confirmationToken"]
    # qty change
    http_json("PATCH", f"{base_url(env)}/api/me/cart/items/{cid}", {"quantity": "3"}, auth(ta))
    s_code, s_body, _ = m.submit_order(env, ta, token)
    # stock/status change after fresh confirm
    c2, b2 = m.confirm(env, ta, [cid])
    token2 = b2["data"]["confirmationToken"]
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(s))
    s2_c, s2_b, _ = m.submit_order(env, ta, token2)
    # re-online, reconfirm, success
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/online", headers=auth(s))
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}", {"stock": "10"}, auth(s))
    # cart may still have item
    carts = m.db_cart(env, "b032_buyer_a")
    if not carts:
        cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    else:
        cid = str(carts[0]["id"])
    s3_c, s3_b, _, _ = m.place_order(env, ta, [cid])
    # UI confirm modal with 清单/单价/数量/总金额
    # ensure cart has selectable item
    m.align_product(env, s, p["P-ON-5"], PRODUCTS["P-ON-5"])
    m.cart_add(env, ta, p["P-ON-5"], "1")
    shot = run_node(
        f"""
const {{ chromium }} = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {{
  const fe = {json.dumps(fe_url(env))};
  const out = {{ok:false}};
  const browser = await chromium.launch({{headless:true}});
  try {{
    const page = await browser.newPage({{viewport:{{width:1280,height:900}}}});
    await page.goto(fe + '/login', {{waitUntil:'networkidle'}});
    await page.locator('#username').fill('b032_buyer_a');
    await page.locator('#password').fill('B032-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{timeout:15000}});
    await page.goto(fe + '/me/cart', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(800);
    await page.getByRole('button', {{ name: '下单' }}).click();
    const modal = page.locator('.ant-modal').filter({{ hasText: '确认下单' }});
    await modal.waitFor({{ state: 'visible', timeout: 10000 }});
    await page.waitForTimeout(400);
    const hasTotal = await modal.locator('text=总金额').count();
    const hasUnit = await modal.locator('text=¥').count();
    const bodyText = await modal.innerText();
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-checkout-confirm.png'))}, fullPage:true}});
    out.shots = ['b12-checkout-confirm.png'];
    out.ui = {{hasTotal, hasUnit, bodyText: bodyText.slice(0, 400), url: page.url()}};
    out.ok = hasTotal > 0 && hasUnit > 0 && bodyText.includes('确认下单');
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b12_ac4",
    )
    # ensure not byte-identical to cart-selection if both exist
    cart_shot = SHOTS / "b12-cart-selection.png"
    conf_shot = SHOTS / "b12-checkout-confirm.png"
    distinct = True
    if cart_shot.exists() and conf_shot.exists():
        distinct = sha256_file(cart_shot) != sha256_file(conf_shot)
    ok = (
        c_code in (200, 201)
        and msg(s_body) == "确认信息已变化，请重新确认"
        and s2_c >= 400
        and s3_c == 201
        and msg(s3_b) == "下单成功"
        and shot.get("ok") is True
        and distinct
    )
    detail = {
        "qty_change": {"http": s_code, "message": msg(s_body)},
        "offline_after_confirm": {"http": s2_c, "message": msg(s2_b), "nested": nested_msgs(s2_b)},
        "reconfirm_success": {"http": s3_c, "message": msg(s3_b)},
        "ui_confirm": shot,
        "shots_distinct_from_cart": distinct,
    }
    m.dump_case("PB-B12-AC4", detail)
    return expect(ok, detail, "PB-B12-AC4", "confirm changes + reconfirm + real UI modal")


def ac_b13_01(env, fx):
    m.reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    # POS
    cid = m.cart_add(env, ta, p["P-ON-10"], "2")
    stock0 = m.db_stock(env, p["P-ON-10"])
    code, body, _, _ = m.place_order(env, ta, [cid])
    stock1 = m.db_stock(env, p["P-ON-10"])
    pos_ok = code == 201 and msg(body) == "下单成功" and int(stock0) - int(stock1) == 2 and len(m.db_cart(env, "b032_buyer_a")) == 0
    # NEG
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = m.cart_add(env, ta, p["P-ON-1"], "1")
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cart_item SET quantity=5 WHERE id=%s", (cid,))
    finally:
        conn.close()
    stock_n0 = m.db_stock(env, p["P-ON-1"])
    cart_n0 = m.db_cart(env, "b032_buyer_a")
    cn, bn, _, _ = m.place_order(env, ta, [cid])
    neg_ok = cn >= 400 and m.db_stock(env, p["P-ON-1"]) == stock_n0 and m.db_cart(env, "b032_buyer_a") == cart_n0 and len(m.db_orders(env, "b032_buyer_a")) == 0

    breaks = {}
    for phase, need_probe in [
        ("after_order", "order_created"),
        ("after_stock", "stock_updated"),
        ("after_cart", "cart_deleted"),
    ]:
        m.reset_ns(env)
        ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
        fx["tokens"]["A"] = ta
        cid = m.cart_add(env, ta, p["P-ON-10"], "1")
        _, c_body = m.confirm(env, ta, [cid])
        token = c_body["data"]["confirmationToken"]
        m.clear_probe(env)
        set_control(env, fail_phase=phase, probe=True, hold_seconds=0)
        stock_b = m.db_stock(env, p["P-ON-10"])
        cart_b = m.db_cart(env, "b032_buyer_a")
        s_code, s_body, _ = m.submit_order(env, ta, token)
        set_control(env, fail_phase=None, probe=False, hold_seconds=0)
        phases = m.probe_phases(env)
        stock_a = m.db_stock(env, p["P-ON-10"])
        cart_a = m.db_cart(env, "b032_buyer_a")
        orders_a = m.db_orders(env, "b032_buyer_a")
        rolled = stock_a == stock_b and len(cart_a) == len(cart_b) and len(orders_a) == 0 and s_code >= 400
        breaks[phase] = {
            "http": s_code,
            "message": msg(s_body),
            "probe": phases,
            "rolled_back": rolled,
            "required_probe": need_probe,
            "probe_hit": need_probe in str(phases),
            "stock": [stock_b, stock_a],
            "cart_len": [len(cart_b), len(cart_a)],
        }

    breaks_ok = all(
        breaks[ph]["rolled_back"] and breaks[ph]["probe_hit"]
        for ph in ("after_order", "after_stock", "after_cart")
    )
    ok = pos_ok and neg_ok and breaks_ok
    detail = {
        "pos": {"http": code, "message": msg(body), "stock": [stock0, stock1]},
        "neg": {"http": cn, "message": msg(bn)},
        "breakpoints": breaks,
        "trigger_sql": "fixtures/b032_tx_probes.sql",
        "conjunction": "after_order AND after_stock AND after_cart (no OR)",
    }
    m.dump_case("PB-B13-AC1", detail)
    return expect(ok, detail, "PB-B13-AC1", "POS/NEG + three breakpoints each roll back")


def ac_b13_02(env, fx):
    """余数 / 锁定前加购 / 锁定后加购."""
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    # unselected kept
    c1 = m.cart_add(env, ta, p["P-ON-10"], "2")
    c2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    code, body, _, _ = m.place_order(env, ta, [c1])
    cart = m.db_cart(env, "b032_buyer_a")
    kept = [r for r in cart if str(r["product_id"]) == p["P-ON-5"]]
    # 锁定前新增: confirm then PATCH qty before submit → 确认信息已变化; reconfirm uses new qty
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, cb = m.confirm(env, ta, [cid])
    token = cb["data"]["confirmationToken"]
    http_json("PATCH", f"{base_url(env)}/api/me/cart/items/{cid}", {"quantity": "3"}, auth(ta))
    pre_c, pre_b, _ = m.submit_order(env, ta, token)
    # reconfirm locks new qty 3
    sc, sb, _, _ = m.place_order(env, ta, [cid])
    items = m.db_order_items(env, m.db_orders(env, "b032_buyer_a")[0]["id"]) if sc == 201 else []
    locked_qty = str(items[0]["quantity"]) if items else None
    # 锁定后新增: hold TX, concurrent add while locks held, then remainder/new line survives
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    tb = login_customer(env, "b032_buyer_b", "B032-BuyerB-Pass9", "13803200002")
    fx["tokens"]["B"] = tb
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, cb = m.confirm(env, ta, [cid])
    token = cb["data"]["confirmationToken"]
    m.clear_probe(env)
    set_control(env, fail_phase=None, probe=True, hold_seconds=3)
    results = {}

    def submitter():
        results["submit"] = m.submit_order(env, ta, token)

    def adder():
        # wait until order_created probe appears (= inside TX / holding locks)
        deadline = time.time() + 8
        while time.time() < deadline:
            phases = m.probe_phases(env)
            if any("order_created" in x for x in phases):
                break
            time.sleep(0.05)
        # attempt add same product for same buyer via second request while TX holds locks
        results["add"] = http_json(
            "POST",
            f"{base_url(env)}/api/me/cart/items",
            {"productId": p["P-ON-10"]},
            auth(ta, new_key()),
            timeout=30,
        )
        results["add_at"] = time.time()

    t1 = threading.Thread(target=submitter)
    t2 = threading.Thread(target=adder)
    t1.start()
    time.sleep(0.2)
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    set_control(env, fail_phase=None, probe=False, hold_seconds=0)
    cart_after = m.db_cart(env, "b032_buyer_a")
    orders = m.db_orders(env, "b032_buyer_a")
    post_lock_survived = len(cart_after) >= 1 and len(orders) == 1
    # 余数>0: public confirm/submit digest forces qty equality → remainder always 0.
    # Prove via code path note + attempt: after successful full-qty order cart line gone (remainder 0).
    remainder_note = (
        "CheckoutService digest includes cart quantity; success path always has "
        "confirmation.qty == cart.qty, so remainder = cart.qty - confirmation.qty is always 0 "
        "via public API. Partial-line order API does not exist."
    )
    remainder_ok = False  # cannot prove >0 via public API
    ok_core = (
        code == 201
        and len(kept) == 1
        and msg(pre_b) == "确认信息已变化，请重新确认"
        and sc == 201
        and locked_qty == "3"
        and post_lock_survived
    )
    # Overall: FAIL remainder conjunct explicitly while others pass → AC FAIL (missing conjunct)
    # Or PASS with remainder marked BLOCKED sub-conjunct — audit says every conjunct must be proven.
    detail = {
        "unselected_kept": kept,
        "lock_before_add": {
            "submit_after_patch": {"http": pre_c, "message": msg(pre_b)},
            "reconfirm_order_qty": locked_qty,
        },
        "lock_after_add": {
            "submit": redact(results.get("submit")),
            "add": redact(results.get("add")),
            "cart_after": cart_after,
            "orders": len(orders),
            "probe": m.probe_phases(env),
        },
        "remainder_gt0": {
            "proven": remainder_ok,
            "note": remainder_note,
            "disposition": "BLOCKED",
        },
    }
    m.dump_case("PB-B13-AC2", detail)
    if ok_core and not remainder_ok:
        return m.result(
            "PB-B13-AC2",
            "FAIL",
            {**detail, "fail_reason": "余数>0 kept not runnable via public API (digest forces qty equality)"},
        )
    return expect(ok_core and remainder_ok, detail, "PB-B13-AC2", "remainder + lock before/after add")


def ac_b13_03(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, body, _, _ = m.place_order(env, ta, [cid])
    oid = m.order_id_of(body)
    snap = m.db_order_items(env, oid)
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}", {"stock": "0"}, auth(s))
    steps = advance_full(env, s, oid)
    snap2 = m.db_order_items(env, oid)
    # new orders rejected at stock 0
    add_c, add_b = http_json(
        "POST", f"{base_url(env)}/api/me/cart/items", {"productId": p["P-ON-10"]}, auth(ta, new_key())
    )
    # merchant cancel does not restore cart
    m.align_product(env, s, p["P-ON-5"], PRODUCTS["P-ON-5"])
    cid2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = m.place_order(env, ta, [cid2])
    oid2 = m.order_id_of(body2)
    m.cancel_admin(env, s, oid2, "PLACED")
    cart = m.db_cart(env, "b032_buyer_a")
    ok = (
        snap == snap2
        and all(x["http"] == 200 for x in steps)
        and steps[-1]["status"] == "COMPLETED"
        and add_c >= 400
        and all(str(r["product_id"]) != p["P-ON-5"] for r in cart)
    )
    detail = {
        "snap": snap,
        "snap_after": snap2,
        "flow_to_complete": steps,
        "new_order_at_zero": {"http": add_c, "message": msg(add_b)},
        "merchant_cancel_cart": cart,
    }
    m.dump_case("PB-B13-AC3", detail)
    return expect(ok, detail, "PB-B13-AC3", "snapshot + complete after zero + merchant cancel no cart restore")


def ac_b13_04(env, fx):
    m.reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, c_body = m.confirm(env, ta, [cid])
    token = c_body["data"]["confirmationToken"]
    key = new_key()
    s1, b1, _ = m.submit_order(env, ta, token, key)
    # simulate lost response: client retries same key
    s2, b2, _ = m.submit_order(env, ta, token, key)
    orders = m.db_orders(env, "b032_buyer_a")
    # recover from 订单历史
    hist_c, hist_b = http_json("GET", f"{base_url(env)}/api/me/orders", headers=auth(ta))
    found = False
    data = (hist_b or {}).get("data")
    items = []
    if isinstance(data, dict):
        items = data.get("items") or data.get("content") or []
    elif isinstance(data, list):
        items = data
    for it in items:
        if str(it.get("orderNo") or "") == str(orders[0]["order_no"]):
            found = True
    # idempotency key not for cart-clear: after success cart empty; retry does not "补清车" path — cart still empty, still duplicate tip
    cart = m.db_cart(env, "b032_buyer_a")
    # intentional new purchase
    cid2 = m.cart_add(env, ta, p["P-ON-10"], "1")
    s3, b3, _, _ = m.place_order(env, ta, [cid2])
    ok = (
        s1 == 201
        and msg(b1) == "下单成功"
        and msg(b2) == "订单已提交，请勿重复下单"
        and len(orders) == 1
        and found
        and hist_c == 200
        and len(cart) == 0
        and s3 == 201
        and len(m.db_orders(env, "b032_buyer_a")) == 2
    )
    detail = {
        "first": {"http": s1, "message": msg(b1)},
        "lost_response_replay": {"http": s2, "message": msg(b2)},
        "recovered_in_history": found,
        "cart_after_replay": cart,
        "idempotency_not_cart_clear": "DEPRECATED_RUNNER — see second_audit_acs.ac_b13_04 measured conjunct",
        "new_purchase": {"http": s3, "message": msg(b3)},
    }
    m.dump_case("PB-B13-AC4", detail)
    return expect(ok, detail, "PB-B13-AC4", "idempotent + history recover + not cart-clear")


def ac_b13_05(env, fx):
    m.reset_ns(env)
    ta, tb, s, p = fx["tokens"]["A"], fx["tokens"]["B"], fx["tokens"]["S"], fx["products"]
    m.align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    ca = m.cart_add(env, ta, p["P-ON-1"], "1")
    cb = m.cart_add(env, tb, p["P-ON-1"], "1")
    _, ba = m.confirm(env, ta, [ca])
    _, bb = m.confirm(env, tb, [cb])
    ta_tok, tb_tok = ba["data"]["confirmationToken"], bb["data"]["confirmationToken"]
    ka, kb = new_key(), new_key()

    def a():
        return m.submit_order(env, ta, ta_tok, ka)

    def b():
        return m.submit_order(env, tb, tb_tok, kb)

    race = m.barrier_dual(a, b, "simultaneous")
    stock = m.db_stock(env, p["P-ON-1"])
    placed = len(m.db_orders(env, "b032_buyer_a")) + len(m.db_orders(env, "b032_buyer_b"))
    codes = []
    for side in ("A", "B"):
        r = race[side].get("result")
        codes.append(r[0] if isinstance(r, tuple) else 0)

    # lock-before vs lock-after mutate during submit
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = m.cart_add(env, ta, p["P-ON-10"], "2")
    _, cb = m.confirm(env, ta, [cid])
    token = cb["data"]["confirmationToken"]
    # lock-BEFORE: patch qty before submit starts
    http_json("PATCH", f"{base_url(env)}/api/me/cart/items/{cid}", {"quantity": "4"}, auth(ta))
    before_c, before_b, _ = m.submit_order(env, ta, token)
    # lock-AFTER: hold TX and patch/delete while held
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    c_extra = m.cart_add(env, ta, p["P-ON-5"], "1")  # unselected later
    _, cb = m.confirm(env, ta, [cid])
    token = cb["data"]["confirmationToken"]
    m.clear_probe(env)
    set_control(env, fail_phase=None, probe=True, hold_seconds=3)
    mut = {}

    def sub():
        mut["submit"] = m.submit_order(env, ta, token)

    def mutate():
        deadline = time.time() + 8
        while time.time() < deadline:
            if any("order_created" in x for x in m.probe_phases(env)):
                break
            time.sleep(0.05)
        mut["patch"] = http_json(
            "PATCH",
            f"{base_url(env)}/api/me/cart/items/{cid}",
            {"quantity": "9"},
            auth(ta),
            timeout=30,
        )
        mut["add"] = http_json(
            "POST",
            f"{base_url(env)}/api/me/cart/items",
            {"productId": p["P-ON-5"]},
            auth(ta, new_key()),
            timeout=30,
        )

    t1 = threading.Thread(target=sub)
    t2 = threading.Thread(target=mutate)
    t1.start()
    time.sleep(0.15)
    t2.start()
    t1.join(30)
    t2.join(30)
    set_control(env, fail_phase=None, probe=False, hold_seconds=0)
    orders = m.db_orders(env, "b032_buyer_a")
    items = m.db_order_items(env, orders[0]["id"]) if orders else []
    order_qty = str(items[0]["quantity"]) if items else None
    cart_after = m.db_cart(env, "b032_buyer_a")
    # offline reject
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(s))
    co, bo, _, _ = m.place_order(env, ta, [cid])

    ok = (
        placed == 1
        and stock == "0"
        and 201 in codes
        and any(c >= 400 for c in codes)
        and msg(before_b) == "确认信息已变化，请重新确认"
        and len(orders) == 1
        and order_qty == "1"  # lock-after patch did not inflate order
        and co >= 400
        and "已下架" in nested_msgs(bo)
    )
    detail = {
        "oversell_race": redact(race),
        "stock": stock,
        "placed": placed,
        "lock_before_mutate": {"http": before_c, "message": msg(before_b)},
        "lock_after_mutate": {
            "submit": redact(mut.get("submit")),
            "patch": redact(mut.get("patch")),
            "add": redact(mut.get("add")),
            "order_qty": order_qty,
            "cart_after": cart_after,
        },
        "offline_submit": {"http": co, "message": msg(bo), "nested": nested_msgs(bo)},
    }
    m.dump_case("PB-B13-AC5", detail)
    return expect(ok, detail, "PB-B13-AC5", "no oversell + lock before/after mutate + offline")


def run_screenshots(env, fx):
    """Final screenshot pass for remaining UI (clear-cart, product detail). AC-specific shots already taken."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    seller_pwd = env.get("B032_SELLER_PASSWORD", "")
    # ensure cart has items for clear-cart confirm UI
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    m.align_product(env, fx["tokens"]["S"], fx["products"]["P-ON-10"], PRODUCTS["P-ON-10"])
    m.cart_add(env, ta, fx["products"]["P-ON-10"], "1")
    js = f"""
const {{ chromium }} = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {{
  const fe = {json.dumps(fe_url(env))};
  const out = {{ok:false, shots:[]}};
  const browser = await chromium.launch({{headless:true}});
  try {{
    const page = await browser.newPage({{viewport:{{width:1280,height:900}}}});
    await page.goto(fe + '/login', {{waitUntil:'networkidle'}});
    await page.locator('#username').fill('b032_buyer_a');
    await page.locator('#password').fill('B032-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{timeout:15000}});
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b03-after-login.png'))}, fullPage:true}});
    out.shots.push('b03-after-login.png');

    const pid = {json.dumps(str(fx['products']['P-ON-10']))};
    await page.goto(fe + '/products/' + pid, {{waitUntil:'networkidle'}});
    await page.waitForTimeout(800);
    const directBuy = await page.getByRole('button', {{ name: /立即购买|直接下单/ }}).count();
    const addCart = await page.getByRole('button', {{ name: /加入购物车/ }}).count();
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-product-detail-no-direct-buy.png'))}, fullPage:true}});
    out.shots.push('b12-product-detail-no-direct-buy.png');
    out.detail = {{directBuy, addCart}};

    await page.goto(fe + '/me/cart', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(600);
    await page.getByRole('button', {{ name: /清空购物车/ }}).click();
    const clearModal = page.locator('.ant-modal').filter({{ hasText: '确定清空购物车' }});
    await clearModal.waitFor({{ state: 'visible', timeout: 10000 }});
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-clear-cart-confirm.png'))}, fullPage:true}});
    out.shots.push('b12-clear-cart-confirm.png');

    // verify required shots exist and confirm≠cart
    const fs = require('fs');
    const crypto = require('crypto');
    const hash = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
    const cart = {json.dumps(str(SHOTS/'b12-cart-selection.png'))};
    const conf = {json.dumps(str(SHOTS/'b12-checkout-confirm.png'))};
    const hist = {json.dumps(str(SHOTS/'b03-order-history.png'))};
    const adm = {json.dumps(str(SHOTS/'b03-admin-orders.png'))};
    out.required = {{
      cart: fs.existsSync(cart),
      confirm: fs.existsSync(conf),
      history: fs.existsSync(hist),
      admin: fs.existsSync(adm),
      cart_confirm_distinct: fs.existsSync(cart) && fs.existsSync(conf) && hash(cart) !== hash(conf),
    }};
    out.ok = out.required.cart && out.required.confirm && out.required.history && out.required.admin && out.required.cart_confirm_distinct && directBuy === 0 && addCart > 0;
  }} catch(e) {{ out.error = String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
"""
    return run_node(js, "ui_screenshots_final")


OVERRIDES = {
    "ac_b01_02": ac_b01_02,
    "ac_b01_03": ac_b01_03,
    "ac_b02_02": ac_b02_02,
    "ac_b02_04": ac_b02_04,
    "ac_b02_05": ac_b02_05,
    "ac_b03_03": ac_b03_03,
    "ac_b03_05": ac_b03_05,
    "ac_b12_03": ac_b12_03,
    "ac_b12_04": ac_b12_04,
    "ac_b13_01": ac_b13_01,
    "ac_b13_02": ac_b13_02,
    "ac_b13_03": ac_b13_03,
    "ac_b13_04": ac_b13_04,
    "ac_b13_05": ac_b13_05,
}
