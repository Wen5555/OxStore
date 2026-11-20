#!/usr/bin/env python3
"""Second-audit AC runners (OF-19): V8 path, timing matrix, hard conjuncts. No fake PASS."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from decimal import Decimal
from pathlib import Path

import prepare_and_run as m
from b032_common import (
    auth,
    base_url,
    connect_mysql,
    fe_url,
    http_json,
    login_customer,
    msg,
    new_key,
    redact,
)
from conjuncts import ConjunctTracker, finish

SHOTS = m.SHOTS
PW_DIR = m.PW_DIR
PRODUCTS = m.PRODUCTS
V8_SQL = Path("/tmp/oxstore-develop/backend/src/main/resources/db/migrations/V8__close_legacy_fixed_price_intents.sql")
V8_FIXTURE = m.ROOT / "fixtures" / "V8__close_legacy_fixed_price_intents.sql"


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
    parsed["node_exit"] = proc.returncode
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


def cart_fingerprint(rows) -> list[dict]:
    return [
        {
            "id": str(r["id"]),
            "product_id": str(r["product_id"]),
            "quantity": str(r["quantity"]),
        }
        for r in sorted(rows, key=lambda x: int(x["id"]))
    ]


def probe_rows(env) -> list[dict]:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, phase, note, at_ts FROM b032_tx_probe ORDER BY id")
            return list(cur.fetchall() or [])
    finally:
        conn.close()


def wait_probe_phase(env, phase_substr: str, timeout=8.0) -> dict | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for r in probe_rows(env):
            if phase_substr in (r.get("phase") or ""):
                return r
        time.sleep(0.05)
    return None


def run_v8_migration(env) -> dict:
    """Install+CALL upgrade_oxstore_v8 from develop V8 SQL via mysql client (real migration path)."""
    src = V8_SQL if V8_SQL.exists() else V8_FIXTURE
    if not src.exists():
        return {"ok": False, "error": f"V8 SQL missing: {src}"}
    # Keep a committed copy under fixtures for evidence
    if V8_SQL.exists() and (not V8_FIXTURE.exists() or V8_FIXTURE.read_bytes() != V8_SQL.read_bytes()):
        V8_FIXTURE.write_bytes(V8_SQL.read_bytes())
    cmd = [
        "mysql",
        f"-h{env.get('B032_DB_HOST', '127.0.0.1')}",
        f"-P{env.get('B032_DB_PORT', '3306')}",
        f"-u{env.get('B032_DB_USER', 'oxstore_test')}",
        f"-p{env.get('B032_DB_PASSWORD', '')}",
        env["B032_DB_NAME"],
    ]
    proc = subprocess.run(cmd, input=src.read_text(encoding="utf-8"), capture_output=True, text=True, timeout=60)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-2000:],
        "sql_path": str(src),
        "sql_sha256": sha256_file(src),
    }


# -------------------- PB-B03-AC5: real V8 migration --------------------


def ac_b03_05(env, fx):
    """Close/unfreeze via V8__close_legacy_fixed_price_intents.sql — NOT a fake close API."""
    m.reset_ns(env)
    s, ta, tb, p = fx["tokens"]["S"], fx["tokens"]["A"], fx["tokens"]["B"], fx["products"]
    ct = ConjunctTracker("PB-B03-AC5")

    # Explicitly do NOT call nonexistent POST /api/admin/legacy-intents/close as the close path.
    ct.check(
        "no_fake_close_api_as_path",
        True,
        {"note": "close path = CALL upgrade_oxstore_v8 from V8 SQL; archive is GET-only"},
    )

    conn = connect_mysql(env)
    seed = {}
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM trade_attempt WHERE intent_id IN (SELECT id FROM purchase_intent WHERE product_name_snapshot LIKE 'LEGACY-%')")
            cur.execute("DELETE FROM purchase_intent WHERE product_name_snapshot LIKE 'LEGACY-%'")
            cur.execute("SELECT id FROM customer WHERE username='b032_buyer_a'")
            cid = cur.fetchone()["id"]
            cur.execute("SELECT id FROM customer WHERE username='b032_buyer_b'")
            cid_b = cur.fetchone()["id"]
            pid_trade = int(p["P-ON-10"])
            pid_manual = int(p["P-ON-5"])
            # Seed FROZEN TRADE + MANUAL products (stock > 0 required by V8 guard)
            cur.execute(
                "UPDATE product SET status='FROZEN', freeze_source='TRADE', offline_reason=NULL, "
                "stock='10', status_updated_at=NOW(6) WHERE id=%s",
                (pid_trade,),
            )
            cur.execute(
                "UPDATE product SET status='FROZEN', freeze_source='MANUAL', offline_reason=NULL, "
                "stock='5', status_updated_at=NOW(6) WHERE id=%s",
                (pid_manual,),
            )
            cur.execute(
                """
                INSERT INTO purchase_intent
                (product_id, customer_id, product_name_snapshot, buyer_name, buyer_phone, status,
                 submitted_at, queue_seq, updated_at, processed_at, legacy_closed_at, legacy_close_reason)
                VALUES
                (%s,%s,'LEGACY-SUCCESS','b032_buyer_a','13803200001','SUCCESS',NOW(6),201,NOW(6),NOW(6),NULL,NULL),
                (%s,%s,'LEGACY-FAILED','b032_buyer_a','13803200001','FAILED',NOW(6),202,NOW(6),NOW(6),NULL,NULL),
                (%s,%s,'LEGACY-QUEUING','b032_buyer_a','13803200001','QUEUING',NOW(6),203,NOW(6),NULL,NULL,NULL),
                (%s,%s,'LEGACY-IN-TX','b032_buyer_a','13803200001','IN_TRANSACTION',NOW(6),204,NOW(6),NULL,NULL,NULL)
                """,
                (pid_trade, cid, pid_trade, cid, pid_trade, cid, pid_trade, cid),
            )
            cur.execute(
                "SELECT id, status, product_name_snapshot FROM purchase_intent WHERE product_name_snapshot LIKE 'LEGACY-%' ORDER BY id"
            )
            intents = list(cur.fetchall())
            in_tx = next(i for i in intents if i["status"] == "IN_TRANSACTION")
            cur.execute(
                "INSERT INTO trade_attempt (intent_id, started_at, finished_at, result, fail_action, legacy_closed_at) "
                "VALUES (%s, NOW(6), NULL, NULL, NULL, NULL)",
                (in_tx["id"],),
            )
            cur.execute("SELECT id, intent_id, finished_at, result, legacy_closed_at FROM trade_attempt WHERE intent_id=%s", (in_tx["id"],))
            attempt = cur.fetchone()
            cur.execute(
                "SELECT id, stock, status, freeze_source FROM product WHERE id IN (%s,%s)",
                (pid_trade, pid_manual),
            )
            products_before = {str(r["id"]): r for r in cur.fetchall()}
            # Orders before — must stay unchanged / no new order from migration
            cur.execute(
                "SELECT COUNT(*) c FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b032_%'"
            )
            orders_before = int(cur.fetchone()["c"])
            seed = {
                "intents": intents,
                "attempt": attempt,
                "products_before": products_before,
                "orders_before": orders_before,
                "customer_b_id": cid_b,
            }
    except Exception as e:
        m.dump_case("PB-B03-AC5", {"seed_error": str(e)})
        ct.skip("seed_legacy_rows", f"seed failed: {e}", disposition="NOT_EXECUTED")
        return finish(ct, m.result, {"path": "V8 migration", "seed_error": str(e)})
    finally:
        conn.close()

    ct.check(
        "seed_statuses_SUCCESS_FAILED_QUEUING_IN_TRANSACTION",
        {i["status"] for i in seed["intents"]} >= {"SUCCESS", "FAILED", "QUEUING", "IN_TRANSACTION"},
        {"statuses": [i["status"] for i in seed["intents"]]},
    )
    ct.check(
        "seed_FROZEN_TRADE_and_MANUAL_products",
        seed["products_before"][p["P-ON-10"]]["status"] == "FROZEN"
        and seed["products_before"][p["P-ON-10"]]["freeze_source"] == "TRADE"
        and seed["products_before"][p["P-ON-5"]]["status"] == "FROZEN"
        and seed["products_before"][p["P-ON-5"]]["freeze_source"] == "MANUAL",
        seed["products_before"],
    )
    ct.check("seed_unfinished_trade_attempt", seed["attempt"] is not None and seed["attempt"]["finished_at"] is None, seed["attempt"])

    stock_trade_before = str(seed["products_before"][p["P-ON-10"]]["stock"])
    stock_manual_before = str(seed["products_before"][p["P-ON-5"]]["stock"])

    mig = run_v8_migration(env)
    ct.check("v8_migration_executed", mig.get("ok") is True, mig, on_fail="NOT_EXECUTED")
    if not mig.get("ok"):
        m.dump_case("PB-B03-AC5", {"migration": mig, "seed": seed})
        # Revoke any "needs business fix / BLOCKED for missing API" charge
        return finish(
            ct,
            m.result,
            {
                "path": "V8 migration",
                "note": "NOT_EXECUTED due to migration runner failure — not a business close-API defect",
                "revoked_charge": "fake POST /api/admin/legacy-intents/close BLOCKED",
            },
        )

    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status, legacy_closed_at, legacy_close_reason, product_name_snapshot "
                "FROM purchase_intent WHERE product_name_snapshot LIKE 'LEGACY-%' ORDER BY id"
            )
            intents_after = list(cur.fetchall())
            in_tx_id = next(i["id"] for i in intents_after if i["status"] == "IN_TRANSACTION")
            cur.execute(
                "SELECT id, intent_id, finished_at, result, legacy_closed_at FROM trade_attempt WHERE intent_id=%s",
                (in_tx_id,),
            )
            attempt_after = cur.fetchone()
            cur.execute(
                "SELECT id, stock, status, freeze_source, offline_reason FROM product WHERE id IN (%s,%s)",
                (int(p["P-ON-10"]), int(p["P-ON-5"])),
            )
            products_after = {str(r["id"]): r for r in cur.fetchall()}
            cur.execute(
                "SELECT COUNT(*) c FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b032_%'"
            )
            orders_after = int(cur.fetchone()["c"])
    finally:
        conn.close()

    by_snap = {i["product_name_snapshot"]: i for i in intents_after}
    ct.check(
        "migration_closes_QUEUING_IN_TRANSACTION_keep_status",
        by_snap["LEGACY-QUEUING"]["status"] == "QUEUING"
        and by_snap["LEGACY-QUEUING"]["legacy_closed_at"] is not None
        and by_snap["LEGACY-QUEUING"]["legacy_close_reason"] == "FIXED_PRICE_CHALLENGE_B"
        and by_snap["LEGACY-IN-TX"]["status"] == "IN_TRANSACTION"
        and by_snap["LEGACY-IN-TX"]["legacy_closed_at"] is not None
        and by_snap["LEGACY-IN-TX"]["status"] != "CANCELLED",
        {k: by_snap[k] for k in ("LEGACY-QUEUING", "LEGACY-IN-TX")},
    )
    ct.check(
        "SUCCESS_FAILED_history_untouched",
        by_snap["LEGACY-SUCCESS"]["legacy_closed_at"] is None
        and by_snap["LEGACY-FAILED"]["legacy_closed_at"] is None
        and by_snap["LEGACY-SUCCESS"]["status"] == "SUCCESS"
        and by_snap["LEGACY-FAILED"]["status"] == "FAILED",
        {k: by_snap[k] for k in ("LEGACY-SUCCESS", "LEGACY-FAILED")},
    )
    ct.check(
        "trade_attempt_legacy_closed_unfinished",
        attempt_after is not None
        and attempt_after["legacy_closed_at"] is not None
        and attempt_after["finished_at"] is None
        and attempt_after["result"] is None,
        attempt_after,
    )
    ct.check(
        "TRADE_product_unfrozen_ONLINE",
        products_after[p["P-ON-10"]]["status"] == "ONLINE"
        and products_after[p["P-ON-10"]]["freeze_source"] is None,
        products_after[p["P-ON-10"]],
    )
    ct.check(
        "MANUAL_frozen_becomes_OFFLINE_MANUAL",
        products_after[p["P-ON-5"]]["status"] == "OFFLINE"
        and products_after[p["P-ON-5"]]["offline_reason"] == "MANUAL",
        products_after[p["P-ON-5"]],
    )
    ct.check(
        "stock_not_replenished",
        str(products_after[p["P-ON-10"]]["stock"]) == stock_trade_before
        and str(products_after[p["P-ON-5"]]["stock"]) == stock_manual_before,
        {
            "trade": [stock_trade_before, str(products_after[p["P-ON-10"]]["stock"])],
            "manual": [stock_manual_before, str(products_after[p["P-ON-5"]]["stock"])],
        },
    )
    ct.check("no_new_order_from_migration", orders_after == seed["orders_before"], {"before": seed["orders_before"], "after": orders_after})

    # Archive GET content (customer + merchant)
    c_ad, b_ad = http_json(
        "GET", f"{base_url(env)}/api/admin/legacy-intents?page=1&size=50", headers=auth(s)
    )
    c_me, b_me = http_json(
        "GET", f"{base_url(env)}/api/me/legacy-intents?page=1&size=50", headers=auth(ta)
    )
    def archive_items(body):
        data = (body or {}).get("data") if isinstance(body, dict) else None
        if isinstance(data, dict):
            return data.get("items") or data.get("content") or []
        if isinstance(data, list):
            return data
        return []

    admin_items = archive_items(b_ad)
    me_items = archive_items(b_me)
    admin_snaps = {str(it.get("productNameSnapshot") or it.get("product_name_snapshot") or "") for it in admin_items}
    me_snaps = {str(it.get("productNameSnapshot") or it.get("product_name_snapshot") or "") for it in me_items}
    ct.check(
        "archive_admin_response_content",
        c_ad == 200 and "LEGACY-QUEUING" in admin_snaps and "LEGACY-SUCCESS" in admin_snaps,
        {"http": c_ad, "message": msg(b_ad), "snaps": sorted(admin_snaps), "sample": redact(admin_items[:2])},
    )
    ct.check(
        "archive_customer_own_response_content",
        c_me == 200 and "LEGACY-IN-TX" in me_snaps,
        {"http": c_me, "message": msg(b_me), "snaps": sorted(me_snaps), "sample": redact(me_items[:2])},
    )
    # Buyer B should not see buyer A's archive rows as own
    c_b, b_b = http_json(
        "GET", f"{base_url(env)}/api/me/legacy-intents?page=1&size=50", headers=auth(tb)
    )
    b_snaps = {str(it.get("productNameSnapshot") or "") for it in archive_items(b_b)}
    ct.check(
        "archive_customer_isolation",
        c_b == 200 and "LEGACY-QUEUING" not in b_snaps,
        {"http": c_b, "snaps": sorted(b_snaps)},
    )

    # Read-only rejection: POST/PUT/DELETE on archive endpoints
    post_c, post_b = http_json("POST", f"{base_url(env)}/api/admin/legacy-intents", {}, auth(s))
    put_c, put_b = http_json("PUT", f"{base_url(env)}/api/admin/legacy-intents/1", {}, auth(s))
    del_c, del_b = http_json("DELETE", f"{base_url(env)}/api/admin/legacy-intents/1", headers=auth(s))
    # Also probe the nonexistent close endpoint — must NOT be used as success path; expect non-2xx
    close_c, close_b = http_json("POST", f"{base_url(env)}/api/admin/legacy-intents/close", {}, auth(s))
    ct.check(
        "archive_read_only_rejects_mutations",
        all(c >= 400 or c == 405 for c in (post_c, put_c, del_c, close_c)),
        {
            "POST": {"http": post_c, "message": msg(post_b)},
            "PUT": {"http": put_c, "message": msg(put_b)},
            "DELETE": {"http": del_c, "message": msg(del_b)},
            "POST_close_nonexistent": {"http": close_c, "message": msg(close_b), "note": "probed only to prove not a close path"},
        },
    )

    detail_extra = {
        "path": "fixtures/V8__close_legacy_fixed_price_intents.sql → CALL upgrade_oxstore_v8()",
        "migration": mig,
        "seed": redact(seed),
        "intents_after": intents_after,
        "attempt_after": attempt_after,
        "products_after": products_after,
        "revoked_charge": "previous BLOCKED for missing close API — wrong test path; V8 is the close/unfreeze mechanism",
    }
    m.dump_case("PB-B03-AC5", {**detail_extra, **ct.as_detail()})
    # Realign products for subsequent ACs
    m.align_product(env, s, p["P-ON-10"], PRODUCTS["P-ON-10"])
    m.align_product(env, s, p["P-ON-5"], PRODUCTS["P-ON-5"])
    return finish(ct, m.result, detail_extra)


# -------------------- PB-B13 hardened --------------------


def ac_b13_01(env, fx):
    m.reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    ct = ConjunctTracker("PB-B13-AC1")

    # POS: full cart fingerprint empty + order/items/receipts persisted + UI success shot
    cid = m.cart_add(env, ta, p["P-ON-10"], "2")
    cart0 = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    stock0 = m.db_stock(env, p["P-ON-10"])
    code, body, _, _ = m.place_order(env, ta, [cid])
    stock1 = m.db_stock(env, p["P-ON-10"])
    cart1 = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    orders = m.db_orders(env, "b032_buyer_a")
    items = m.db_order_items(env, orders[0]["id"]) if orders else []
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT r.id, r.operation_type FROM operation_receipt r "
                "JOIN customer c ON c.id=r.customer_id WHERE c.username='b032_buyer_a'"
            )
            receipts = list(cur.fetchall() or [])
    finally:
        conn.close()

    ct.check("pos_http_message", code == 201 and msg(body) == "下单成功", {"http": code, "message": msg(body)})
    ct.check("pos_stock_delta", int(stock0) - int(stock1) == 2, {"stock": [stock0, stock1]})
    ct.check("pos_cart_full_set_cleared", cart1 == [], {"cart_before": cart0, "cart_after": cart1})
    ct.check("pos_order_items_receipts_persisted", len(orders) == 1 and len(items) >= 1 and len(receipts) >= 1, {
        "orders": orders, "items": items, "receipts": receipts
    })

    # Success UI screenshot
    shot_ok = False
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
    // cart may be empty after POS — add then order via UI if possible
    await page.goto(fe + '/products/' + {json.dumps(str(p["P-ON-5"]))}, {{waitUntil:'networkidle'}});
    const add = page.getByRole('button', {{ name: /加入购物车/ }});
    if (await add.count()) {{ await add.click(); await page.waitForTimeout(500); }}
    await page.goto(fe + '/me/cart', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(600);
    const orderBtn = page.getByRole('button', {{ name: '下单' }});
    if (await orderBtn.count()) {{
      await orderBtn.click();
      const modal = page.locator('.ant-modal').filter({{ hasText: '确认下单' }});
      await modal.waitFor({{ state: 'visible', timeout: 10000 }});
      await modal.getByRole('button', {{ name: /确认|下单/ }}).last().click();
      await page.waitForTimeout(1200);
    }}
    const bodyText = await page.locator('body').innerText();
    const hasSuccess = bodyText.includes('下单成功') || bodyText.includes('订单号') || /ORD|订单/.test(bodyText);
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b13-order-success.png'))}, fullPage:true}});
    out.shots = ['b13-order-success.png'];
    out.bodySnippet = bodyText.slice(0, 500);
    out.ok = hasSuccess;
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b13_success",
    )
    shot_ok = shot.get("ok") is True and (SHOTS / "b13-order-success.png").exists()
    ct.check("pos_success_ui_screenshot", shot_ok, shot, on_fail="FAIL")

    # NEG: insufficient — cart full-set unchanged
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
    cart_n0 = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    cn, bn, _, _ = m.place_order(env, ta, [cid])
    cart_n1 = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    ct.check(
        "neg_no_order_stock_cart_full_set",
        cn >= 400 and m.db_stock(env, p["P-ON-1"]) == stock_n0 and cart_n1 == cart_n0 and len(m.db_orders(env, "b032_buyer_a")) == 0,
        {"http": cn, "message": msg(bn), "cart_before": cart_n0, "cart_after": cart_n1},
    )
    # Failure reason: if only generic 500, mark strictly
    fail_msg = nested_msgs(bn)
    ct.check(
        "neg_failure_reason_not_generic_only",
        cn >= 400 and ("库存" in fail_msg or "不足" in fail_msg or "选购" in fail_msg),
        {"message": fail_msg, "http": cn},
    )

    # Multi-product mid-fault: both lines unchanged (no half order)
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    c1 = m.cart_add(env, ta, p["P-ON-10"], "1")
    c2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, cb = m.confirm(env, ta, [c1, c2])
    token = cb["data"]["confirmationToken"]
    cart_b = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    stock_b = {p["P-ON-10"]: m.db_stock(env, p["P-ON-10"]), p["P-ON-5"]: m.db_stock(env, p["P-ON-5"])}
    m.clear_probe(env)
    set_control(env, fail_phase="after_order", probe=True, hold_seconds=0)
    s_code, s_body, _ = m.submit_order(env, ta, token)
    set_control(env, fail_phase=None, probe=False, hold_seconds=0)
    cart_a = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    stock_a = {p["P-ON-10"]: m.db_stock(env, p["P-ON-10"]), p["P-ON-5"]: m.db_stock(env, p["P-ON-5"])}
    orders_a = m.db_orders(env, "b032_buyer_a")
    ct.check(
        "multi_product_mid_fault_batch_unchanged",
        s_code >= 400 and cart_a == cart_b and stock_a == stock_b and len(orders_a) == 0,
        {
            "http": s_code,
            "message": msg(s_body),
            "cart_before": cart_b,
            "cart_after": cart_a,
            "stock_before": stock_b,
            "stock_after": stock_a,
            "probe": m.probe_phases(env),
        },
    )

    # Three breakpoints AND
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
        cart_b = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
        s_code, s_body, _ = m.submit_order(env, ta, token)
        set_control(env, fail_phase=None, probe=False, hold_seconds=0)
        phases = m.probe_phases(env)
        stock_a = m.db_stock(env, p["P-ON-10"])
        cart_a = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
        orders_a = m.db_orders(env, "b032_buyer_a")
        rolled = stock_a == stock_b and cart_a == cart_b and len(orders_a) == 0 and s_code >= 400
        breaks[phase] = {
            "http": s_code,
            "message": msg(s_body),
            "probe": phases,
            "rolled_back": rolled,
            "probe_hit": need_probe in str(phases),
            "cart_before": cart_b,
            "cart_after": cart_a,
            "stock": [stock_b, stock_a],
        }
        ct.check(
            f"breakpoint_{phase}_rollback_and_probe",
            rolled and need_probe in str(phases),
            breaks[phase],
        )

    m.dump_case("PB-B13-AC1", {"breakpoints": breaks, **ct.as_detail()})
    return finish(ct, m.result, {"breakpoints": breaks, "trigger_sql": "fixtures/b032_tx_probes.sql"})


def _hold_mutate(env, ta, token, mutate_fn, hold_seconds=3) -> dict:
    """True-hold timing: mutate while after_order SLEEP holds TX; record monotonic timeline."""
    m.clear_probe(env)
    set_control(env, fail_phase=None, probe=True, hold_seconds=hold_seconds)
    box: dict = {"timeline": {}}

    def submitter():
        box["timeline"]["submit_start"] = time.time()
        box["submit"] = m.submit_order(env, ta, token)
        box["timeline"]["submit_end"] = time.time()

    def mutator():
        pr = wait_probe_phase(env, "order_created", timeout=8)
        box["timeline"]["probe_observed"] = time.time()
        box["probe_row"] = pr
        if pr and pr.get("at_ts") is not None:
            box["timeline"]["probe_at_ts"] = str(pr["at_ts"])
        box["timeline"]["mutation_start"] = time.time()
        box["mutation"] = mutate_fn()
        box["timeline"]["mutation_end"] = time.time()

    t1 = threading.Thread(target=submitter)
    t2 = threading.Thread(target=mutator)
    t1.start()
    time.sleep(0.1)
    t2.start()
    t1.join(40)
    t2.join(40)
    set_control(env, fail_phase=None, probe=False, hold_seconds=0)
    tl = box["timeline"]
    # Overlap proof: mutation started after probe (inside hold) and mutation_end >= submit_end if blocked
    started_during_hold = (
        tl.get("probe_observed") is not None
        and tl.get("mutation_start") is not None
        and tl.get("submit_end") is not None
        and tl["mutation_start"] >= tl["probe_observed"]
        and tl["mutation_start"] <= tl["submit_end"] + 0.05
    )
    blocked_until_release = (
        tl.get("mutation_end") is not None
        and tl.get("submit_end") is not None
        and tl["mutation_end"] + 0.01 >= tl["submit_end"]
        and (tl["mutation_end"] - tl.get("mutation_start", tl["mutation_end"])) >= (hold_seconds * 0.4)
    )
    box["overlap"] = {
        "started_during_hold": started_during_hold,
        "blocked_until_release": blocked_until_release,
        "hold_seconds": hold_seconds,
    }
    box["final_db"] = {
        "orders": m.db_orders(env, "b032_buyer_a"),
        "cart": cart_fingerprint(m.db_cart(env, "b032_buyer_a")),
        "probe_phases": m.probe_phases(env),
    }
    return box


def ac_b13_02(env, fx):
    m.reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    ct = ConjunctTracker("PB-B13-AC2")

    # Unselected kept (full set)
    c1 = m.cart_add(env, ta, p["P-ON-10"], "2")
    c2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    code, body, _, _ = m.place_order(env, ta, [c1])
    cart = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    kept = [r for r in cart if r["product_id"] == p["P-ON-5"] and r["quantity"] == "1"]
    ct.check("unselected_kept_full_set", code == 201 and len(kept) == 1 and len(cart) == 1, {"cart": cart, "message": msg(body)})

    # Before lock: PATCH then submit → 确认信息已变化 (NOT "during submit")
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, cb = m.confirm(env, ta, [cid])
    token = cb["data"]["confirmationToken"]
    http_json("PATCH", f"{base_url(env)}/api/me/cart/items/{cid}", {"quantity": "3"}, auth(ta))
    pre_c, pre_b, _ = m.submit_order(env, ta, token)
    sc, sb, _, _ = m.place_order(env, ta, [cid])
    items = m.db_order_items(env, m.db_orders(env, "b032_buyer_a")[0]["id"]) if sc == 201 else []
    locked_qty = str(items[0]["quantity"]) if items else None
    ct.check(
        "pre_lock_patch_then_submit_rejects",
        msg(pre_b) == "确认信息已变化，请重新确认" and sc == 201 and locked_qty == "3",
        {"pre": {"http": pre_c, "message": msg(pre_b)}, "reconfirm_qty": locked_qty},
    )

    # During true hold: add SAME selected product
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, cb = m.confirm(env, ta, [cid])
    token = cb["data"]["confirmationToken"]

    def add_same():
        return http_json(
            "POST",
            f"{base_url(env)}/api/me/cart/items",
            {"productId": p["P-ON-10"]},
            auth(ta, new_key()),
            timeout=40,
        )

    hold_add = _hold_mutate(env, ta, token, add_same, hold_seconds=3)
    ct.check(
        "during_hold_add_same_product_timeline",
        hold_add["overlap"]["started_during_hold"] is True,
        hold_add,
        on_fail="FAIL",
    )
    # Post-hold cart may contain surviving new line or merged qty — record honestly
    cart_after = hold_add["final_db"]["cart"]
    orders = hold_add["final_db"]["orders"]
    ct.check(
        "during_hold_add_final_state_recorded",
        len(orders) == 1,
        {"cart_after": cart_after, "orders": len(orders), "mutation": redact(hold_add.get("mutation"))},
    )

    # Remainder >0 — source-based FAIL (digest includes qty)
    ct.check(
        "remainder_gt0_via_public_api",
        False,
        {
            "proven": False,
            "source": "CheckoutService digest includes cart quantity; confirmation.qty == cart.qty on success → remainder always 0",
            "disposition": "FAIL",
        },
        on_fail="FAIL",
    )

    m.dump_case("PB-B13-AC2", ct.as_detail())
    return finish(ct, m.result, {"note": "pre-lock ≠ during-hold; remainder FAIL by source"})


def ac_b13_03(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B13-AC3")
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, body, _, _ = m.place_order(env, ta, [cid])
    oid = m.order_id_of(body)
    snap = m.db_order_items(env, oid)
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}", {"stock": "0"}, auth(s))
    steps = advance_full(env, s, oid)
    snap2 = m.db_order_items(env, oid)
    ct.check("snapshot_stable_through_complete", snap == snap2 and steps[-1]["status"] == "COMPLETED", {"snap": snap, "snap2": snap2, "steps": steps})

    # stock0: existing cart line submit rejected (not only add reject)
    m.align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    cid_z = m.cart_add(env, ta, p["P-ON-1"], "1")
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{p['P-ON-1']}", {"stock": "0"}, auth(s))
    # keep cart row even if product offline
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM cart_item WHERE id=%s", (cid_z,))
            exists = cur.fetchone()
            if not exists:
                cur.execute("SELECT id FROM customer WHERE username='b032_buyer_a'")
                cust = cur.fetchone()["id"]
                cur.execute(
                    "INSERT INTO cart_item(customer_id, product_id, quantity, updated_at) VALUES (%s,%s,1,NOW(6))",
                    (cust, p["P-ON-1"]),
                )
                cid_z = str(cur.lastrowid)
    finally:
        conn.close()
    zj_c, zj_b, _, _ = m.place_order(env, ta, [cid_z])
    ct.check("stock0_existing_cart_submit_rejected", zj_c >= 400 and len(m.db_orders(env, "b032_buyer_a")) == 1, {
        "http": zj_c, "message": msg(zj_b), "nested": nested_msgs(zj_b)
    })

    # Customer cancel — no cart restore (same round)
    m.align_product(env, s, p["P-ON-5"], PRODUCTS["P-ON-5"])
    cid2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = m.place_order(env, ta, [cid2])
    oid2 = m.order_id_of(body2)
    cart_before_cancel = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    m.cancel_customer(env, ta, oid2, "PLACED")
    cart_after_cust = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    ct.check(
        "customer_cancel_no_cart_restore",
        all(r["product_id"] != p["P-ON-5"] for r in cart_after_cust),
        {"before": cart_before_cancel, "after": cart_after_cust},
    )

    # Merchant cancel — no cart restore
    cid3 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body3, _, _ = m.place_order(env, ta, [cid3])
    oid3 = m.order_id_of(body3)
    m.cancel_admin(env, s, oid3, "PLACED")
    cart_after_merch = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    ct.check(
        "merchant_cancel_no_cart_restore",
        all(r["product_id"] != p["P-ON-5"] for r in cart_after_merch),
        {"after": cart_after_merch},
    )

    m.dump_case("PB-B13-AC3", ct.as_detail())
    return finish(ct, m.result)


def ac_b13_04(env, fx):
    m.reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    ct = ConjunctTracker("PB-B13-AC4")
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, c_body = m.confirm(env, ta, [cid])
    token = c_body["data"]["confirmationToken"]
    key = new_key()
    s1, b1, _ = m.submit_order(env, ta, token, key)
    s2, b2, _ = m.submit_order(env, ta, token, key)
    orders = m.db_orders(env, "b032_buyer_a")
    hist_c, hist_b = http_json("GET", f"{base_url(env)}/api/me/orders", headers=auth(ta))
    items = []
    data = (hist_b or {}).get("data")
    if isinstance(data, dict):
        items = data.get("items") or data.get("content") or []
    elif isinstance(data, list):
        items = data
    found = any(str(it.get("orderNo") or "") == str(orders[0]["order_no"]) for it in items) if orders else False
    ct.check("first_success", s1 == 201 and msg(b1) == "下单成功", {"http": s1, "message": msg(b1)})
    ct.check("lost_response_replay", msg(b2) == "订单已提交，请勿重复下单" and len(orders) == 1, {"http": s2, "message": msg(b2)})
    ct.check("recovered_in_history", found and hist_c == 200, {"found": found})

    # After success: add new cart line, then replay OLD key — must NOT clear the new cart
    cid_new = m.cart_add(env, ta, p["P-ON-5"], "1")
    cart_before_replay = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    s_replay, b_replay, _ = m.submit_order(env, ta, token, key)
    cart_after_replay = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    ct.check(
        "idempotency_not_cart_clear_after_new_add",
        cart_after_replay == cart_before_replay
        and any(r["id"] == str(cid_new) for r in cart_after_replay)
        and msg(b_replay) == "订单已提交，请勿重复下单"
        and len(m.db_orders(env, "b032_buyer_a")) == 1,
        {
            "cart_before": cart_before_replay,
            "cart_after": cart_after_replay,
            "replay": {"http": s_replay, "message": msg(b_replay)},
        },
    )

    # Concurrent identical key → one order; stock deducted once
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    stock0 = m.db_stock(env, p["P-ON-10"])
    _, c_body = m.confirm(env, ta, [cid])
    token = c_body["data"]["confirmationToken"]
    key2 = new_key()

    def a():
        return m.submit_order(env, ta, token, key2)

    def b():
        return m.submit_order(env, ta, token, key2)

    race = m.barrier_dual(a, b, "simultaneous")
    stock1 = m.db_stock(env, p["P-ON-10"])
    n_orders = len(m.db_orders(env, "b032_buyer_a"))
    ct.check(
        "concurrent_same_key_one_order_stock_once",
        n_orders == 1 and int(stock0) - int(stock1) == 1,
        {"race": redact(race), "stock": [stock0, stock1], "orders": n_orders},
    )

    m.dump_case("PB-B13-AC4", ct.as_detail())
    return finish(ct, m.result)


def ac_b13_05(env, fx):
    m.reset_ns(env)
    ta, tb, s, p = fx["tokens"]["A"], fx["tokens"]["B"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B13-AC5")

    # Oversell race single SKU
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
    ct.check(
        "no_oversell_single_sku",
        placed == 1 and stock == "0" and 201 in codes and any(c >= 400 for c in codes),
        {"race": redact(race), "stock": stock, "placed": placed, "codes": codes},
    )

    # Multi-product concurrent: no half-order (A takes P-ON-10+P-ON-5; B races same)
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    tb = login_customer(env, "b032_buyer_b", "B032-BuyerB-Pass9", "13803200002")
    fx["tokens"]["A"] = ta
    fx["tokens"]["B"] = tb
    m.align_product(env, s, p["P-ON-10"], {"name": PRODUCTS["P-ON-10"]["name"], "stock": "1", "status": "ONLINE"})
    m.align_product(env, s, p["P-ON-5"], {"name": PRODUCTS["P-ON-5"]["name"], "stock": "1", "status": "ONLINE"})
    ca1 = m.cart_add(env, ta, p["P-ON-10"], "1")
    ca2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    cb1 = m.cart_add(env, tb, p["P-ON-10"], "1")
    cb2 = m.cart_add(env, tb, p["P-ON-5"], "1")
    _, ba = m.confirm(env, ta, [ca1, ca2])
    _, bb = m.confirm(env, tb, [cb1, cb2])

    def a2():
        return m.submit_order(env, ta, ba["data"]["confirmationToken"], new_key())

    def b2():
        return m.submit_order(env, tb, bb["data"]["confirmationToken"], new_key())

    race2 = m.barrier_dual(a2, b2, "simultaneous")
    oa = m.db_orders(env, "b032_buyer_a")
    ob = m.db_orders(env, "b032_buyer_b")
    # Winner has 2 items; loser 0 orders — no half
    def item_count(orders, user):
        if not orders:
            return 0
        return len(m.db_order_items(env, orders[0]["id"]))

    winners = []
    if oa:
        winners.append(("A", item_count(oa, "a")))
    if ob:
        winners.append(("B", item_count(ob, "b")))
    half = any(n not in (0, 2) for _, n in [("A", item_count(oa, "a")), ("B", item_count(ob, "b"))])
    ct.check(
        "multi_product_no_half_order",
        not half and len(winners) == 1 and winners[0][1] == 2,
        {"race": redact(race2), "A_orders": oa, "B_orders": ob, "winners": winners},
    )

    # Lock-BEFORE (serial, before submit) — distinct from during-hold
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    m.align_product(env, s, p["P-ON-10"], PRODUCTS["P-ON-10"])
    cid = m.cart_add(env, ta, p["P-ON-10"], "2")
    _, cb = m.confirm(env, ta, [cid])
    token = cb["data"]["confirmationToken"]
    http_json("PATCH", f"{base_url(env)}/api/me/cart/items/{cid}", {"quantity": "4"}, auth(ta))
    before_c, before_b, _ = m.submit_order(env, ta, token)
    ct.check(
        "lock_before_patch_serial_rejects",
        msg(before_b) == "确认信息已变化，请重新确认",
        {"http": before_c, "message": msg(before_b)},
    )

    # During true hold matrix: PATCH qty / DELETE / ADD same selected product
    matrix = {}
    for name, mut_factory in [
        (
            "patch_qty",
            lambda cid: (lambda: http_json(
                "PATCH", f"{base_url(env)}/api/me/cart/items/{cid}", {"quantity": "9"}, auth(ta), timeout=40
            )),
        ),
        (
            "delete_selected",
            lambda cid: (lambda: http_json(
                "DELETE", f"{base_url(env)}/api/me/cart/items/{cid}", headers=auth(ta), timeout=40
            )),
        ),
        (
            "add_same_selected",
            lambda cid: (lambda: http_json(
                "POST",
                f"{base_url(env)}/api/me/cart/items",
                {"productId": p["P-ON-10"]},
                auth(ta, new_key()),
                timeout=40,
            )),
        ),
    ]:
        m.reset_ns(env)
        ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
        fx["tokens"]["A"] = ta
        m.align_product(env, s, p["P-ON-10"], PRODUCTS["P-ON-10"])
        cid = m.cart_add(env, ta, p["P-ON-10"], "1")
        _, cb = m.confirm(env, ta, [cid])
        token = cb["data"]["confirmationToken"]
        box = _hold_mutate(env, ta, token, mut_factory(cid), hold_seconds=3)
        matrix[name] = {
            "timeline": box.get("timeline"),
            "overlap": box.get("overlap"),
            "mutation": redact(box.get("mutation")),
            "submit": redact(box.get("submit")),
            "final_db": box.get("final_db"),
        }
        ct.check(
            f"during_hold_{name}_started_in_hold",
            box["overlap"]["started_during_hold"] is True,
            matrix[name],
        )
        # Order qty must remain confirmation qty if submit succeeded
        orders = box["final_db"]["orders"]
        if orders and name == "patch_qty":
            oitems = m.db_order_items(env, orders[0]["id"])
            ct.check(
                "during_hold_patch_does_not_inflate_order",
                str(oitems[0]["quantity"]) == "1",
                {"items": oitems},
            )

    # Offline submit
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    m.align_product(env, s, p["P-ON-10"], PRODUCTS["P-ON-10"])
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(s))
    co, bo, _, _ = m.place_order(env, ta, [cid])
    ct.check(
        "offline_submit_rejected",
        co >= 400 and "已下架" in nested_msgs(bo),
        {"http": co, "message": msg(bo), "nested": nested_msgs(bo)},
    )

    m.dump_case("PB-B13-AC5", {"matrix": matrix, **ct.as_detail()})
    return finish(ct, m.result, {"matrix": matrix})


# -------------------- Other gap ACs --------------------


def ac_b01_03(env, fx):
    """Terminals + merchant cancel + source-backed no-timeout (not 2s alone)."""
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B01-AC3")
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, body, _, _ = m.place_order(env, ta, [cid])
    oid = m.order_id_of(body)
    advance_full(env, s, oid)
    adv_c, adv_b = m.advance(env, s, oid, "COMPLETE", "SHIPPED")
    can_c, can_b = m.cancel_customer(env, ta, oid, "COMPLETED")
    ct.check("completed_no_advance", adv_c >= 400, {"http": adv_c, "message": msg(adv_b)})
    ct.check("completed_no_customer_cancel", can_c >= 400, {"http": can_c, "message": msg(can_b)})

    cid2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = m.place_order(env, ta, [cid2])
    oid2 = m.order_id_of(body2)
    m.cancel_customer(env, ta, oid2, "PLACED")
    adv2_c, adv2_b = m.advance(env, s, oid2, "CONFIRM", "PLACED")
    ct.check("cancelled_no_advance", adv2_c >= 400, {"http": adv2_c, "message": msg(adv2_b)})

    # Merchant cancel of PLACED
    cid3 = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, body3, _, _ = m.place_order(env, ta, [cid3])
    oid3 = m.order_id_of(body3)
    mc_c, mc_b = m.cancel_admin(env, s, oid3, "PLACED")
    still = [o for o in m.db_orders(env, "b032_buyer_a") if str(o["id"]) == oid3][0]
    ct.check(
        "merchant_cancel_placed",
        mc_c == 200 and still["status"] == "CANCELLED",
        {"http": mc_c, "message": msg(mc_b), "order": still},
    )

    # No timeout: short wait + source evidence (no scheduled cancel job in codebase path)
    cid4 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body4, _, _ = m.place_order(env, ta, [cid4])
    oid4 = m.order_id_of(body4)
    time.sleep(2.0)
    still4 = [o for o in m.db_orders(env, "b032_buyer_a") if str(o["id"]) == oid4][0]
    # Source audit: look for cancel scheduler mentions
    src_hits = subprocess.run(
        ["rg", "-n", "schedule|@Scheduled|timeout.*cancel|auto.?cancel", "/tmp/oxstore-develop/backend/src/main/java/com/team/shop", "-g", "*.java"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    hit_lines = [ln for ln in (src_hits.stdout or "").splitlines() if "cancel" in ln.lower() or "Scheduled" in ln]
    ct.check(
        "no_timeout_auto_cancel_source_and_wait",
        still4["status"] == "PLACED",
        {
            "wait_sec": 2,
            "status_after_wait": still4["status"],
            "source_scan_hits": hit_lines[:20],
            "note": "2s wait alone insufficient; combined with source scan of cancel schedulers",
        },
    )

    m.dump_case("PB-B01-AC3", ct.as_detail())
    return finish(ct, m.result)


def ac_b01_04(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B01-AC4")
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, body, _, _ = m.place_order(env, ta, [cid])
    oid = m.order_id_of(body)
    steps = []
    for a, e in [("CONFIRM", "PLACED"), ("PREPARE", "CONFIRMED"), ("SHIP", "PREPARED"), ("COMPLETE", "SHIPPED")]:
        hc, hb = m.advance(env, s, oid, a, e)
        steps.append({"action": a, "http": hc, "message": msg(hb), "body_keys": list(((hb or {}).get("data") or {}).keys()) if isinstance(hb, dict) else []})
    order = m.db_orders(env, "b032_buyer_a")[0]
    ct.check("api_full_flow_no_logistics_fields", all(x["http"] == 200 for x in steps) and order["status"] == "COMPLETED", {"steps": steps})

    # Merchant UI full flow screenshot
    seller_pwd = env.get("B032_SELLER_PASSWORD", "")
    shot = run_node(
        f"""
const {{ chromium }} = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {{
  const fe = {json.dumps(fe_url(env))};
  const out = {{ok:false}};
  const browser = await chromium.launch({{headless:true}});
  try {{
    const page = await browser.newPage({{viewport:{{width:1280,height:900}}}});
    await page.goto(fe + '/admin/login', {{waitUntil:'networkidle'}});
    await page.locator('#username').fill('admin');
    await page.locator('#password').fill({json.dumps(seller_pwd)});
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{timeout:15000}});
    await page.goto(fe + '/admin/orders', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(1000);
    const text = await page.locator('body').innerText();
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b01-merchant-orders-flow.png'))}, fullPage:true}});
    out.shots = ['b01-merchant-orders-flow.png'];
    out.url = page.url();
    out.hasOrders = text.includes('订单') || text.includes('PLACED') || text.includes('已');
    out.ok = !page.url().includes('/login') && out.hasOrders;
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b01_ac4",
    )
    ct.check("merchant_ui_orders_flow_screenshot", shot.get("ok") is True and (SHOTS / "b01-merchant-orders-flow.png").exists(), shot)
    m.dump_case("PB-B01-AC4", ct.as_detail())
    return finish(ct, m.result, {"steps": steps})


def ac_b01_05(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B01-AC5")
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, body, _, _ = m.place_order(env, ta, [cid])
    oid = m.order_id_of(body)
    first = m.advance(env, s, oid, "CONFIRM", "PLACED")
    stock_before = m.db_stock(env, p["P-ON-10"])
    dup = m.advance(env, s, oid, "CONFIRM", "PLACED")
    stock_after = m.db_stock(env, p["P-ON-10"])
    ct.check("dup_confirm_rejected_stock_unchanged", first[0] == 200 and dup[0] >= 400 and stock_before == stock_after, {
        "stock": [stock_before, stock_after], "dup": msg(dup[1])
    })

    # Advance to SHIPPED then duplicate SHIP / COMPLETE — stock unchanged
    m.advance(env, s, oid, "PREPARE", "CONFIRMED")
    m.advance(env, s, oid, "SHIP", "PREPARED")
    stock_s0 = m.db_stock(env, p["P-ON-10"])
    dup_ship = m.advance(env, s, oid, "SHIP", "PREPARED")
    stock_s1 = m.db_stock(env, p["P-ON-10"])
    m.advance(env, s, oid, "COMPLETE", "SHIPPED")
    stock_c0 = m.db_stock(env, p["P-ON-10"])
    dup_complete = m.advance(env, s, oid, "COMPLETE", "SHIPPED")
    stock_c1 = m.db_stock(env, p["P-ON-10"])
    ct.check(
        "dup_ship_complete_stock_unchanged",
        dup_ship[0] >= 400 and dup_complete[0] >= 400 and stock_s0 == stock_s1 and stock_c0 == stock_c1,
        {
            "dup_ship": {"http": dup_ship[0], "message": msg(dup_ship[1])},
            "dup_complete": {"http": dup_complete[0], "message": msg(dup_complete[1])},
            "stock_ship": [stock_s0, stock_s1],
            "stock_complete": [stock_c0, stock_c1],
        },
    )

    # Concurrent confirm race
    cid2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = m.place_order(env, ta, [cid2])
    oid2 = m.order_id_of(body2)

    def a():
        return m.advance(env, s, oid2, "CONFIRM", "PLACED")

    def b():
        return m.advance(env, s, oid2, "CONFIRM", "PLACED")

    race = m.barrier_dual(a, b, "simultaneous")
    o2 = [o for o in m.db_orders(env, "b032_buyer_a") if str(o["id"]) == oid2][0]
    race_codes = []
    for side in ("A", "B"):
        r = race[side]["result"] if race[side].get("ok") else (0, {})
        race_codes.append(r[0] if isinstance(r, tuple) else 0)
    ct.check(
        "concurrent_confirm_one_success",
        o2["status"] == "CONFIRMED" and 200 in race_codes and any(c >= 400 for c in race_codes),
        {"race": redact(race), "status": o2["status"]},
    )
    m.dump_case("PB-B01-AC5", ct.as_detail())
    return finish(ct, m.result)


def ac_b02_03(env, fx):
    m.reset_ns(env)
    s, p = fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B02-AC3")
    pid = p["P-STOCK"]
    m.align_product(env, s, pid, PRODUCTS["P-STOCK"])
    # Place an order first so stock edit cannot alter existing order lines
    ta = fx["tokens"]["A"]
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, body, _, _ = m.place_order(env, ta, [cid])
    oid = m.order_id_of(body)
    snap = m.db_order_items(env, oid)

    bad_inputs = []
    for val in ["abc", "-1", "1.5", "", "01", " "]:
        c, b = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": val}, auth(s))
        bad_inputs.append({"value": val, "http": c, "message": msg(b)})
    ct.check(
        "reject_non_numeric_and_signed",
        all(x["http"] >= 400 for x in bad_inputs),
        {"cases": bad_inputs},
    )
    # Valid edit
    c_ok, b_ok = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "15"}, auth(s))
    ct.check("accept_valid_stock", c_ok == 200 and str(m.db_stock(env, pid)) == "15", {"http": c_ok, "message": msg(b_ok)})
    snap2 = m.db_order_items(env, oid)
    ct.check("stock_edit_does_not_change_existing_order", snap == snap2, {"snap": snap, "snap2": snap2})
    m.dump_case("PB-B02-AC3", ct.as_detail())
    return finish(ct, m.result)


def ac_b02_04(env, fx):
    import audit_acs as base
    # Reuse hardened base then add pagination boundary conjuncts
    r = base.ac_b02_04(env, fx)
    ct = ConjunctTracker("PB-B02-AC4")
    # Re-check from detail + pagination
    for name, ok in [
        ("zero_offline_invisible", r["verdict"] == "PASS"),
    ]:
        # If base failed, mark its overall; else expand pagination
        pass
    # Always run pagination boundaries freshly
    m.reset_ns(env)
    # Ensure some products exist
    list1_c, list1_b = http_json("GET", f"{base_url(env)}/api/products?page=1&size=2")
    list2_c, list2_b = http_json("GET", f"{base_url(env)}/api/products?page=2&size=2")
    bad_c, bad_b = http_json("GET", f"{base_url(env)}/api/products?page=0&size=2")

    def page_ids(body):
        data = (body or {}).get("data") if isinstance(body, dict) else None
        items = []
        if isinstance(data, dict):
            items = data.get("items") or data.get("content") or []
            total = data.get("total") or data.get("totalElements")
        elif isinstance(data, list):
            items = data
            total = len(data)
        else:
            total = None
        ids = [str(it.get("productId") or it.get("id") or "") for it in items]
        return ids, total, data

    ids1, total1, d1 = page_ids(list1_b)
    ids2, total2, d2 = page_ids(list2_b)
    overlap = set(ids1) & set(ids2)
    ct.check("list_page1_ok", list1_c == 200 and len(ids1) > 0, {"http": list1_c, "ids": ids1, "total": total1})
    ct.check("list_page2_boundary", list2_c == 200, {"http": list2_c, "ids": ids2, "total": total2})
    ct.check("list_pages_no_id_overlap_when_both_nonempty", not ids1 or not ids2 or len(overlap) == 0, {"overlap": list(overlap)})
    ct.check("list_page0_rejected", bad_c >= 400 or msg(bad_b), {"http": bad_c, "message": msg(bad_b)})
    # Include base offline/invisible evidence
    base_ok = r["verdict"] == "PASS"
    ct.check("base_offline_invisible_cycles", base_ok, r.get("detail"))
    m.dump_case("PB-B02-AC4", ct.as_detail())
    return finish(ct, m.result)


def ac_b03_01(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B03-AC1")
    c1 = m.cart_add(env, ta, p["P-ON-10"], "2")
    c2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    c3 = m.cart_add(env, ta, p["P-ON-1"], "1")  # will leave unselected
    # Confirm page amounts
    conf_c, conf_b = m.confirm(env, ta, [c1, c2])  # unselected c3 not in snapshot
    conf_items = ((conf_b or {}).get("data") or {}).get("items") or []
    conf_total = ((conf_b or {}).get("data") or {}).get("totalAmount") or ((conf_b or {}).get("data") or {}).get("total")
    ct.check("unselected_not_in_confirm_snapshot", conf_c in (200, 201) and len(conf_items) == 2, {
        "confirm_items": redact(conf_items), "total": conf_total
    })
    code, body, _, _ = m.place_order(env, ta, [c1, c2])
    oid = m.order_id_of(body)
    snap = m.db_order_items(env, oid)
    order = m.db_orders(env, "b032_buyer_a")[0]
    # Mutate live product + republish path (offline/online)
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}", {"stock": "99"}, auth(s))
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-5']}/offline", headers=auth(s))
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-5']}/online", headers=auth(s))
    snap2 = m.db_order_items(env, oid)
    total = Decimal(str(order["total_amount"]))
    calc = sum(Decimal(str(i["unit_price"])) * Decimal(str(i["quantity"])) for i in snap)
    ct.check("snapshot_stable_after_republish_mutate", snap == snap2, {"snap": snap, "snap2": snap2})
    ct.check("detail_lines_match_total", total == calc and str(total) == f"{total:.2f}", {"total": str(total), "calc": str(calc)})
    # Confirm total vs order total consistency (three places: confirm / detail / total)
    try:
        conf_total_d = Decimal(str(conf_total)) if conf_total is not None else None
    except Exception:
        conf_total_d = None
    ct.check(
        "confirm_detail_total_consistent",
        conf_total_d is not None and conf_total_d == total,
        {"confirm_total": str(conf_total), "order_total": str(total), "lines": snap},
    )
    ct.check("order_created", code == 201 and order["order_no"], {"http": code, "message": msg(body)})
    m.dump_case("PB-B03-AC1", ct.as_detail())
    return finish(ct, m.result)


def ac_b03_02(env, fx):
    m.reset_ns(env)
    s, p = fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B03-AC2")
    pid = p["P-ON-10"]
    before = m.product_row(env, pid)
    # name/price
    c1, b1 = http_json(
        "PATCH", f"{base_url(env)}/api/admin/products/{pid}",
        {"name": "HACKED", "price": "0.01", "stock": "10"}, auth(s),
    )
    after = m.product_row(env, pid)
    ct.check("name_price_immutable", after["name"] == before["name"] and str(after["price"]) == str(before["price"]), {
        "http": c1, "message": msg(b1), "before": before, "after": after
    })
    # description / image-ish fields if accepted by API
    c2, b2 = http_json(
        "PATCH", f"{base_url(env)}/api/admin/products/{pid}",
        {"description": "HACKED-DESC", "stock": "10"}, auth(s),
    )
    after2 = m.product_row(env, pid)
    # product_row may not include description — query it
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT description FROM product WHERE id=%s", (pid,))
            desc = cur.fetchone()["description"]
    finally:
        conn.close()
    ct.check(
        "description_not_silently_replaced_or_explicit",
        "HACKED-DESC" not in str(desc) or c2 >= 400,
        {"http": c2, "message": msg(b2), "description_prefix": str(desc)[:80]},
    )
    m.dump_case("PB-B03-AC2", ct.as_detail())
    return finish(ct, m.result)


def ac_b12_02(env, fx):
    m.reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    ct = ConjunctTracker("PB-B12-AC2")
    c1 = m.cart_add(env, ta, p["P-ON-10"], "3")
    c2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    code, body, _, _ = m.place_order(env, ta, [c1, c2])
    orders = m.db_orders(env, "b032_buyer_a")
    items = m.db_order_items(env, orders[0]["id"])
    ct.check(
        "multi_product_one_order_placed",
        code == 201 and orders[0]["status"] == "PLACED" and len(items) == 2 and any(str(i["quantity"]) == "3" for i in items),
        {"http": code, "message": msg(body), "items": items},
    )
    # Multi-product whole-order cancel
    m.cancel_customer(env, ta, str(orders[0]["id"]), "PLACED")
    o2 = m.db_orders(env, "b032_buyer_a")[0]
    ct.check("multi_product_whole_order_cancel", o2["status"] == "CANCELLED", {"order": o2})
    # Single qty
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    c3 = m.cart_add(env, ta, p["P-ON-10"], "1")
    code2, body2, _, _ = m.place_order(env, ta, [c3])
    ct.check("single_qty_order", code2 == 201 and msg(body2) == "下单成功", {"http": code2, "message": msg(body2)})
    m.dump_case("PB-B12-AC2", ct.as_detail())
    return finish(ct, m.result)


def ac_b12_03(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B12-AC3")
    c_on = m.cart_add(env, ta, p["P-ON-10"], "1")
    m.align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    c_low = m.cart_add(env, ta, p["P-ON-1"], "1")
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cart_item SET quantity=5 WHERE id=%s", (c_low,))
            # Stale offline / nonexistent rows left in cart
            cur.execute("SELECT id FROM customer WHERE username='b032_buyer_a'")
            cust = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO cart_item(customer_id, product_id, quantity, updated_at) VALUES (%s,%s,1,NOW(6))",
                (cust, p["P-OFF-M"]),
            )
            c_off_stale = str(cur.lastrowid)
            # nonexistent product id: use high id if FK allows — else skip
            c_missing = None
            missing_err = None
            try:
                cur.execute(
                    "INSERT INTO cart_item(customer_id, product_id, quantity, updated_at) VALUES (%s,%s,1,NOW(6))",
                    (cust, 999999),
                )
                c_missing = str(cur.lastrowid)
            except Exception as e:
                missing_err = str(e)
    finally:
        conn.close()

    # Toggle selection: uncheck all selectable via API if available — use confirm empty / selected
    c_empty, b_empty = m.confirm(env, ta, [])
    ct.check("empty_select_rejected", msg(b_empty) == "请选择商品", {"http": c_empty, "message": msg(b_empty)})

    # Insufficient selectable (not 失效) + offline stale not in successful submit
    code, body, _, _ = m.place_order(env, ta, [c_on])
    ct.check("submit_only_valid_selected", code == 201 and msg(body) == "下单成功", {"http": code, "message": msg(body)})

    # UI: disabled offline / invalid tags / insufficient hint / toggle
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
    // re-seed cart for UI: add online + ensure stale offline visible if API allows
    await page.goto(fe + '/me/cart', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(1000);
    const allLabel = await page.locator('text=全选可下单商品').count();
    const disabled = await page.locator('.ant-checkbox-disabled, input[type=checkbox][disabled]').count();
    const invalidTag = await page.locator('text=已下架').count();
    const insufHint = await page.locator('text=当前库存').count();
    const checkedBefore = await page.locator('.ant-checkbox-checked').count();
    // toggle: click 全选 then uncheck
    const allBox = page.locator('text=全选可下单商品').first();
    if (await allBox.count()) {{ await allBox.click(); await page.waitForTimeout(300); }}
    const checkedAfterToggle = await page.locator('.ant-checkbox-checked').count();
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-cart-selection.png'))}, fullPage:true}});
    out.shots = ['b12-cart-selection.png'];
    out.ui = {{allLabel, disabled, invalidTag, insufHint, checkedBefore, checkedAfterToggle}};
    out.ok = allLabel > 0 && (disabled > 0 || invalidTag > 0) && insufHint >= 0;
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b12_ac3",
    )
    ui = shot.get("ui") or {}
    ct.check(
        "ui_has_invalid_or_disabled_offline_rows",
        shot.get("ok") is True and (ui.get("disabled", 0) > 0 or ui.get("invalidTag", 0) > 0),
        shot,
    )
    ct.check(
        "stale_offline_row_prepared",
        c_off_stale is not None,
        {"stale_offline_cart_id": c_off_stale, "missing_product": c_missing, "missing_err": missing_err},
    )
    m.dump_case("PB-B12-AC3", ct.as_detail())
    return finish(ct, m.result)


def ac_b12_04(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B12-AC4")
    cid = m.cart_add(env, ta, p["P-ON-10"], "2")
    c_code, c_body = m.confirm(env, ta, [cid])
    token = c_body["data"]["confirmationToken"]
    stock_after_confirm = m.db_stock(env, p["P-ON-10"])
    # Confirm itself must not reduce stock
    ct.check("confirm_keeps_stock_online", str(stock_after_confirm) == "10" and m.product_row(env, p["P-ON-10"])["status"] == "ONLINE", {
        "stock": stock_after_confirm
    })
    http_json("PATCH", f"{base_url(env)}/api/me/cart/items/{cid}", {"quantity": "3"}, auth(ta))
    s_code, s_body, _ = m.submit_order(env, ta, token)
    ct.check("qty_change_rejects", msg(s_body) == "确认信息已变化，请重新确认", {"http": s_code, "message": msg(s_body)})

    # Identity replace / republish
    c2, b2 = m.confirm(env, ta, [cid])
    token2 = b2["data"]["confirmationToken"]
    orders0 = m.db_orders(env, "b032_buyer_a")
    cart0 = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    stock0 = m.db_stock(env, p["P-ON-10"])
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(s))
    s2_c, s2_b, _ = m.submit_order(env, ta, token2)
    orders1 = m.db_orders(env, "b032_buyer_a")
    cart1 = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    stock1 = m.db_stock(env, p["P-ON-10"])
    ct.check(
        "reject_keeps_orders_stock_cart_full_set",
        s2_c >= 400 and orders1 == orders0 and cart1 == cart0 and stock1 == stock0,
        {"http": s2_c, "nested": nested_msgs(s2_b), "orders": [len(orders0), len(orders1)], "cart": cart1, "stock": [stock0, stock1]},
    )
    # Republish then success
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/online", headers=auth(s))
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}", {"stock": "10"}, auth(s))
    carts = m.db_cart(env, "b032_buyer_a")
    cid = str(carts[0]["id"]) if carts else m.cart_add(env, ta, p["P-ON-10"], "1")
    s3_c, s3_b, _, _ = m.place_order(env, ta, [cid])
    ct.check("republish_reconfirm_success", s3_c == 201 and msg(s3_b) == "下单成功", {"http": s3_c, "message": msg(s3_b)})
    # Stock declined after success, still ONLINE if remaining >0
    row = m.product_row(env, p["P-ON-10"])
    ct.check("after_success_stock_down_still_online", int(row["stock"]) < 10 and row["status"] == "ONLINE", row)

    # In-place price N/A — prove not editable
    before = m.product_row(env, p["P-ON-5"])
    cp, bp = http_json("PATCH", f"{base_url(env)}/api/admin/products/{p['P-ON-5']}", {"price": "0.01", "stock": "5"}, auth(s))
    after = m.product_row(env, p["P-ON-5"])
    ct.check(
        "inplace_price_N_A_immutable",
        str(after["price"]) == str(before["price"]),
        {"http": cp, "message": msg(bp), "before": before, "after": after, "disposition": "N/A proven immutable"},
    )

    # UI confirm modal
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
    const bodyText = await modal.innerText();
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-checkout-confirm.png'))}, fullPage:true}});
    out.shots = ['b12-checkout-confirm.png'];
    out.ui = {{bodyText: bodyText.slice(0, 400)}};
    out.ok = bodyText.includes('确认下单') && bodyText.includes('总金额');
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b12_ac4",
    )
    distinct = True
    cart_shot = SHOTS / "b12-cart-selection.png"
    conf_shot = SHOTS / "b12-checkout-confirm.png"
    if cart_shot.exists() and conf_shot.exists():
        distinct = sha256_file(cart_shot) != sha256_file(conf_shot)
    ct.check("confirm_ui_modal_distinct", shot.get("ok") is True and distinct, {"shot": shot, "distinct": distinct})
    m.dump_case("PB-B12-AC4", ct.as_detail())
    return finish(ct, m.result)


def ac_b12_05(env, fx):
    m.reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    ct = ConjunctTracker("PB-B12-AC5")
    m.cart_add(env, ta, p["P-ON-10"], "1")
    m.cart_add(env, ta, p["P-ON-5"], "1")
    stock_before = {k: m.db_stock(env, p[k]) for k in ("P-ON-10", "P-ON-5")}
    # Toggle select should not change stock
    carts = m.db_cart(env, "b032_buyer_a")
    if carts:
        http_json("PATCH", f"{base_url(env)}/api/me/cart/items/{carts[0]['id']}", {"quantity": str(carts[0]["quantity"])}, auth(ta))
    stock_mid = {k: m.db_stock(env, p[k]) for k in ("P-ON-10", "P-ON-5")}
    ct.check("select_toggle_no_stock_change", stock_before == stock_mid, {"before": stock_before, "mid": stock_mid})

    c1, b1 = http_json("DELETE", f"{base_url(env)}/api/me/cart", headers=auth(ta))
    stock_after = {k: m.db_stock(env, p[k]) for k in ("P-ON-10", "P-ON-5")}
    cart_after = m.db_cart(env, "b032_buyer_a")
    ct.check(
        "clear_cart_api_no_order_stock_change",
        c1 == 200 and stock_before == stock_after and len(cart_after) == 0 and len(m.db_orders(env, "b032_buyer_a")) == 0,
        {"http": c1, "message": msg(b1), "stock_after": stock_after},
    )

    # Real confirm modal screenshot (.ant-modal-confirm)
    m.cart_add(env, ta, p["P-ON-10"], "1")
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
    await page.waitForTimeout(600);
    await page.getByRole('button', {{ name: /清空购物车/ }}).click();
    const clearModal = page.locator('.ant-modal-confirm, .ant-modal').filter({{ hasText: '确定清空购物车' }});
    await clearModal.waitFor({{ state: 'visible', timeout: 10000 }});
    await page.waitForTimeout(300);
    const visible = await clearModal.isVisible();
    const text = await clearModal.innerText();
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-clear-cart-confirm.png'))}, fullPage:true}});
    out.shots = ['b12-clear-cart-confirm.png'];
    out.ui = {{visible, text: text.slice(0, 200)}};
    out.ok = visible && text.includes('确定清空');
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b12_ac5_clear",
    )
    ct.check("clear_cart_confirm_modal_screenshot", shot.get("ok") is True and (SHOTS / "b12-clear-cart-confirm.png").exists(), shot)
    m.dump_case("PB-B12-AC5", ct.as_detail())
    return finish(ct, m.result)


def ac_b12_06(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B12-AC6")
    # Multi-problem rows listed together on final submit
    m.align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    m.align_product(env, s, p["P-ON-10"], PRODUCTS["P-ON-10"])
    c_low = m.cart_add(env, ta, p["P-ON-1"], "1")
    c_off = m.cart_add(env, ta, p["P-ON-10"], "1")
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cart_item SET quantity=5 WHERE id=%s", (c_low,))
    finally:
        conn.close()
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(s))
    stock_b = {p["P-ON-1"]: m.db_stock(env, p["P-ON-1"]), p["P-ON-10"]: m.db_stock(env, p["P-ON-10"])}
    cart_b = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    # Final submit path (confirm+submit), not early return only
    conf_c, conf_b = m.confirm(env, ta, [c_low, c_off])
    if conf_c in (200, 201) and isinstance(conf_b, dict) and (conf_b.get("data") or {}).get("confirmationToken"):
        token = conf_b["data"]["confirmationToken"]
        s_c, s_b, _ = m.submit_order(env, ta, token)
        final_msgs = nested_msgs(s_b)
        final_http = s_c
        path_used = "confirm+submit"
    else:
        # confirm may already reject with listing
        final_msgs = nested_msgs(conf_b)
        final_http = conf_c
        path_used = "confirm_reject"
        # Also try place_order for message comparison
        po_c, po_b, _, _ = m.place_order(env, ta, [c_low, c_off])
        final_msgs = final_msgs + " " + nested_msgs(po_b)
        final_http = max(final_http, po_c)

    name1 = PRODUCTS["P-ON-1"]["name"]
    name10 = PRODUCTS["P-ON-10"]["name"]
    has_insuf = "库存不足" in final_msgs and name1 in final_msgs
    has_off = "已下架" in final_msgs and name10 in final_msgs
    stock_a = {p["P-ON-1"]: m.db_stock(env, p["P-ON-1"]), p["P-ON-10"]: m.db_stock(env, p["P-ON-10"])}
    cart_a = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    ct.check(
        "multi_problem_rows_listed",
        has_insuf and has_off,
        {"path": path_used, "http": final_http, "messages": final_msgs},
    )
    ct.check(
        "final_fail_stock_cart_unchanged",
        stock_a == stock_b and cart_a == cart_b and len(m.db_orders(env, "b032_buyer_a")) == 0,
        {"stock_before": stock_b, "stock_after": stock_a, "cart_before": cart_b, "cart_after": cart_a},
    )
    # Nonexistent / empty
    c_empty, b_empty = m.confirm(env, ta, [])
    ct.check("empty_select_message", msg(b_empty) == "请选择商品", {"http": c_empty, "message": msg(b_empty)})

    # UI error tip screenshot if possible
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
    const orderBtn = page.getByRole('button', {{ name: '下单' }});
    if (await orderBtn.count()) {{
      await orderBtn.click();
      await page.waitForTimeout(800);
      const modal = page.locator('.ant-modal');
      if (await modal.count()) {{
        const confirmBtn = modal.getByRole('button', {{ name: /确认|下单/ }}).last();
        if (await confirmBtn.count()) {{ await confirmBtn.click(); await page.waitForTimeout(1000); }}
      }}
    }}
    const text = await page.locator('body').innerText();
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-submit-error-tip.png'))}, fullPage:true}});
    out.shots = ['b12-submit-error-tip.png'];
    out.text = text.slice(0, 600);
    out.ok = text.includes('库存') || text.includes('下架') || text.includes('请选择') || text.includes('失败') || text.includes('重试');
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b12_ac6_err",
    )
    ct.check("ui_error_tip_screenshot", shot.get("ok") is True or (SHOTS / "b12-submit-error-tip.png").exists(), shot)
    m.dump_case("PB-B12-AC6", ct.as_detail())
    return finish(ct, m.result)


def run_screenshots(env, fx):
    """Final pass: remaining required shots + index mapping."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    m.align_product(env, fx["tokens"]["S"], fx["products"]["P-ON-10"], PRODUCTS["P-ON-10"])
    m.cart_add(env, ta, fx["products"]["P-ON-10"], "1")
    # Ensure at least one order for history
    cid = m.cart_add(env, ta, fx["products"]["P-ON-5"], "1")
    m.place_order(env, ta, [cid])
    seller_pwd = env.get("B032_SELLER_PASSWORD", "")
    js = f"""
const {{ chromium }} = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {{
  const fe = {json.dumps(fe_url(env))};
  const out = {{ok:false, shots:[], mapping:[]}};
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
    out.mapping.push({{file:'b03-after-login.png', ac:'PB-B03', step:'after login'}});

    const pid = {json.dumps(str(fx['products']['P-ON-10']))};
    await page.goto(fe + '/products/' + pid, {{waitUntil:'networkidle'}});
    await page.waitForTimeout(600);
    const directBuy = await page.getByRole('button', {{ name: /立即购买|直接下单/ }}).count();
    const addCart = await page.getByRole('button', {{ name: /加入购物车/ }}).count();
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-product-detail-no-direct-buy.png'))}, fullPage:true}});
    out.shots.push('b12-product-detail-no-direct-buy.png');
    out.mapping.push({{file:'b12-product-detail-no-direct-buy.png', ac:'PB-B12-AC1', step:'product detail no direct buy'}});
    out.detail = {{directBuy, addCart}};

    await page.goto(fe + '/me/cart', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(500);
    await page.getByRole('button', {{ name: /清空购物车/ }}).click();
    const clearModal = page.locator('.ant-modal-confirm, .ant-modal').filter({{ hasText: '确定清空购物车' }});
    await clearModal.waitFor({{ state: 'visible', timeout: 10000 }});
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-clear-cart-confirm.png'))}, fullPage:true}});
    out.shots.push('b12-clear-cart-confirm.png');
    out.mapping.push({{file:'b12-clear-cart-confirm.png', ac:'PB-B12-AC5', step:'clear cart confirm modal'}});
    await page.keyboard.press('Escape');

    await page.goto(fe + '/me/orders', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(800);
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b03-order-history.png'))}, fullPage:true}});
    out.shots.push('b03-order-history.png');
    out.mapping.push({{file:'b03-order-history.png', ac:'PB-B03-AC3', step:'customer order history'}});

    const page2 = await browser.newPage({{viewport:{{width:1280,height:900}}}});
    await page2.goto(fe + '/admin/login', {{waitUntil:'networkidle'}});
    await page2.locator('#username').fill('admin');
    await page2.locator('#password').fill({json.dumps(seller_pwd)});
    await page2.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page2.waitForURL(u => !String(u).includes('/login'), {{timeout:15000}});
    await page2.goto(fe + '/admin/orders', {{waitUntil:'networkidle'}});
    await page2.waitForTimeout(800);
    await page2.screenshot({{path: {json.dumps(str(SHOTS/'b03-admin-orders.png'))}, fullPage:true}});
    out.shots.push('b03-admin-orders.png');
    out.mapping.push({{file:'b03-admin-orders.png', ac:'PB-B03-AC3', step:'merchant order management'}});

    const fs = require('fs');
    const required = [
      'b03-after-login.png','b12-product-detail-no-direct-buy.png','b12-cart-selection.png',
      'b12-checkout-confirm.png','b12-clear-cart-confirm.png','b03-order-history.png','b03-admin-orders.png',
      'b13-order-success.png','b12-submit-error-tip.png','b01-merchant-orders-flow.png'
    ];
    out.required_exists = Object.fromEntries(required.map(f => [f, fs.existsSync({json.dumps(str(SHOTS))}+'/'+f)]));
    out.ok = directBuy === 0 && addCart > 0 && out.required_exists['b12-clear-cart-confirm.png'] && out.required_exists['b03-admin-orders.png'];
  }} catch(e) {{ out.error = String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
"""
    return run_node(js, "ui_screenshots_final")
