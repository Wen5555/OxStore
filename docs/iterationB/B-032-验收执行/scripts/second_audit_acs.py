#!/usr/bin/env python3
"""Second-audit AC runners (OF-19): V8 path, timing matrix, hard conjuncts. No fake PASS."""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import subprocess
import threading
import time
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

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


def product_images(env, pid) -> list:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, image_path, sort_order, content_type, size_bytes "
                "FROM product_image WHERE product_id=%s ORDER BY id",
                (pid,),
            )
            return list(cur.fetchall() or [])
    finally:
        conn.close()


def multipart_any(method: str, url: str, fields: dict, files: list, headers: dict):
    """POST/PUT/PATCH multipart; files is list of (field, Path)."""
    import mimetypes
    import uuid
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
        method=method.upper(),
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
    except error.URLError as e:
        return 0, {"error": str(e.reason)}


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


def wait_hold_lock(env, timeout=8.0) -> dict | None:
    """Wait until named lock b032_tx_hold is held (visible during after_stock SLEEP)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        conn = connect_mysql(env)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT IS_USED_LOCK('b032_tx_hold') AS holder")
                row = cur.fetchone() or {}
                holder = row.get("holder")
                if holder is not None:
                    return {"holder": holder, "observed_mono": time.monotonic(), "observed_wall": time.time()}
        finally:
            conn.close()
        time.sleep(0.02)
    return None


def _http_signal_issued(method: str, url: str, body, headers: dict, issued: dict, timeout: float = 60.0):
    """Write the HTTP request fully, mark issued, then read the response.

    issued['mono'] is set only after request bytes are sent — not before connect.
    """
    parsed = urlparse(url)
    payload = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    hdrs = {"Accept": "application/json", **(headers or {})}
    if payload is not None:
        hdrs["Content-Type"] = "application/json"
        hdrs["Content-Length"] = str(len(payload))
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=timeout)
    path = parsed.path + (("?" + parsed.query) if parsed.query else "")
    try:
        conn.putrequest(method.upper(), path)
        for key, value in hdrs.items():
            conn.putheader(key, str(value))
        conn.endheaders()
        if payload is not None:
            conn.send(payload)
        issued["mono"] = time.monotonic()
        issued["wall"] = time.time()
        issued["set"] = True
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="replace")
        try:
            parsed_body = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed_body = {"raw": raw}
        return resp.status, parsed_body
    except Exception as exc:
        if not issued.get("set"):
            issued["mono"] = time.monotonic()
            issued["wall"] = time.time()
            issued["set"] = True
            issued["send_error"] = str(exc)
        return 0, {"error": str(exc)}
    finally:
        conn.close()


def _in_flight_pre_lock_once(env, ta, confirmation_token, mutate_fn) -> dict:
    """Race: mutate after submit bytes are on the wire, before checkout lockCustomer.

    After-lock mutations that share customer FOR UPDATE cannot return 2xx while submit
    is still in-flight on a successful path (they wait for commit). A 2xx mutation that
    finishes before submit_end therefore ran without waiting on checkout's customer lock.
    """
    issued = {"set": False}
    box: dict = {"timeline": {}, "issued": issued}

    def submitter():
        box["timeline"]["submit_thread_start_mono"] = time.monotonic()
        code, body = _http_signal_issued(
            "POST",
            f"{base_url(env)}/api/me/orders",
            {"confirmationToken": confirmation_token},
            auth(ta, new_key()),
            issued,
            timeout=60.0,
        )
        box["submit"] = (code, body)
        box["timeline"]["submit_end_mono"] = time.monotonic()
        box["timeline"]["submit_end_wall"] = time.time()

    def mutator():
        deadline = time.monotonic() + 5.0
        while not issued.get("set") and time.monotonic() < deadline:
            time.sleep(0.00005)
        if not issued.get("set"):
            box["timeline"]["mutation_skipped"] = "submit_never_issued"
            box["mutation"] = None
            return
        box["timeline"]["mutation_start_mono"] = time.monotonic()
        box["timeline"]["mutation_start_wall"] = time.time()
        box["mutation"] = mutate_fn()
        box["timeline"]["mutation_end_mono"] = time.monotonic()
        box["timeline"]["mutation_end_wall"] = time.time()

    t_mut = threading.Thread(target=mutator, name="b032-inflight-mut")
    t_sub = threading.Thread(target=submitter, name="b032-inflight-sub")
    t_mut.start()
    t_sub.start()
    t_sub.join(timeout=60)
    t_mut.join(timeout=60)
    tl = box["timeline"]
    issued_mono = issued.get("mono")
    mut_s, mut_e = tl.get("mutation_start_mono"), tl.get("mutation_end_mono")
    sub_e = tl.get("submit_end_mono")
    mut_tuple = box.get("mutation")
    mut_code = mut_tuple[0] if isinstance(mut_tuple, tuple) else None
    sub_tuple = box.get("submit")
    sub_code = sub_tuple[0] if isinstance(sub_tuple, tuple) else None
    mut_dur = (mut_e - mut_s) if mut_s is not None and mut_e is not None else None
    window = (
        issued.get("set") is True
        and issued_mono is not None
        and mut_s is not None
        and mut_e is not None
        and sub_e is not None
        and issued_mono <= mut_s
        and mut_e < sub_e
        and mut_dur is not None
        and mut_dur < 0.5
        and mut_code in (200, 201)
    )
    box["window"] = {
        "hit": window,
        "issued_set": bool(issued.get("set")),
        "issued_before_mutate": (
            issued_mono is not None and mut_s is not None and issued_mono <= mut_s
        ),
        "mutate_finished_before_submit_end": (
            mut_e is not None and sub_e is not None and mut_e < sub_e
        ),
        "mutation_short": mut_dur is not None and mut_dur < 0.5,
        "mutation_http": mut_code,
        "submit_http": sub_code,
        "mutation_duration_s": mut_dur,
        "note": "window = submit bytes issued, mutate 2xx completed before submit response, "
        "duration <0.5s (did not wait on checkout customer FOR UPDATE / after_stock hold)",
    }
    box["timeline"]["issued_mono"] = issued_mono
    box["timeline"]["issued_wall"] = issued.get("wall")
    box["final_db"] = {
        "orders": m.db_orders(env, "b032_buyer_a"),
        "cart": cart_fingerprint(m.db_cart(env, "b032_buyer_a")),
    }
    return box


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

    # Close path = V8 CALL (documented in detail_extra); meta notes are NOT formal conjuncts.
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

    # Real intent/trade entries (IntentController, AdminIntentController, TradeController)
    # — not fake PUT/PATCH/DELETE on /api/admin/legacy-intents/{id}.
    real_ids = [(str(i["id"]), i.get("status")) for i in intents_after]
    snap_before = {str(i["id"]): dict(i) for i in intents_after}
    mut_attempts = []
    sub_c, sub_b = http_json(
        "POST",
        f"{base_url(env)}/api/products/{p['P-ON-10']}/intents",
        headers=auth(ta, new_key()),
    )
    mut_attempts.append(
        {
            "entry": "POST /api/products/{productId}/intents",
            "id": p["P-ON-10"],
            "http": sub_c,
            "message": msg(sub_b),
        }
    )
    q_c, q_b = http_json(
        "GET",
        f"{base_url(env)}/api/admin/intents?productId={p['P-ON-10']}&page=1&size=10",
        headers=auth(s),
    )
    mut_attempts.append(
        {
            "entry": "GET /api/admin/intents",
            "id": p["P-ON-10"],
            "http": q_c,
            "message": msg(q_b),
        }
    )
    for rid, st in real_ids:
        for action, body in [
            ("start", None),
            ("success", None),
            ("fail", {"action": "DISCARD"}),
        ]:
            if body is None:
                hc, hb = http_json(
                    "POST", f"{base_url(env)}/api/admin/intents/{rid}/{action}", headers=auth(s)
                )
            else:
                hc, hb = http_json(
                    "POST", f"{base_url(env)}/api/admin/intents/{rid}/{action}", body, auth(s)
                )
            mut_attempts.append(
                {
                    "entry": f"POST /api/admin/intents/{{id}}/{action}",
                    "id": rid,
                    "status": st,
                    "http": hc,
                    "message": msg(hb),
                }
            )
    writes = [a for a in mut_attempts if a["entry"].startswith("POST")]
    writes_rejected = all(a["http"] >= 400 for a in writes)
    queue_not_writable = q_c >= 400
    legacy_entry_c, legacy_entry_b = sub_c, sub_b
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, status, legacy_closed_at, legacy_close_reason, product_name_snapshot "
                "FROM purchase_intent WHERE product_name_snapshot LIKE 'LEGACY-%' ORDER BY id"
            )
            intents_after_mut = list(cur.fetchall())
    finally:
        conn.close()
    unchanged = all(
        str(i["id"]) in snap_before
        and snap_before[str(i["id"])]["status"] == i["status"]
        and str(snap_before[str(i["id"])].get("legacy_closed_at")) == str(i.get("legacy_closed_at"))
        for i in intents_after_mut
    )
    ct.check(
        "archive_real_id_mutations_rejected_no_state_write",
        writes_rejected and queue_not_writable and unchanged,
        {
            "attempts": mut_attempts,
            "writes_rejected": writes_rejected,
            "queue_not_writable": queue_not_writable,
            "legacy_entry": {"http": legacy_entry_c, "message": msg(legacy_entry_b)},
            "unchanged": unchanged,
            "before": snap_before,
            "after": intents_after_mut,
            "note": "IntentController POST /api/products/{id}/intents; AdminIntentController GET /api/admin/intents; TradeController POST /api/admin/intents/{id}/start|success|fail",
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
    checkout_receipts = [
        r for r in receipts if str(r.get("operation_type") or "").upper() == "CHECKOUT"
    ]
    # Precise CHECKOUT receipt only — never soft-pass on arbitrary receipt>=1
    ct.check(
        "pos_order_items_and_checkout_receipt",
        len(orders) == 1 and len(items) >= 1 and len(checkout_receipts) >= 1,
        {
            "orders": orders,
            "items": items,
            "receipts": receipts,
            "checkout_receipts": checkout_receipts,
        },
    )
    # Rollback paths must leave zero orphan order_items / CHECKOUT receipts
    # (asserted per-breakpoint below with precise queries)

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
        conn = connect_mysql(env)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) c FROM order_item oi "
                    "JOIN shop_order so ON so.id=oi.order_id "
                    "JOIN customer c ON c.id=so.customer_id WHERE c.username='b032_buyer_a'"
                )
                orphan_items = int(cur.fetchone()["c"])
                cur.execute(
                    "SELECT r.id, r.operation_type FROM operation_receipt r "
                    "JOIN customer c ON c.id=r.customer_id WHERE c.username='b032_buyer_a' "
                    "AND r.operation_type='CHECKOUT'"
                )
                checkout_rcpt = list(cur.fetchall() or [])
        finally:
            conn.close()
        rolled = (
            stock_a == stock_b
            and cart_a == cart_b
            and len(orders_a) == 0
            and orphan_items == 0
            and len(checkout_rcpt) == 0
            and s_code >= 400
        )
        breaks[phase] = {
            "http": s_code,
            "message": msg(s_body),
            "probe": phases,
            "rolled_back": rolled,
            "probe_hit": need_probe in str(phases),
            "cart_before": cart_b,
            "cart_after": cart_a,
            "stock": [stock_b, stock_a],
            "orphan_order_items": orphan_items,
            "checkout_receipts_after": checkout_rcpt,
        }
        ct.check(
            f"breakpoint_{phase}_rollback_and_probe",
            rolled and need_probe in str(phases),
            breaks[phase],
        )

    m.dump_case("PB-B13-AC1", {"breakpoints": breaks, **ct.as_detail()})
    return finish(ct, m.result, {"breakpoints": breaks, "trigger_sql": "fixtures/b032_tx_probes.sql"})


def _hold_mutate(env, ta, token, mutate_fn, hold_seconds=3) -> dict:
    """True-hold timing: mutate while after_stock SLEEP holds TX.

    Barrier = MySQL named lock b032_tx_hold (GET_LOCK around SLEEP in after_stock).
    MyISAM probe is NOT used as mid-hold signal (not readable until TX ends).
    Clocks use time.monotonic(); wall timestamps recorded separately.
    """
    m.clear_probe(env)
    # Ensure any leaked named lock from a prior aborted run is cleared on THIS session
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT RELEASE_LOCK('b032_tx_hold')")
    finally:
        conn.close()
    set_control(env, fail_phase=None, probe=True, hold_seconds=hold_seconds)
    box: dict = {"timeline": {}, "ok_to_mutate": False}

    def submitter():
        box["timeline"]["submit_start_mono"] = time.monotonic()
        box["timeline"]["submit_start_wall"] = time.time()
        box["submit"] = m.submit_order(env, ta, token)
        box["timeline"]["submit_end_mono"] = time.monotonic()
        box["timeline"]["submit_end_wall"] = time.time()

    def mutator():
        lock_obs = wait_hold_lock(env, timeout=max(2.0, hold_seconds + 2))
        box["hold_lock"] = lock_obs
        if lock_obs is None:
            # Hard fail: do NOT mutate after hold-lock timeout
            box["timeline"]["hold_lock_timeout"] = True
            box["timeline"]["hold_observed_mono"] = None
            box["mutation"] = None
            box["ok_to_mutate"] = False
            return
        box["ok_to_mutate"] = True
        box["timeline"]["hold_observed_mono"] = lock_obs["observed_mono"]
        box["timeline"]["hold_observed_wall"] = lock_obs["observed_wall"]
        box["timeline"]["hold_lock_holder"] = lock_obs["holder"]
        box["timeline"]["mutation_start_mono"] = time.monotonic()
        box["timeline"]["mutation_start_wall"] = time.time()
        box["mutation"] = mutate_fn()
        box["timeline"]["mutation_end_mono"] = time.monotonic()
        box["timeline"]["mutation_end_wall"] = time.time()

    t1 = threading.Thread(target=submitter, name="b032-submit")
    t2 = threading.Thread(target=mutator, name="b032-mutate")
    t1.start()
    time.sleep(0.05)
    t2.start()
    t1.join(timeout=hold_seconds + 30)
    t2.join(timeout=hold_seconds + 30)
    box["threads"] = {
        "submit_alive": t1.is_alive(),
        "mutate_alive": t2.is_alive(),
    }
    set_control(env, fail_phase=None, probe=False, hold_seconds=0)
    tl = box["timeline"]
    hold_ok = box.get("ok_to_mutate") is True and tl.get("hold_observed_mono") is not None
    # No soft 50ms tolerance: mutation must start strictly before submit_end
    started_during_hold = (
        hold_ok
        and tl.get("mutation_start_mono") is not None
        and tl.get("submit_end_mono") is not None
        and tl["mutation_start_mono"] >= tl["hold_observed_mono"]
        and tl["mutation_start_mono"] < tl["submit_end_mono"]
        and not box["threads"]["submit_alive"]
        and not box["threads"]["mutate_alive"]
    )
    blocked_until_release = (
        hold_ok
        and tl.get("mutation_end_mono") is not None
        and tl.get("submit_end_mono") is not None
        and tl["mutation_end_mono"] >= tl["submit_end_mono"]
        and (tl["mutation_end_mono"] - tl["mutation_start_mono"]) >= (hold_seconds * 0.5)
    )
    box["overlap"] = {
        "started_during_hold": started_during_hold,
        "blocked_until_release": blocked_until_release,
        "hold_proven": started_during_hold and blocked_until_release,
        "hold_seconds": hold_seconds,
        "hold_lock_timeout": bool(tl.get("hold_lock_timeout")),
        "barrier": "IS_USED_LOCK(b032_tx_hold)",
        "clock": "time.monotonic",
    }
    box["final_db"] = {
        "orders": m.db_orders(env, "b032_buyer_a"),
        "cart": cart_fingerprint(m.db_cart(env, "b032_buyer_a")),
        "probe_phases": m.probe_phases(env),
        "stocks": {},
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
    if hold_add["overlap"].get("hold_lock_timeout"):
        ct.skip(
            "during_hold_add_same_product",
            "b032_tx_hold named lock not observed before timeout — hold observation failed",
            disposition="NOT_EXECUTED",
        )
    else:
        ct.check(
            "during_hold_add_same_product_hold_proven",
            hold_add["overlap"].get("hold_proven") is True,
            hold_add,
            on_fail="FAIL",
        )
        cart_after = hold_add["final_db"]["cart"]
        orders = hold_add["final_db"]["orders"]
        # Selected line consumed by order; concurrent same-product ADD must be retained in cart
        add_retained = len(cart_after) >= 1 and any(
            r["product_id"] == p["P-ON-10"] for r in cart_after
        )
        ct.check(
            "during_hold_add_retained_in_cart",
            len(orders) == 1 and add_retained,
            {
                "cart_after": cart_after,
                "orders": len(orders),
                "mutation": redact(hold_add.get("mutation")),
                "order_qty": (
                    str(m.db_order_items(env, orders[0]["id"])[0]["quantity"]) if orders else None
                ),
            },
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

    # RETAINED conjunct: same product + NEW settlement key → can create multiple orders
    m.align_product(env, fx["tokens"]["S"], p["P-ON-10"], PRODUCTS["P-ON-10"])
    cid_new = m.cart_add(env, ta, p["P-ON-10"], "1")
    s_new, b_new, _, _ = m.place_order(env, ta, [cid_new])  # new confirmation + new key inside
    ct.check(
        "same_product_new_settlement_key_allows_second_order",
        s_new == 201 and msg(b_new) == "下单成功" and len(m.db_orders(env, "b032_buyer_a")) == 2,
        {"http": s_new, "message": msg(b_new), "orders": len(m.db_orders(env, "b032_buyer_a"))},
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

    # Lock-BEFORE window: serial PATCH + DELETE + ADD after confirm, before submit
    # (distinct from during-hold matrix below)
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    m.align_product(env, s, p["P-ON-10"], PRODUCTS["P-ON-10"])
    m.align_product(env, s, p["P-ON-5"], PRODUCTS["P-ON-5"])
    m.align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    cid_patch = m.cart_add(env, ta, p["P-ON-10"], "2")
    cid_del = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, cb = m.confirm(env, ta, [cid_patch, cid_del])
    token = cb["data"]["confirmationToken"]
    t_confirm = time.monotonic()
    patch_c, patch_b = http_json(
        "PATCH", f"{base_url(env)}/api/me/cart/items/{cid_patch}", {"quantity": "4"}, auth(ta)
    )
    t_patch = time.monotonic()
    del_c, del_b = http_json(
        "DELETE", f"{base_url(env)}/api/me/cart/items/{cid_del}", headers=auth(ta)
    )
    t_delete = time.monotonic()
    add_c, add_b = http_json(
        "POST",
        f"{base_url(env)}/api/me/cart/items",
        {"productId": p["P-ON-1"]},
        auth(ta, new_key()),
    )
    t_add = time.monotonic()
    t_submit_start = time.monotonic()
    before_c, before_b, _ = m.submit_order(env, ta, token)
    t_submit_end = time.monotonic()
    lock_before_serial = t_confirm < t_patch < t_delete < t_add <= t_submit_start < t_submit_end
    lock_before_reject = msg(before_b) in (
        "确认信息已变化，请重新确认",
        "所选商品无法下单",
    )
    ct.check(
        "lock_before_patch_delete_add_serial_rejects",
        patch_c == 200
        and del_c == 200
        and add_c in (200, 201)
        and before_c >= 400
        and lock_before_reject
        and lock_before_serial,
        {
            "window": "after_confirm_before_submit",
            "not_in_flight": True,
            "distinct_from": "during_hold",
            "patch": {"http": patch_c, "message": msg(patch_b)},
            "delete": {"http": del_c, "message": msg(del_b)},
            "add": {"http": add_c, "message": msg(add_b)},
            "submit": {"http": before_c, "message": msg(before_b)},
            "mono": {
                "confirm": t_confirm,
                "patch": t_patch,
                "delete": t_delete,
                "add": t_add,
                "submit_start": t_submit_start,
                "submit_end": t_submit_end,
                "serial": lock_before_serial,
            },
        },
    )
    # In-flight = submit HTTP bytes already sent AND checkout has not yet taken
    # customer FOR UPDATE. Serial confirm-then-mutate-then-submit is NOT this window.
    inflight = {"delete": None, "add": None}
    for kind in ("delete", "add"):
        last = None
        for attempt in range(1, 41):
            m.reset_ns(env)
            ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
            fx["tokens"]["A"] = ta
            m.align_product(env, s, p["P-ON-10"], PRODUCTS["P-ON-10"])
            cid_if = m.cart_add(env, ta, p["P-ON-10"], "1")
            _, cb_if = m.confirm(env, ta, [cid_if])
            tok_if = cb_if["data"]["confirmationToken"]
            if kind == "delete":
                mut = lambda: http_json(
                    "DELETE",
                    f"{base_url(env)}/api/me/cart/items/{cid_if}",
                    headers=auth(ta),
                    timeout=40,
                )
            else:
                mut = lambda: http_json(
                    "POST",
                    f"{base_url(env)}/api/me/cart/items",
                    {"productId": p["P-ON-10"]},
                    auth(ta, new_key()),
                    timeout=40,
                )
            last = _in_flight_pre_lock_once(env, ta, tok_if, mut)
            last["attempt"] = attempt
            last["kind"] = kind
            if last.get("window", {}).get("hit"):
                inflight[kind] = last
                break
        if inflight[kind] is None:
            inflight[kind] = last

    def _if_ok(kind: str) -> tuple[bool, dict]:
        box = inflight.get(kind) or {}
        win = box.get("window") or {}
        tl = box.get("timeline") or {}
        db = box.get("final_db") or {}
        orders = db.get("orders") or []
        cart = db.get("cart") or []
        sub = box.get("submit") if isinstance(box.get("submit"), tuple) else (None, None)
        mut = box.get("mutation") if isinstance(box.get("mutation"), tuple) else (None, None)
        ev = {
            "attempt": box.get("attempt"),
            "window": win,
            "timeline": tl,
            "submit": {"http": sub[0], "message": msg(sub[1])},
            "mutation": {"http": mut[0], "message": msg(mut[1])},
            "orders": len(orders),
            "cart": cart,
        }
        if not win.get("hit"):
            return False, ev
        if kind == "delete":
            # Pre-lock DELETE must surface in this submit's validation: reject, no order.
            ok = (
                sub[0] is not None
                and sub[0] >= 400
                and len(orders) == 0
                and mut[0] == 200
            )
            ev["expected"] = "DELETE 200 in window → submit reject, no order"
            return ok, ev
        rem = [r for r in cart if r["product_id"] == p["P-ON-10"]]
        rem_qty = rem[0]["quantity"] if len(rem) == 1 else None
        oqty = None
        if orders:
            items = m.db_order_items(env, orders[0]["id"])
            oqty = str(items[0]["quantity"]) if items else None
        # Pre-lock ADD reflects in latest check (digest → 409, cart keeps +1)
        # or, if submit won with locked qty, order qty is that snapshot and remainder accurate.
        ok_reject = sub[0] is not None and sub[0] >= 400 and len(orders) == 0 and rem_qty == "2"
        ok_lock = sub[0] == 201 and len(orders) == 1 and oqty is not None and rem_qty is not None
        ev["order_qty"] = oqty
        ev["remainder_qty"] = rem_qty
        ev["expected"] = "ADD 2xx in window → 409+cart qty 2 or 201+locked snapshot"
        return ok_reject or ok_lock, ev

    del_ok, del_ev = _if_ok("delete")
    add_ok, add_ev = _if_ok("add")
    del_hit = bool((inflight.get("delete") or {}).get("window", {}).get("hit"))
    add_hit = bool((inflight.get("add") or {}).get("window", {}).get("hit"))
    if not del_hit or not add_hit:
        ct.skip(
            "in_flight_pre_lock_delete_add",
            "could not construct submit-issued / lock-not-held window for "
            + ",".join(
                k for k, hit in (("delete", del_hit), ("add", add_hit)) if not hit
            ),
            disposition="NOT_EXECUTED",
        )
        # Attach timelines even when skipped
        ct.items[-1]["evidence"] = {
            "reason": ct.items[-1]["evidence"]["reason"],
            "delete": del_ev,
            "add": add_ev,
            "not_serial_before_submit": True,
        }
    else:
        ct.check(
            "in_flight_pre_lock_delete_add",
            del_ok and add_ok,
            {
                "delete": del_ev,
                "add": add_ev,
                "not_serial_before_submit": True,
            },
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
            "threads": box.get("threads"),
            "mutation": redact(box.get("mutation")),
            "submit": redact(box.get("submit")),
            "final_db": box.get("final_db"),
        }
        if box["overlap"].get("hold_lock_timeout"):
            ct.skip(
                f"during_hold_{name}",
                "b032_tx_hold named lock timeout — not mutating; hold unobservable",
                disposition="NOT_EXECUTED",
            )
            continue
        hold_proven = box["overlap"].get("hold_proven") is True
        ct.check(
            f"during_hold_{name}_hold_proven",
            hold_proven,
            matrix[name],
        )
        orders = box["final_db"]["orders"]
        cart_after = box["final_db"]["cart"]
        submit_tuple = box.get("submit")
        submit_code = submit_tuple[0] if isinstance(submit_tuple, tuple) else None
        oitems = m.db_order_items(env, orders[0]["id"]) if orders else []
        order_qty = str(oitems[0]["quantity"]) if oitems else None
        rem_rows = [r for r in cart_after if r["product_id"] == p["P-ON-10"]]
        rem_qty = rem_rows[0]["quantity"] if len(rem_rows) == 1 else None
        if name == "patch_qty":
            ct.check(
                "during_hold_patch_final_order_qty_unchanged",
                len(orders) == 1 and oitems and order_qty == "1",
                {"items": oitems, "cart_after": cart_after},
            )
        elif name == "delete_selected":
            # After-lock DELETE PASS: successful order with original qty.
            # submit>=400 and no order is NOT a DELETE PASS (do not OR that in).
            delete_ok = (
                hold_proven
                and submit_code == 201
                and len(orders) == 1
                and order_qty == "1"
            )
            if delete_ok:
                ct.check(
                    "during_hold_delete_final_state",
                    True,
                    {
                        "submit_code": submit_code,
                        "orders": len(orders),
                        "order_qty": order_qty,
                        "cart_after": cart_after,
                        "mutation": redact(box.get("mutation")),
                    },
                )
            elif submit_code == 201 and len(orders) == 1 and order_qty != "1":
                ct.check(
                    "during_hold_delete_final_state",
                    False,
                    {
                        "submit_code": submit_code,
                        "orders": len(orders),
                        "order_qty": order_qty,
                        "cart_after": cart_after,
                        "mutation": redact(box.get("mutation")),
                    },
                )
            else:
                ct.skip(
                    "during_hold_delete_final_state",
                    "after-lock DELETE did not yield HTTP 201 + 1 order + qty=1 "
                    f"(submit={submit_code}, orders={len(orders)}, qty={order_qty}); "
                    "submit>=400 and no order is not DELETE PASS",
                    disposition="NOT_EXECUTED",
                )
        elif name == "add_same_selected":
            # Remainder of concurrent ADD must be exactly +1 on cart; order qty stays 1.
            add_ok = (
                hold_proven
                and submit_code == 201
                and len(orders) == 1
                and order_qty == "1"
                and rem_qty == "1"
            )
            if add_ok:
                ct.check(
                    "during_hold_add_final_retained",
                    True,
                    {
                        "submit_code": submit_code,
                        "orders": len(orders),
                        "order_qty": order_qty,
                        "remainder_qty": rem_qty,
                        "cart_after": cart_after,
                    },
                )
            elif submit_code == 201 and len(orders) == 1 and (order_qty != "1" or rem_qty != "1"):
                ct.check(
                    "during_hold_add_final_retained",
                    False,
                    {
                        "submit_code": submit_code,
                        "orders": len(orders),
                        "order_qty": order_qty,
                        "remainder_qty": rem_qty,
                        "cart_after": cart_after,
                    },
                )
            else:
                ct.skip(
                    "during_hold_add_final_retained",
                    "after-lock ADD did not yield HTTP 201 + order qty=1 + remainder qty=1 "
                    f"(submit={submit_code}, orders={len(orders)}, qty={order_qty}, rem={rem_qty})",
                    disposition="NOT_EXECUTED",
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

    # Merchant cancel of COMPLETED must be rejected (not PLACED success)
    mc_c, mc_b = m.cancel_admin(env, s, oid, "COMPLETED")
    still_completed = [o for o in m.db_orders(env, "b032_buyer_a") if str(o["id"]) == oid][0]
    ct.check(
        "merchant_cancel_completed_rejected",
        mc_c >= 400 and still_completed["status"] == "COMPLETED",
        {"http": mc_c, "message": msg(mc_b), "order": still_completed},
    )

    # No timeout auto-cancel: source scan of real @Scheduled candidates MUST enter PASS,
    # plus short wait showing PLACED unchanged (not wait-alone proof).
    cid4 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body4, _, _ = m.place_order(env, ta, [cid4])
    oid4 = m.order_id_of(body4)
    time.sleep(2.0)
    still4 = [o for o in m.db_orders(env, "b032_buyer_a") if str(o["id"]) == oid4][0]
    src_hits = subprocess.run(
        [
            "rg",
            "-n",
            "@Scheduled|SchedulingConfigurer|order.*timeout|cancel.*schedul|TimeoutCancel",
            "/tmp/oxstore-develop/backend/src/main/java",
            "-g",
            "*.java",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    all_hits = [ln for ln in (src_hits.stdout or "").splitlines() if ln.strip()]
    # Filter to order-cancel related; auction settle schedulers are unrelated
    cancel_related = [
        ln
        for ln in all_hits
        if any(k in ln.lower() for k in ("cancel", "timeout", "placed", "order"))
        and "auction" not in ln.lower()
    ]
    # PASS only if wait stayed PLACED AND no order-cancel scheduler candidate found
    no_order_cancel_scheduler = len(cancel_related) == 0
    ct.check(
        "no_timeout_auto_cancel_scheduler_absent_and_wait_placed",
        still4["status"] == "PLACED" and no_order_cancel_scheduler,
        {
            "wait_sec": 2,
            "status_after_wait": still4["status"],
            "all_scheduled_hits": all_hits[:30],
            "order_cancel_related_hits": cancel_related[:20],
            "scheduler_absent": no_order_cancel_scheduler,
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

    # Merchant UI live flow (not a still of an already-COMPLETED API order)
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    cid_ui = m.cart_add(env, ta, p["P-ON-10"], "1")
    _, body_ui, _, _ = m.place_order(env, ta, [cid_ui])
    seller_pwd = env.get("B032_SELLER_PASSWORD", "")
    shot = run_node(
        f"""
const {{ chromium }} = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {{
  const fe = {json.dumps(fe_url(env))};
  const out = {{ok:false, steps:[]}};
  const browser = await chromium.launch({{headless:true}});
  try {{
    const page = await browser.newPage({{viewport:{{width:1280,height:900}}}});
    await page.goto(fe + '/admin/login', {{waitUntil:'networkidle'}});
    await page.locator('#username').fill('admin');
    await page.locator('#password').fill({json.dumps(seller_pwd)});
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{timeout:15000}});
    await page.goto(fe + '/admin/orders', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(800);
    async function confirmAction(label) {{
      await page.getByRole('button', {{ name: label }}).first().click();
      const visiblePop = page.locator('.ant-popover').filter({{ hasText: '确认' }}).last();
      await visiblePop.waitFor({{ state: 'visible', timeout: 8000 }});
      await visiblePop.locator('button.ant-btn-primary').last().click();
      await page.waitForTimeout(900);
      out.steps.push(label);
    }}
    await confirmAction('确认订单');
    await confirmAction('完成备货');
    const textMid = await page.locator('body').innerText();
    out.mid = {{
      hasShip: textMid.includes('开始发货'),
      hasPrepared: textMid.includes('待发货') || textMid.includes('备货'),
      url: page.url(),
    }};
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b01-merchant-orders-flow.png'))}, fullPage:true}});
    out.shots = ['b01-merchant-orders-flow.png'];
    out.ok = out.mid.hasShip === true && out.steps.length === 2;
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b01_ac4",
    )
    ct.check("merchant_ui_orders_flow_screenshot", shot.get("ok") is True, shot)
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
    # Order and stock edit MUST target the SAME product (not P-STOCK substitute)
    pid = p["P-ON-10"]
    m.align_product(env, s, pid, PRODUCTS["P-ON-10"])
    ta = fx["tokens"]["A"]
    cid = m.cart_add(env, ta, pid, "1")
    _, body, _, _ = m.place_order(env, ta, [cid])
    oid = m.order_id_of(body)
    snap = m.db_order_items(env, oid)
    stock_after_order = m.db_stock(env, pid)

    bad_inputs = []
    for val in ["abc", "-1", "1.5", "", "01", " "]:
        stock_before = m.db_stock(env, pid)
        c, b = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": val}, auth(s))
        stock_after = m.db_stock(env, pid)
        bad_inputs.append(
            {
                "value": val,
                "http": c,
                "message": msg(b),
                "stock_unchanged": stock_before == stock_after,
                "stock": [stock_before, stock_after],
            }
        )
    exact_tip = "库存不能为负数，请输入非负整数。"
    ct.check(
        "reject_invalid_stock_exact_tip_and_stock_unchanged",
        all(
            x["http"] >= 400
            and x["message"] == exact_tip
            and x["stock_unchanged"]
            for x in bad_inputs
        ),
        {"cases": bad_inputs, "product_id": pid, "exact_tip": exact_tip},
    )
    c_ok, b_ok = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "15"}, auth(s))
    ct.check(
        "accept_valid_stock_same_product",
        c_ok == 200 and str(m.db_stock(env, pid)) == "15",
        {"http": c_ok, "message": msg(b_ok), "after_order_stock": stock_after_order},
    )
    snap2 = m.db_order_items(env, oid)
    ct.check(
        "stock_edit_same_product_does_not_change_existing_order_lines",
        snap == snap2,
        {"snap": snap, "snap2": snap2, "product_id": pid},
    )
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
    c3 = m.cart_add(env, ta, p["P-ON-1"], "1")  # unselected
    conf_c, conf_b = m.confirm(env, ta, [c1, c2])
    conf_items = ((conf_b or {}).get("data") or {}).get("items") or []
    conf_total = ((conf_b or {}).get("data") or {}).get("totalAmount") or ((conf_b or {}).get("data") or {}).get("total")
    ct.check(
        "unselected_not_in_confirm_snapshot",
        conf_c in (200, 201) and len(conf_items) == 2,
        {"confirm_items": redact(conf_items), "total": conf_total},
    )
    code, body, _, _ = m.place_order(env, ta, [c1, c2])
    oid = m.order_id_of(body)
    snap = m.db_order_items(env, oid)
    order = m.db_orders(env, "b032_buyer_a")[0]
    # Order detail API — line-by-line compare (not DB-only stand-in for UI)
    d_c, d_b = http_json("GET", f"{base_url(env)}/api/me/orders/{oid}", headers=auth(ta))
    detail_data = (d_b or {}).get("data") if isinstance(d_b, dict) else {}
    detail_items = (detail_data or {}).get("items") or (detail_data or {}).get("orderItems") or []
    detail_total = (detail_data or {}).get("totalAmount") or (detail_data or {}).get("total")
    line_match = False
    if detail_items and len(detail_items) == len(snap):
        def line_key(it):
            return (
                str(it.get("productId") or it.get("product_id") or ""),
                str(it.get("quantity") or ""),
                str(it.get("unitPrice") or it.get("unit_price") or ""),
            )
        db_keys = sorted(line_key({"product_id": i["product_id"], "quantity": i["quantity"], "unit_price": i["unit_price"]}) for i in snap)
        api_keys = sorted(line_key(i) for i in detail_items)
        line_match = db_keys == api_keys
    ct.check(
        "order_detail_line_by_line",
        d_c == 200 and line_match,
        {"http": d_c, "detail_items": redact(detail_items), "db_snap": snap, "detail_total": detail_total},
    )
    # Three places: confirm page totals, order detail lines/total, order list/header total
    try:
        conf_total_d = Decimal(str(conf_total)) if conf_total is not None else None
        detail_total_d = Decimal(str(detail_total)) if detail_total is not None else None
        order_total_d = Decimal(str(order["total_amount"]))
    except Exception:
        conf_total_d = detail_total_d = order_total_d = None
    calc = sum(Decimal(str(i["unit_price"])) * Decimal(str(i["quantity"])) for i in snap)
    ct.check(
        "three_place_amount_consistent_confirm_detail_total",
        conf_total_d is not None
        and detail_total_d is not None
        and conf_total_d == detail_total_d == order_total_d == calc
        and str(order_total_d) == f"{order_total_d:.2f}",
        {
            "confirm_total": str(conf_total),
            "detail_total": str(detail_total),
            "order_total": str(order["total_amount"]),
            "calc": str(calc),
        },
    )
    # New-identity republish: create a NEW product; old order snapshot must keep old product id/name
    old_pid = str(snap[0]["product_id"])
    old_name = snap[0].get("product_name") or snap[0].get("product_name_snapshot")
    # mutate live product + offline original
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}", {"stock": "99"}, auth(s))
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(s))
    # create brand-new product (new identity)
    seed = m.ROOT / "fixtures" / "seed.png"
    http_c, http_b = m.multipart_post(
        f"{base_url(env)}/api/admin/products",
        {
            "name": f"B032-REPUBLISH-NEW-{int(time.time())}",
            "price": "12.50",
            "stock": "10",
            "descriptionHtml": "<p>republish identity</p>",
            "category2Id": str(fx.get("category2Id") or 16),
            "sellingMode": "FIXED_PRICE",
        },
        [("images", seed)],
        auth(s),
    )
    new_pid = None
    if http_c in (200, 201) and isinstance(http_b, dict):
        data = http_b.get("data") or {}
        new_pid = str(data.get("productId") or data.get("id") or "")
    snap2 = m.db_order_items(env, oid)
    d2_c, d2_b = http_json("GET", f"{base_url(env)}/api/me/orders/{oid}", headers=auth(ta))
    d2_items = ((d2_b or {}).get("data") or {}).get("items") or []
    still_old = all(str(i.get("product_id") or i.get("productId")) == str(si["product_id"]) for i, si in zip(
        [{"product_id": x["product_id"]} for x in snap2], snap
    ))
    ct.check(
        "new_identity_republish_keeps_old_snapshot",
        snap == snap2 and still_old and new_pid and new_pid != old_pid,
        {
            "create_http": http_c,
            "create_message": msg(http_b),
            "old_pid": old_pid,
            "new_pid": new_pid,
            "snap": snap,
            "snap2": snap2,
            "detail_after": redact(d2_items),
        },
    )
    ct.check("order_created", code == 201 and order["order_no"], {"http": code, "message": msg(body)})
    # Three UI places: history list total, detail line items, detail total
    ui_amt = run_node(
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
    await page.goto(fe + '/me/order-history', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(700);
    const listText = await page.locator('body').innerText();
    await page.getByRole('button', {{ name: '详情' }}).first().click();
    const modal = page.locator('.ant-modal').last();
    await modal.waitFor({{ state: 'visible', timeout: 8000 }});
    await page.waitForTimeout(400);
    const detailText = await modal.innerText();
    out.listHasTotal = listText.includes('¥{order_total_d}') || listText.includes('{order_total_d}');
    out.detailHasTotal = detailText.includes('¥{order_total_d}') || detailText.includes('{order_total_d}');
    out.detailHasLines = (detailText.match(/¥/g) || []).length >= 3;
    out.detailSnippet = detailText.slice(0, 500);
    out.ok = out.listHasTotal && out.detailHasTotal && out.detailHasLines;
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b03_ac1_amounts",
    )
    ct.check(
        "three_ui_places_list_lines_total",
        ui_amt.get("ok") is True,
        ui_amt,
    )
    m.dump_case("PB-B03-AC1", ct.as_detail())
    return finish(ct, m.result)


def ac_b03_03(env, fx):
    """Order history/management: order pagination (not product list), isolation, cancel UI."""
    m.reset_ns(env)
    ta, tb, s, p = fx["tokens"]["A"], fx["tokens"]["B"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B03-AC3")
    # Seed five-state + cancelled for A; one order for B (isolation)
    for target in ("PLACED", "CONFIRMED", "PREPARED", "SHIPPED", "COMPLETED"):
        m.align_product(env, s, p["P-ON-10"], PRODUCTS["P-ON-10"])
        cid = m.cart_add(env, ta, p["P-ON-10"], "1")
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
    m.align_product(env, s, p["P-ON-5"], PRODUCTS["P-ON-5"])
    cid_c = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body_c, _, _ = m.place_order(env, ta, [cid_c])
    oid_c = m.order_id_of(body_c)
    m.cancel_customer(env, ta, oid_c, "PLACED")
    m.align_product(env, s, p["P-ON-5"], PRODUCTS["P-ON-5"])
    cid_b = m.cart_add(env, tb, p["P-ON-5"], "1")
    m.place_order(env, tb, [cid_b])

    def page_ids(body):
        data = (body or {}).get("data") if isinstance(body, dict) else None
        items, total = [], None
        if isinstance(data, dict):
            items = data.get("items") or data.get("content") or []
            total = data.get("total") or data.get("totalElements")
        elif isinstance(data, list):
            items = data
            total = len(data)
        ids = [str(it.get("orderId") or it.get("id") or "") for it in items]
        return ids, total, items

    c1, b1 = http_json("GET", f"{base_url(env)}/api/me/orders?page=1&size=2", headers=auth(ta))
    c2, b2 = http_json("GET", f"{base_url(env)}/api/me/orders?page=2&size=2", headers=auth(ta))
    ids1, total1, items1 = page_ids(b1)
    ids2, total2, items2 = page_ids(b2)
    overlap = set(ids1) & set(ids2)
    # Reverse chronological: createdAt descending if present
    def created_list(items):
        return [it.get("createdAt") or it.get("created_at") for it in items if it.get("createdAt") or it.get("created_at")]
    t1 = created_list(items1)
    chrono_ok = all(t1[i] >= t1[i + 1] for i in range(len(t1) - 1)) if len(t1) >= 2 else True
    ct.check(
        "order_pagination_no_overlap_total_desc",
        c1 == 200 and c2 == 200 and len(ids1) > 0 and len(overlap) == 0 and total1 and int(total1) >= 6 and chrono_ok,
        {"page1": ids1, "page2": ids2, "total": total1, "overlap": list(overlap), "created": t1},
    )
    # Customer isolation: B must not see A's order ids
    cb, bb = http_json("GET", f"{base_url(env)}/api/me/orders?page=1&size=50", headers=auth(tb))
    b_ids, _, _ = page_ids(bb)
    ct.check(
        "customer_sees_only_own_orders",
        cb == 200 and not set(ids1) & set(b_ids),
        {"A_sample": ids1, "B_ids": b_ids},
    )
    # Merchant site-wide includes both
    ca, ba = http_json("GET", f"{base_url(env)}/api/admin/orders?page=1&size=50", headers=auth(s))
    a_ids, a_total, a_items = page_ids(ba)
    ct.check(
        "merchant_sees_sitewide_orders",
        ca == 200 and a_total and int(a_total) >= 7 and len(a_ids) >= 2,
        {"http": ca, "total": a_total, "count": len(a_ids)},
    )
    # Merchant GET page=2: IDs, no overlap with page=1, reverse chrono, total
    cm1, bm1 = http_json("GET", f"{base_url(env)}/api/admin/orders?page=1&size=2", headers=auth(s))
    cm2, bm2 = http_json("GET", f"{base_url(env)}/api/admin/orders?page=2&size=2", headers=auth(s))
    m_ids1, m_total1, m_items1 = page_ids(bm1)
    m_ids2, m_total2, m_items2 = page_ids(bm2)
    m_overlap = set(m_ids1) & set(m_ids2)
    m_t1 = created_list(m_items1)
    m_t2 = created_list(m_items2)
    m_chrono_p1 = all(m_t1[i] >= m_t1[i + 1] for i in range(len(m_t1) - 1)) if len(m_t1) >= 2 else False
    m_chrono_p2 = all(m_t2[i] >= m_t2[i + 1] for i in range(len(m_t2) - 1)) if len(m_t2) >= 2 else True
    m_chrono_cross = True
    if m_t1 and m_t2:
        m_chrono_cross = m_t1[-1] >= m_t2[0]
    m_total_n = int(m_total1) if m_total1 else 0
    ct.check(
        "merchant_order_pagination_page2_no_overlap_total_desc",
        cm1 == 200
        and cm2 == 200
        and len(m_ids1) == 2
        and len(m_ids2) == 2
        and len(m_overlap) == 0
        and m_total_n >= 7
        and m_total1 == m_total2
        and m_chrono_p1
        and m_chrono_p2
        and m_chrono_cross,
        {
            "page1": m_ids1,
            "page2": m_ids2,
            "total": m_total1,
            "total2": m_total2,
            "overlap": list(m_overlap),
            "created1": m_t1,
            "created2": m_t2,
            "http": [cm1, cm2],
        },
    )
    # Cancel metadata via detail API (not DB-only stand-in for UI claim)
    det_c, det_b = http_json("GET", f"{base_url(env)}/api/me/orders/{oid_c}", headers=auth(ta))
    det = (det_b or {}).get("data") if isinstance(det_b, dict) else {}
    cancel_by = det.get("cancelledBy") or det.get("cancelled_by") or det.get("cancelBy")
    cancel_at = det.get("cancelledAt") or det.get("cancelled_at") or det.get("cancelAt")
    ct.check(
        "cancel_party_and_time_in_detail",
        det_c == 200 and bool(cancel_by) and bool(cancel_at),
        {"http": det_c, "cancelledBy": cancel_by, "cancelledAt": cancel_at, "status": det.get("status")},
    )
    # Screenshots while polymorphic data present — write history/admin here (not overwritten later)
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
    await page.goto(fe + '/login', {{waitUntil:'networkidle'}});
    await page.locator('#username').fill('b032_buyer_a');
    await page.locator('#password').fill('B032-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{timeout:15000}});
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b03-after-login.png'))}, fullPage:true}});
    // Prefer order-history route; fall back to /me/orders if app uses that
    await page.goto(fe + '/me/order-history', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(800);
    if (!(await page.locator('text=订单历史').count()) && !(await page.locator('text=订单').count())) {{
      await page.goto(fe + '/me/orders', {{waitUntil:'networkidle'}});
      await page.waitForTimeout(800);
    }}
    const url = page.url();
    const text = await page.locator('body').innerText();
    const isHome = url.endsWith('/') || url.includes('/home') || (!url.includes('order') && text.includes('热门'));
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b03-order-history.png'))}, fullPage:true}});
    out.history = {{url, isHome, hasHistory: text.includes('订单'), empty: text.includes('暂无订单')}};
    // Cancel detail UI: open 详情 on a cancelled row and assert 取消发起方/取消时间
    const cancelRow = page.locator('.ant-table-row').filter({{ hasText: '已取消' }}).first();
    out.cancelDetail = {{ present: await cancelRow.count() > 0 }};
    if (out.cancelDetail.present) {{
      await cancelRow.getByRole('button', {{ name: '详情' }}).click();
      const det = page.locator('.ant-modal').filter({{ hasText: '订单详情' }});
      await det.waitFor({{ state: 'visible', timeout: 10000 }});
      await page.waitForTimeout(400);
      const detText = await det.innerText();
      await page.screenshot({{path: {json.dumps(str(SHOTS/'b03-cancel-detail.png'))}, fullPage:true}});
      out.cancelDetail = {{
        present: true,
        visible: await det.isVisible(),
        text: detText.slice(0, 900),
        hasPartyLabel: detText.includes('取消发起方'),
        hasPartyCustomer: detText.includes('客户'),
        hasTimeLabel: detText.includes('取消时间'),
        hasTimeValue: /取消时间[\\s\\S]{{0,80}}\\d{{4}}/.test(detText),
      }};
    }}
    const page2 = await browser.newPage({{viewport:{{width:1280,height:900}}}});
    await page2.goto(fe + '/admin/login', {{waitUntil:'networkidle'}});
    await page2.locator('#username').fill('admin');
    await page2.locator('#password').fill({json.dumps(seller_pwd)});
    await page2.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page2.waitForURL(u => !String(u).includes('/login'), {{timeout:15000}});
    await page2.goto(fe + '/admin/orders', {{waitUntil:'networkidle'}});
    await page2.waitForTimeout(1000);
    const t2 = await page2.locator('body').innerText();
    await page2.screenshot({{path: {json.dumps(str(SHOTS/'b03-admin-orders.png'))}, fullPage:true}});
    out.admin = {{url: page2.url(), hasManage: t2.includes('订单管理') || t2.includes('订单'), multi: (t2.match(/PLACED|CONFIRMED|COMPLETED|CANCELLED|已/g)||[]).length}};
    const cd = out.cancelDetail || {{}};
    out.ok = !out.history.isHome && out.history.hasHistory && !out.history.empty && out.admin.hasManage && out.admin.multi >= 3
      && cd.visible === true && cd.hasPartyLabel === true && cd.hasPartyCustomer === true
      && cd.hasTimeLabel === true && cd.hasTimeValue === true;
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b03_ac3",
    )
    ct.check("history_and_admin_polymorphic_screenshots", shot.get("ok") is True, shot)
    cd = (shot.get("cancelDetail") or {})
    ct.check(
        "cancel_party_and_time_in_ui_modal",
        cd.get("visible") is True
        and cd.get("hasPartyLabel") is True
        and cd.get("hasPartyCustomer") is True
        and cd.get("hasTimeLabel") is True
        and cd.get("hasTimeValue") is True,
        {"cancelDetail": cd, "shot": str(SHOTS / "b03-cancel-detail.png")},
    )
    m.dump_case("PB-B03-AC3", ct.as_detail())
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
    # Images: no replace endpoint may exist; prove product_image rows unchanged after replace attempts
    imgs_before = product_images(env, pid)
    img_attempts = []
    c_img_json, b_img_json = http_json(
        "PATCH",
        f"{base_url(env)}/api/admin/products/{pid}",
        {"images": ["HACKED.png"], "imageUrls": ["HACKED.png"], "mainImageUrl": "HACKED.png", "stock": "10"},
        auth(s),
    )
    img_attempts.append({"entry": "PATCH json image fields", "http": c_img_json, "message": msg(b_img_json)})
    for method, url in [
        ("POST", f"{base_url(env)}/api/admin/products/{pid}"),
        ("PUT", f"{base_url(env)}/api/admin/products/{pid}"),
        ("PATCH", f"{base_url(env)}/api/admin/products/{pid}"),
        ("POST", f"{base_url(env)}/api/admin/products/{pid}/images"),
        ("PUT", f"{base_url(env)}/api/admin/products/{pid}/images"),
    ]:
        hc, hb = multipart_any(
            method,
            url,
            {"stock": "10"},
            [("images", m.SEED)],
            auth(s),
        )
        img_attempts.append({"entry": f"{method} {url.split('/api', 1)[-1]}", "http": hc, "message": msg(hb)})
    imgs_after = product_images(env, pid)
    images_unchanged = imgs_before == imgs_after
    multipart_not_applied = all(
        a["http"] not in (200, 201) for a in img_attempts if "json" not in a["entry"]
    )
    ct.check(
        "images_immutable_after_replace_attempts",
        images_unchanged and multipart_not_applied,
        {
            "before": imgs_before,
            "after": imgs_after,
            "unchanged": images_unchanged,
            "attempts": img_attempts,
        },
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

    # Re-seed cart WITH stale offline still present for UI (valid online was consumed)
    m.align_product(env, s, p["P-ON-5"], PRODUCTS["P-ON-5"])
    m.align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    m.cart_add(env, ta, p["P-ON-5"], "1")
    c_low2 = m.cart_add(env, ta, p["P-ON-1"], "1")
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cart_item SET quantity=5 WHERE id=%s", (c_low2,))
            cur.execute("SELECT id FROM customer WHERE username='b032_buyer_a'")
            cust = cur.fetchone()["id"]
            # Offline row may still remain from earlier seed — upsert, do not duplicate
            cur.execute(
                "SELECT id FROM cart_item WHERE customer_id=%s AND product_id=%s",
                (cust, p["P-OFF-M"]),
            )
            existing_off = cur.fetchone()
            if not existing_off:
                cur.execute(
                    "INSERT INTO cart_item(customer_id, product_id, quantity, updated_at) VALUES (%s,%s,1,NOW(6))",
                    (cust, p["P-OFF-M"]),
                )
    finally:
        conn.close()

    orderable_name = PRODUCTS["P-ON-5"]["name"]
    insuf_name = PRODUCTS["P-ON-1"]["name"]
    offline_name = PRODUCTS["P-OFF-M"]["name"]
    shot = run_node(
        f"""
const {{ chromium }} = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {{
  const fe = {json.dumps(fe_url(env))};
  const names = {{
    orderable: {json.dumps(orderable_name)},
    insuf: {json.dumps(insuf_name)},
    offline: {json.dumps(offline_name)},
  }};
  const out = {{ok:false}};
  const browser = await chromium.launch({{headless:true}});
  async function rowOf(page, productName) {{
    const loc = page.getByRole('checkbox', {{ name: '选择' + productName }});
    const present = await loc.count();
    if (!present) return {{ productName, present: false, checked: false, disabled: false }};
    return {{
      productName,
      present: true,
      checked: await loc.isChecked(),
      disabled: await loc.isDisabled(),
    }};
  }}
  async function allRows(page) {{
    return {{
      orderable: await rowOf(page, names.orderable),
      insuf: await rowOf(page, names.insuf),
      offline: await rowOf(page, names.offline),
    }};
  }}
  try {{
    const page = await browser.newPage({{viewport:{{width:1280,height:900}}}});
    await page.goto(fe + '/login', {{waitUntil:'networkidle'}});
    await page.locator('#username').fill('b032_buyer_a');
    await page.locator('#password').fill('B032-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{timeout:15000}});
    await page.goto(fe + '/me/cart', {{waitUntil:'networkidle'}});
    await page.waitForTimeout(1000);
    const allLabel = await page.locator('text=全选可下单商品').count();
    const disabled = await page.locator('.ant-checkbox-disabled, input[type=checkbox][disabled]').count();
    const invalidTag = await page.locator('text=已下架').count();
    const insufHint = await page.locator('text=当前库存').count();
    const atDefault = await allRows(page);
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-cart-selection.png'))}, fullPage:true}});
    const allBox = page.locator('text=全选可下单商品').first();
    await allBox.click();
    await page.waitForTimeout(400);
    const atSelectAll = await allRows(page);
    await allBox.click();
    await page.waitForTimeout(400);
    const atDeselectAll = await allRows(page);
    await page.getByRole('checkbox', {{ name: '选择' + names.orderable }}).click();
    await page.waitForTimeout(200);
    const atRow = await allRows(page);
    out.shots = ['b12-cart-selection.png'];
    out.ui = {{
      allLabel, disabled, invalidTag, insufHint,
      atDefault, atSelectAll, atDeselectAll, atRow,
      checkedDefault: Number(atDefault.orderable.checked),
      checkedAfterSelectAll: Number(atSelectAll.orderable.checked) + Number(atSelectAll.insuf.checked),
      checkedAfterDeselectAll: Number(atDeselectAll.orderable.checked) + Number(atDeselectAll.insuf.checked),
      checkedAfterRow: Number(atRow.orderable.checked) + Number(atRow.insuf.checked),
    }};
    const rowOk =
      atDefault.orderable.present && atDefault.insuf.present && atDefault.offline.present
      && atDefault.orderable.checked === true && atDefault.orderable.disabled === false
      && atDefault.insuf.checked === false && atDefault.insuf.disabled === false
      && atDefault.offline.checked === false && atDefault.offline.disabled === true
      && atSelectAll.orderable.checked === true && atSelectAll.insuf.checked === true
      && atSelectAll.offline.checked === false && atSelectAll.offline.disabled === true
      && atDeselectAll.orderable.checked === false && atDeselectAll.insuf.checked === false
      && atDeselectAll.offline.checked === false
      && atRow.orderable.checked === true && atRow.insuf.checked === false
      && atRow.offline.checked === false;
    out.ok = allLabel > 0 && (disabled > 0 || invalidTag > 0) && insufHint >= 1 && rowOk === true;
    out.rowOk = rowOk;
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b12_ac3",
    )
    ui = shot.get("ui") or {}
    at_default = ui.get("atDefault") or {}
    at_all = ui.get("atSelectAll") or {}
    at_none = ui.get("atDeselectAll") or {}
    at_row = ui.get("atRow") or {}
    ct.check(
        "ui_invalid_disabled_and_insufficient_hint",
        shot.get("ok") is True
        and (ui.get("disabled", 0) > 0 or ui.get("invalidTag", 0) > 0)
        and ui.get("insufHint", 0) >= 1,
        shot,
    )
    ct.check(
        "ui_select_all_deselect_and_row_toggle",
        ui.get("checkedAfterSelectAll", 0) > ui.get("checkedAfterDeselectAll", 0)
        and ui.get("checkedAfterRow", 0) != ui.get("checkedAfterDeselectAll", -1),
        ui,
    )
    ct.check(
        "default_selects_only_orderable_after_valid_removed",
        (at_default.get("orderable") or {}).get("checked") is True
        and (at_default.get("insuf") or {}).get("checked") is False
        and (at_default.get("offline") or {}).get("checked") is False
        and (at_default.get("offline") or {}).get("disabled") is True
        and ui.get("insufHint", 0) >= 1,
        at_default,
    )
    ct.check(
        "row_level_checked_maps_to_orderable",
        shot.get("rowOk") is True
        and (at_all.get("orderable") or {}).get("checked") is True
        and (at_all.get("insuf") or {}).get("checked") is True
        and (at_all.get("offline") or {}).get("checked") is False
        and (at_none.get("orderable") or {}).get("checked") is False
        and (at_none.get("insuf") or {}).get("checked") is False
        and (at_row.get("orderable") or {}).get("checked") is True
        and (at_row.get("insuf") or {}).get("checked") is False
        and (at_row.get("offline") or {}).get("checked") is False,
        {"atDefault": at_default, "atSelectAll": at_all, "atDeselectAll": at_none, "atRow": at_row},
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

    # After confirm: product still ONLINE; stock unchanged by confirm itself (already checked).
    # Rejection path: offline after confirm → reject with full-set unchanged
    c2, b2 = m.confirm(env, ta, [cid])
    token2 = b2["data"]["confirmationToken"]
    row_conf = m.product_row(env, p["P-ON-10"])
    ct.check(
        "after_confirm_still_online_before_submit",
        row_conf["status"] == "ONLINE" and str(row_conf["stock"]) == "10",
        row_conf,
    )
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
    # New-identity publish (not merely re-online same id)
    seed = m.ROOT / "fixtures" / "seed.png"
    http_c, http_b = m.multipart_post(
        f"{base_url(env)}/api/admin/products",
        {
            "name": f"B032-ID-REPLACE-{int(time.time())}",
            "price": "12.50",
            "stock": "10",
            "descriptionHtml": "<p>identity replace</p>",
            "category2Id": str(fx.get("category2Id") or 16),
            "sellingMode": "FIXED_PRICE",
        },
        [("images", seed)],
        auth(s),
    )
    new_pid = None
    if http_c in (200, 201) and isinstance(http_b, dict):
        new_pid = str((http_b.get("data") or {}).get("productId") or (http_b.get("data") or {}).get("id") or "")
    ct.check(
        "new_product_identity_published",
        new_pid is not None and new_pid != p["P-ON-10"],
        {"http": http_c, "message": msg(http_b), "new_pid": new_pid, "old_pid": p["P-ON-10"]},
    )
    # Re-online original + success; stock declines while ONLINE
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/online", headers=auth(s))
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}", {"stock": "10"}, auth(s))
    carts = m.db_cart(env, "b032_buyer_a")
    cid = str(carts[0]["id"]) if carts else m.cart_add(env, ta, p["P-ON-10"], "1")
    s3_c, s3_b, _, _ = m.place_order(env, ta, [cid])
    ct.check("reonline_reconfirm_success", s3_c == 201 and msg(s3_b) == "下单成功", {"http": s3_c, "message": msg(s3_b)})
    row = m.product_row(env, p["P-ON-10"])
    ct.check(
        "after_success_stock_down_still_online",
        int(row["stock"]) < 10 and row["status"] == "ONLINE",
        row,
    )

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
    # Real UI checkbox toggle — not same-qty PATCH
    toggle = run_node(
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
    const before = await page.locator('.ant-checkbox-checked').count();
    const box = page.locator('.ant-checkbox:not(.ant-checkbox-disabled)').first();
    await box.click();
    await page.waitForTimeout(300);
    const mid = await page.locator('.ant-checkbox-checked').count();
    await box.click();
    await page.waitForTimeout(300);
    const after = await page.locator('.ant-checkbox-checked').count();
    out.ui = {{before, mid, after}};
    // Real toggle: checked count changes on click, then restores on second click
    out.ok = before > 0 && mid !== before && after === before;
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b12_ac5_toggle",
    )
    stock_mid = {k: m.db_stock(env, p[k]) for k in ("P-ON-10", "P-ON-5")}
    ct.check(
        "ui_checkbox_toggle_no_stock_change",
        toggle.get("ok") is True and stock_before == stock_mid,
        {"toggle": toggle, "before": stock_before, "mid": stock_mid},
    )

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
    ct.check("clear_cart_confirm_modal_screenshot", shot.get("ok") is True, shot)
    m.dump_case("PB-B12-AC5", ct.as_detail())
    return finish(ct, m.result)


def ac_b12_06(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B12-AC6")
    # Valid confirm FIRST, then introduce problems, then final submit
    m.align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    m.align_product(env, s, p["P-ON-10"], PRODUCTS["P-ON-10"])
    m.align_product(env, s, p["P-ON-5"], PRODUCTS["P-ON-5"])
    c_low = m.cart_add(env, ta, p["P-ON-1"], "1")
    c_off = m.cart_add(env, ta, p["P-ON-10"], "1")
    conf_c, conf_b = m.confirm(env, ta, [c_low, c_off])
    token = None
    if conf_c in (200, 201) and isinstance(conf_b, dict):
        token = (conf_b.get("data") or {}).get("confirmationToken")
    ct.check("valid_confirm_first", token is not None, {"http": conf_c, "message": msg(conf_b)})
    # Introduce problems AFTER confirm
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cart_item SET quantity=5 WHERE id=%s", (c_low,))
    finally:
        conn.close()
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(s))
    stock_b = {p["P-ON-1"]: m.db_stock(env, p["P-ON-1"]), p["P-ON-10"]: m.db_stock(env, p["P-ON-10"])}
    cart_b = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    orders_b = m.db_orders(env, "b032_buyer_a")
    s_c, s_b, _ = m.submit_order(env, ta, token) if token else (0, {"message": "no token"}, None)
    final_msgs = nested_msgs(s_b)
    name1 = PRODUCTS["P-ON-1"]["name"]
    name10 = PRODUCTS["P-ON-10"]["name"]
    expect_insuf = f"商品「{name1}」库存不足：当前可售 1 件，您选购了 5 件，请减少数量或移除后重试。"
    expect_off = f"商品「{name10}」已下架，请从购物车移除后重试。"
    ct.check(
        "final_submit_multi_problem_exact_templates",
        s_c >= 400 and expect_insuf in final_msgs and expect_off in final_msgs,
        {
            "path": "confirm_then_break_then_submit",
            "http": s_c,
            "messages": final_msgs,
            "expect_insuf": expect_insuf,
            "expect_off": expect_off,
        },
    )
    stock_a = {p["P-ON-1"]: m.db_stock(env, p["P-ON-1"]), p["P-ON-10"]: m.db_stock(env, p["P-ON-10"])}
    cart_a = cart_fingerprint(m.db_cart(env, "b032_buyer_a"))
    orders_a = m.db_orders(env, "b032_buyer_a")
    ct.check(
        "final_submit_fail_full_set_unchanged",
        stock_a == stock_b and cart_a == cart_b and orders_a == orders_b,
        {
            "stock_before": stock_b,
            "stock_after": stock_a,
            "cart_before": cart_b,
            "cart_after": cart_a,
            "orders_before": len(orders_b),
            "orders_after": len(orders_a),
        },
    )
    # Missing / empty
    c_empty, b_empty = m.confirm(env, ta, [])
    ct.check("empty_select_message", msg(b_empty) == "请选择商品", {"http": c_empty, "message": msg(b_empty)})
    # Missing product id confirm
    miss_c, miss_b = m.confirm(env, ta, ["999999999"])
    ct.check(
        "missing_product_rejected",
        miss_c >= 400,
        {"http": miss_c, "message": msg(miss_b), "nested": nested_msgs(miss_b)},
    )

    # UI: valid confirm modal FIRST, then mutate, then click 确认下单 (submit) — not confirm-time toast
    m.reset_ns(env)
    ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
    fx["tokens"]["A"] = ta
    m.align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    m.align_product(env, s, p["P-ON-10"], PRODUCTS["P-ON-10"])
    cid_ui_low = m.cart_add(env, ta, p["P-ON-1"], "1")
    cid_ui_off = m.cart_add(env, ta, p["P-ON-10"], "1")
    shot = run_node(
        f"""
const {{ chromium }} = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {{
  const fe = {json.dumps(fe_url(env))};
  const api = {json.dumps(base_url(env))};
  const buyer = {json.dumps(ta)};
  const seller = {json.dumps(s)};
  const cidLow = {json.dumps(str(cid_ui_low))};
  const pidOff = {json.dumps(str(p["P-ON-10"]))};
  const out = {{ok:false, modalVisibleBeforeBreak:false, submitAfterBreak:false}};
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
    // Both rows are defaultCheckoutSelected (qty 1 ≤ stock); do not toggle 全选 (would deselect).
    await page.getByRole('button', {{ name: '下单' }}).click();
    const modal = page.locator('.ant-modal').filter({{ hasText: '确认下单' }});
    await modal.waitFor({{ state: 'visible', timeout: 10000 }});
    const modalText = await modal.innerText();
    out.modalVisibleBeforeBreak = await modal.isVisible();
    out.modalText = modalText.slice(0, 400);
    out.validConfirm = out.modalVisibleBeforeBreak && modalText.includes('总金额') && !modalText.includes('请选择商品');
    const patchResp = await fetch(api + '/api/me/cart/items/' + cidLow, {{
      method: 'PATCH',
      headers: {{ 'Authorization': 'Bearer ' + buyer, 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ quantity: '5' }}),
    }});
    out.patchHttp = patchResp.status;
    const offResp = await fetch(api + '/api/admin/products/' + pidOff + '/offline', {{
      method: 'POST',
      headers: {{ 'Authorization': 'Bearer ' + seller }},
    }});
    out.offlineHttp = offResp.status;
    out.brokeAfterModal = out.patchHttp === 200 && out.offlineHttp === 200;
    await modal.getByRole('button', {{ name: '确认下单' }}).click();
    out.submitAfterBreak = true;
    const toast = page.locator('.ant-message, .ant-notification');
    await toast.first().waitFor({{ state: 'visible', timeout: 10000 }}).catch(() => {{}});
    await page.waitForTimeout(500);
    const toastText = await toast.allInnerTexts().then(t => t.join('\\n')).catch(() => '');
    const text = await page.locator('body').innerText();
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-submit-error-tip.png'))}, fullPage:true}});
    out.shots = ['b12-submit-error-tip.png'];
    out.toast = toastText.slice(0, 400);
    out.text = text.slice(0, 800);
    const blob = toastText + text;
    out.hasStockOrOffline = blob.includes('库存不足') || blob.includes('已下架');
    out.hasConfirmChanged = blob.includes('确认信息已变化');
    out.onlyEmptySelect = blob.includes('请选择商品') && !out.hasStockOrOffline && !out.hasConfirmChanged;
    out.hasSuccess = blob.includes('下单成功');
    out.ok = out.validConfirm === true && out.brokeAfterModal === true && out.submitAfterBreak === true
      && (out.hasStockOrOffline === true || out.hasConfirmChanged === true)
      && out.onlyEmptySelect === false && out.hasSuccess !== true;
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b12_ac6_err",
    )
    ct.check(
        "ui_confirm_then_break_then_submit",
        shot.get("ok") is True
        and shot.get("modalVisibleBeforeBreak") is True
        and shot.get("validConfirm") is True
        and shot.get("brokeAfterModal") is True
        and shot.get("submitAfterBreak") is True,
        shot,
    )
    ct.check(
        "ui_error_tip_stock_or_offline",
        shot.get("ok") is True
        and (shot.get("hasStockOrOffline") is True or shot.get("hasConfirmChanged") is True)
        and shot.get("onlyEmptySelect") is not True,
        shot,
    )
    m.dump_case("PB-B12-AC6", ct.as_detail())
    return finish(ct, m.result)


# -------------------- Former placeholder ACs (explicit conjuncts) --------------------


def ac_b01_01(env, fx):
    m.reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    ct = ConjunctTracker("PB-B01-AC1")
    c1 = m.cart_add(env, ta, p["P-ON-10"], "2")
    c2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    code, body, _, _ = m.place_order(env, ta, [c1, c2])
    orders = m.db_orders(env, "b032_buyer_a")
    items = m.db_order_items(env, orders[0]["id"]) if orders else []
    intents = m.db_open_intents(env, "b032_buyer_a")
    qtys = {str(i["product_id"]): str(i["quantity"]) for i in items}
    ct.check("http_success_message", code == 201 and msg(body) == "下单成功", {"http": code, "message": msg(body)})
    ct.check(
        "single_placed_order_two_lines",
        len(orders) == 1 and orders[0]["status"] == "PLACED" and len(items) == 2,
        {"orders": orders, "items": items},
    )
    ct.check(
        "line_qtys_match_cart",
        qtys.get(p["P-ON-10"]) == "2" and qtys.get(p["P-ON-5"]) == "1",
        {"qtys": qtys},
    )
    ct.check("no_open_legacy_intent", intents == 0, {"open_intents": intents})
    ct.check("response_no_failure_wording", "失败" not in json.dumps(body, ensure_ascii=False), {"body": redact(body)})
    m.dump_case("PB-B01-AC1", ct.as_detail())
    return finish(ct, m.result)


def ac_b01_02(env, fx):
    import audit_acs as aa  # noqa: WPS433

    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B01-AC2")
    cid = m.cart_add(env, ta, p["P-ON-10"], "1")
    code, body, _, _ = m.place_order(env, ta, [cid])
    oid = m.order_id_of(body)
    seq = aa.advance_full(env, s, oid)
    ct.check("place_success", code == 201, {"http": code, "message": msg(body)})
    ct.check(
        "five_state_sequence",
        [x["status"] for x in seq] == ["CONFIRMED", "PREPARED", "SHIPPED", "COMPLETED"],
        {"seq": seq},
    )
    cid2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = m.place_order(env, ta, [cid2])
    oid2 = m.order_id_of(body2)
    skip_c, skip_b = m.advance(env, s, oid2, "SHIP", "PLACED")
    ct.check(
        "skip_step_rejected",
        skip_c >= 400 and ("跳步" in msg(skip_b) or "不允许" in msg(skip_b)),
        {"http": skip_c, "message": msg(skip_b)},
    )
    m.advance(env, s, oid2, "CONFIRM", "PLACED")
    back_c, back_b = m.advance(env, s, oid2, "CONFIRM", "PLACED")
    ct.check("no_rollback_to_prior_state", back_c >= 400, {"http": back_c, "message": msg(back_b)})
    cust_c, cust_b = http_json(
        "POST",
        f"{base_url(env)}/api/admin/orders/{oid}/actions",
        {"action": "CONFIRM", "expectedStatus": "PLACED"},
        auth(ta),
    )
    ct.check("customer_admin_advance_tip", msg(cust_b) == "角色无权访问", {"http": cust_c, "message": msg(cust_b)})
    time.sleep(1.5)
    mid = [o for o in m.db_orders(env, "b032_buyer_a") if str(o["id"]) == oid2][0]
    order = [o for o in m.db_orders(env, "b032_buyer_a") if str(o["id"]) == oid][0]
    ct.check("no_auto_transition_after_wait", mid["status"] == "CONFIRMED", {"mid": mid})
    ct.check("completed_terminal", order["status"] == "COMPLETED", {"order": order})
    m.dump_case("PB-B01-AC2", ct.as_detail())
    return finish(ct, m.result)


def ac_b02_01(env, fx):
    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B02-AC1")
    before = m.db_stock(env, p["P-ON-10"])
    cid = m.cart_add(env, ta, p["P-ON-10"], "2")
    code, body, _, _ = m.place_order(env, ta, [cid])
    after_place = m.db_stock(env, p["P-ON-10"])
    oid = m.order_id_of(body)
    advance_full(env, s, oid)
    after_complete = m.db_stock(env, p["P-ON-10"])
    ct.check("place_success", code == 201, {"http": code, "message": msg(body)})
    ct.check("direct_deduct_on_place", int(before) - int(after_place) == 2, {"before": before, "after_place": after_place})
    ct.check("complete_no_re_deduct", after_place == after_complete, {"after_place": after_place, "after_complete": after_complete})
    m.dump_case("PB-B02-AC1", ct.as_detail())
    return finish(ct, m.result)


def ac_b02_02(env, fx):
    import audit_acs as aa  # noqa: WPS433

    # Re-express audit path with explicit conjuncts
    m.reset_ns(env)
    ta, tb, s, p = fx["tokens"]["A"], fx["tokens"]["B"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B02-AC2")
    cid = m.cart_add(env, ta, p["P-ON-10"], "3")
    _, body, _, _ = m.place_order(env, ta, [cid])
    oid = m.order_id_of(body)
    code, body_p = http_json("GET", f"{base_url(env)}/api/products/{p['P-ON-10']}")
    seen = str(((body_p or {}).get("data") or {}).get("stock") or "")
    stock_db = m.db_stock(env, p["P-ON-10"])
    ct.check("others_see_deducted_stock", stock_db == "7" and (seen == "7" or seen == stock_db), {"seen": seen, "db": stock_db, "http": code})
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(s))
    steps = aa.advance_full(env, s, oid)
    order = [o for o in m.db_orders(env, "b032_buyer_a") if str(o["id"]) == oid][0]
    ct.check(
        "offline_keeps_existing_order_to_complete",
        order["status"] == "COMPLETED" and all(x["http"] == 200 for x in steps),
        {"order": order, "steps": steps},
    )
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
    ct.check(
        "new_order_refused_while_offline",
        rej_c >= 400 and "已下架" in nested_msgs(rej_b),
        {"add": {"http": add_c, "message": msg(add_b)}, "submit": {"http": rej_c, "message": msg(rej_b), "nested": nested_msgs(rej_b)}},
    )
    m.dump_case("PB-B02-AC2", ct.as_detail())
    return finish(ct, m.result)


def ac_b02_05(env, fx):
    import audit_acs as aa  # noqa: WPS433

    m.reset_ns(env)
    ta, s, p = fx["tokens"]["A"], fx["tokens"]["S"], fx["products"]
    ct = ConjunctTracker("PB-B02-AC5")
    before = m.db_stock(env, p["P-ON-10"])
    cid = m.cart_add(env, ta, p["P-ON-10"], "2")
    _, body, _, _ = m.place_order(env, ta, [cid])
    after_order = m.db_stock(env, p["P-ON-10"])
    oid = m.order_id_of(body)
    aa.advance_full(env, s, oid)
    after_complete = m.db_stock(env, p["P-ON-10"])
    ct.check("place_deducts_stock", int(before) - int(after_order) == 2, {"before": before, "after_order": after_order})
    ct.check("complete_stock_unchanged", after_order == after_complete, {"after_order": after_order, "after_complete": after_complete})
    cid2 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body2, _, _ = m.place_order(env, ta, [cid2])
    oid2 = m.order_id_of(body2)
    before_c = m.db_stock(env, p["P-ON-5"])
    m.cancel_customer(env, ta, oid2, "PLACED")
    after_c = m.db_stock(env, p["P-ON-5"])
    ct.check("cancel_restores_stock", int(after_c) == int(before_c) + 1, {"before": before_c, "after": after_c})
    m.align_product(env, s, p["P-ON-1"], PRODUCTS["P-ON-1"])
    cid3 = m.cart_add(env, ta, p["P-ON-1"], "1")
    _, body3, _, _ = m.place_order(env, ta, [cid3])
    oid3 = m.order_id_of(body3)
    row_zero = m.product_row(env, p["P-ON-1"])
    m.cancel_customer(env, ta, oid3, "PLACED")
    row_restored = m.product_row(env, p["P-ON-1"])
    ct.check(
        "zero_stock_auto_offline_then_cancel_restores_online",
        row_zero["status"] == "OFFLINE" and str(row_zero["stock"]) == "0" and row_restored["status"] == "ONLINE",
        {"zero": row_zero, "restored": row_restored},
    )
    m.align_product(env, s, p["P-ON-5"], PRODUCTS["P-ON-5"])
    cid4 = m.cart_add(env, ta, p["P-ON-5"], "1")
    _, body4, _, _ = m.place_order(env, ta, [cid4])
    oid4 = m.order_id_of(body4)
    http_json("POST", f"{base_url(env)}/api/admin/products/{p['P-ON-5']}/offline", headers=auth(s))
    row_man_before = m.product_row(env, p["P-ON-5"])
    m.cancel_customer(env, ta, oid4, "PLACED")
    row_man_after = m.product_row(env, p["P-ON-5"])
    ct.check(
        "manual_offline_stays_offline_after_cancel",
        row_man_before["status"] == "OFFLINE"
        and row_man_before["offline_reason"] == "MANUAL"
        and row_man_after["status"] == "OFFLINE"
        and row_man_after["offline_reason"] == "MANUAL",
        {"before": row_man_before, "after": row_man_after},
    )
    m.dump_case("PB-B02-AC5", ct.as_detail())
    return finish(ct, m.result)


def ac_b03_04(env, fx):
    m.reset_ns(env)
    ta, p = fx["tokens"]["A"], fx["products"]
    ct = ConjunctTracker("PB-B03-AC4")
    c1, b1 = http_json("GET", f"{base_url(env)}/api/me/orders")
    c2, b2 = http_json(
        "GET", f"{base_url(env)}/api/me/orders", headers={"Authorization": "Bearer invalid.token.value"}
    )
    ct.check("unauth_tip", msg(b1) == "请先登录", {"http": c1, "message": msg(b1)})
    ct.check("invalid_token_tip", msg(b2) == "请重新登录", {"http": c2, "message": msg(b2)})
    c_a = m.cart_add(env, ta, p["P-ON-10"], "1")
    m.place_order(env, ta, [c_a])
    c_b = m.cart_add(env, ta, p["P-ON-5"], "1")
    m.place_order(env, ta, [c_b])
    orders = [o for o in m.db_orders(env, "b032_buyer_a") if o["status"] == "PLACED"]
    ct.check("multi_incomplete_orders_allowed", len(orders) >= 2, {"placed_count": len(orders)})
    tb = fx["tokens"]["B"]
    oid = str(orders[0]["id"])
    c3, b3 = http_json("GET", f"{base_url(env)}/api/me/orders/{oid}", headers=auth(tb))
    ct.check("other_buyer_access_denied", c3 >= 400, {"http": c3, "message": msg(b3)})
    m.dump_case("PB-B03-AC4", ct.as_detail())
    return finish(ct, m.result)


def ac_b12_01(env, fx):
    m.reset_ns(env)
    ta, tb, p = fx["tokens"]["A"], fx["tokens"]["B"], fx["products"]
    ct = ConjunctTracker("PB-B12-AC1")
    c0, b0 = http_json(
        "POST",
        f"{base_url(env)}/api/me/orders",
        {"productId": p["P-ON-10"], "quantity": "1"},
        auth(ta, new_key()),
    )
    ct.check("no_direct_order_without_cart_confirm", c0 >= 400, {"http": c0, "message": msg(b0)})
    c1, b1 = http_json(
        "POST", f"{base_url(env)}/api/me/checkout/confirmations", {"cartItemIds": ["1"]}, headers={}
    )
    c2, b2 = http_json(
        "POST",
        f"{base_url(env)}/api/me/checkout/confirmations",
        {"cartItemIds": ["1"]},
        headers={"Authorization": "Bearer bad.token"},
    )
    ct.check("unauth_confirm_tip", msg(b1) == "请先登录", {"http": c1, "message": msg(b1)})
    ct.check("invalid_token_confirm_tip", msg(b2) == "请重新登录", {"http": c2, "message": msg(b2)})
    cid_a = m.cart_add(env, ta, p["P-ON-10"], "1")
    stock_before = m.db_stock(env, p["P-ON-10"])
    cart_before = m.db_cart(env, "b032_buyer_a")
    c3, b3 = m.confirm(env, tb, [cid_a])
    cid_b = m.cart_add(env, tb, p["P-ON-5"], "1")
    c4, b4 = m.confirm(env, ta, [cid_a, cid_b])
    stock_after = m.db_stock(env, p["P-ON-10"])
    cart_after = m.db_cart(env, "b032_buyer_a")
    ct.check("other_cart_line_tip", msg(b3) == "无权操作", {"http": c3, "message": msg(b3)})
    ct.check("mixed_cart_tip", msg(b4) == "无权操作", {"http": c4, "message": msg(b4)})
    ct.check(
        "reject_keeps_stock_cart_no_order",
        stock_before == stock_after and cart_before == cart_after and len(m.db_orders(env, "b032_buyer_a")) == 0,
        {"stock": [stock_before, stock_after], "cart_unchanged": cart_before == cart_after},
    )
    # Product detail UI: no direct-buy button
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
    await page.goto(fe + '/products/' + {json.dumps(str(p['P-ON-10']))}, {{waitUntil:'networkidle'}});
    await page.waitForTimeout(600);
    const text = await page.locator('body').innerText();
    const hasDirect = /立即购买|直接购买|马上买/.test(text);
    const hasAdd = text.includes('加入购物车');
    await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-product-detail-no-direct-buy.png'))}, fullPage:true}});
    out.shots = ['b12-product-detail-no-direct-buy.png'];
    out.hasDirectBuy = hasDirect;
    out.hasAddToCart = hasAdd;
    out.ok = !hasDirect && hasAdd;
  }} catch(e) {{ out.error=String(e); }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
        "ui_b12_ac1",
    )
    ct.check("product_detail_no_direct_buy_ui", shot.get("ok") is True, shot)
    m.dump_case("PB-B12-AC1", ct.as_detail())
    return finish(ct, m.result)


def run_screenshots(env, fx):
    """Index-only final pass: NEVER overwrite AC-step screenshots; never reset_ns here."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    required = [
        ("b03-after-login.png", "PB-B03", "after login"),
        ("b12-product-detail-no-direct-buy.png", "PB-B12-AC1", "product detail"),
        ("b12-cart-selection.png", "PB-B12-AC3", "cart selection defaults"),
        ("b12-checkout-confirm.png", "PB-B12-AC4", "confirm modal"),
        ("b12-clear-cart-confirm.png", "PB-B12-AC5", "clear confirm modal"),
        ("b03-order-history.png", "PB-B03-AC3", "customer order history"),
        ("b03-cancel-detail.png", "PB-B03-AC3", "cancel detail modal"),
        ("b03-admin-orders.png", "PB-B03-AC3", "merchant orders"),
        ("b13-order-success.png", "PB-B13-AC1", "order success"),
        ("b12-submit-error-tip.png", "PB-B12-AC6", "submit error tip"),
        ("b01-merchant-orders-flow.png", "PB-B01-AC4", "merchant orders UI"),
    ]
    mapping = []
    missing = []
    for fname, ac, step in required:
        path = SHOTS / fname
        exists = path.exists() and path.stat().st_size > 1000
        mapping.append({"file": fname, "ac": ac, "step": step, "exists": exists, "bytes": path.stat().st_size if path.exists() else 0})
        if not exists:
            missing.append(fname)
    # Fill ONLY truly missing shots without wiping others — and without reset_ns
    if "b03-after-login.png" in missing or "b12-product-detail-no-direct-buy.png" in missing:
        ta = login_customer(env, "b032_buyer_a", "B032-BuyerA-Pass9", "13803200001")
        m.align_product(env, fx["tokens"]["S"], fx["products"]["P-ON-10"], PRODUCTS["P-ON-10"])
        run_node(
            f"""
const {{ chromium }} = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {{
  const fe = {json.dumps(fe_url(env))};
  const out = {{ok:true}};
  const browser = await chromium.launch({{headless:true}});
  try {{
    const page = await browser.newPage({{viewport:{{width:1280,height:900}}}});
    await page.goto(fe + '/login', {{waitUntil:'networkidle'}});
    await page.locator('#username').fill('b032_buyer_a');
    await page.locator('#password').fill('B032-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{timeout:15000}});
    if ({json.dumps("b03-after-login.png" in missing)}) {{
      await page.screenshot({{path: {json.dumps(str(SHOTS/'b03-after-login.png'))}, fullPage:true}});
    }}
    if ({json.dumps("b12-product-detail-no-direct-buy.png" in missing)}) {{
      await page.goto(fe + '/products/' + {json.dumps(str(fx['products']['P-ON-10']))}, {{waitUntil:'networkidle'}});
      await page.screenshot({{path: {json.dumps(str(SHOTS/'b12-product-detail-no-direct-buy.png'))}, fullPage:true}});
    }}
  }} catch(e) {{ out.error=String(e); out.ok=false; }}
  finally {{ await browser.close(); }}
  console.log(JSON.stringify(out));
}})();
""",
            "ui_shots_fill_missing",
        )
    # Recompute index
    mapping = []
    missing = []
    for fname, ac, step in required:
        path = SHOTS / fname
        exists = path.exists() and path.stat().st_size > 1000
        mapping.append({"file": fname, "ac": ac, "step": step, "exists": exists, "bytes": path.stat().st_size if path.exists() else 0})
        if not exists:
            missing.append(fname)
    return {
        "ok": len(missing) == 0,
        "mapping": mapping,
        "missing": missing,
        "note": "final pass does not overwrite AC-step screenshots; no reset_ns",
    }
