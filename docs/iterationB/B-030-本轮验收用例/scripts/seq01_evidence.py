#!/usr/bin/env python3
"""SEQ-01 evidence for a_first / b_first / simultaneous.

For each mode:
- reset namespace + restore P-ON-1 stock=1 ONLINE
- dual_confirm A/B
- barrier submit both orders
- record both HTTP bodies (redacted)
- assert: exactly one PLACED success; product stock==0; loser has no new order;
  loser's cart line still present (not mis-cleared) OR clearly rejected without half-order
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b030_common import (  # noqa: E402
    ROOT,
    auth_headers,
    base_url,
    connect_mysql,
    http_json,
    load_env,
    login_customer,
)
from helpers_lib import dual_confirm, load_fixtures, product_id  # noqa: E402
from redact import dumps_redacted, redact_obj  # noqa: E402

MODES = ("a_first", "b_first", "simultaneous")
OUT_DIR = ROOT / "review" / "seq01"


def reset(case: str) -> None:
    subprocess.check_call(
        [sys.executable, str(ROOT / "scripts" / "reset_namespace.py"), "--case-id", case],
        cwd=str(ROOT),
    )
    # ensure P-ON-1 is ONLINE stock 1 (reset updates by name; align via seller if needed)
    env = load_env()
    from b030_common import auth_headers as ah, login_seller

    ts = login_seller(env)
    pid = product_id("P-ON-1")
    http_json(
        "PATCH",
        f"{base_url(env)}/api/admin/products/{pid}",
        {"stock": "1"},
        ah(ts),
    )
    # online if needed
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status, stock FROM product WHERE id=%s", (pid,))
            row = cur.fetchone()
    finally:
        conn.close()
    if row["status"] != "ONLINE":
        http_json(
            "POST",
            f"{base_url(env)}/api/admin/products/{pid}/online",
            headers=ah(ts),
        )


def db_snapshot(env: dict, pid: str) -> dict:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, stock, status, offline_reason FROM product WHERE id=%s",
                (pid,),
            )
            product = cur.fetchone()
            cur.execute(
                "SELECT so.id, so.order_no, so.status, so.total_amount, c.username "
                "FROM shop_order so JOIN customer c ON c.id=so.customer_id "
                "WHERE c.username IN ('b030_buyer_a','b030_buyer_b') ORDER BY so.id"
            )
            orders = cur.fetchall()
            cur.execute(
                "SELECT ci.id, c.username, ci.product_id, ci.quantity "
                "FROM cart_item ci JOIN customer c ON c.id=ci.customer_id "
                "WHERE c.username IN ('b030_buyer_a','b030_buyer_b') AND ci.product_id=%s "
                "ORDER BY c.username",
                (pid,),
            )
            carts = cur.fetchall()
            cur.execute(
                "SELECT oi.order_id, oi.product_id, oi.quantity_snapshot AS quantity, c.username "
                "FROM order_item oi "
                "JOIN shop_order so ON so.id=oi.order_id "
                "JOIN customer c ON c.id=so.customer_id "
                "WHERE c.username IN ('b030_buyer_a','b030_buyer_b')"
            )
            items = cur.fetchall()
        return {
            "product": product,
            "orders": orders,
            "carts_for_product": carts,
            "order_items": items,
        }
    finally:
        conn.close()


def parse_curl_json(stdout: str) -> dict:
    stdout = (stdout or "").strip()
    try:
        return json.loads(stdout)
    except Exception:
        return {"raw": stdout[:2000]}


def run_mode(mode: str) -> dict:
    env = load_env()
    load_fixtures()
    reset(f"SEQ-01-{mode}")
    pid = product_id("P-ON-1")
    before = db_snapshot(env, pid)
    dual = dual_confirm(env, product="P-ON-1", qty="1")
    base = base_url(env)

    def cmd(side: str) -> str:
        s = dual[side]
        return (
            f"curl -sS -X POST '{base}/api/me/orders' "
            f"-H 'Authorization: Bearer {s['token']}' "
            f"-H 'Idempotency-Key: {s['idem']}' "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"confirmationToken\":\"{s['confirmationToken']}\"}}'"
        )

    delay = "80" if mode != "simultaneous" else "50"
    p = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "barrier_runner.py"),
            "--seq",
            "SEQ-01",
            "--mode",
            mode,
            "--delay-ms",
            delay,
            "--a-cmd",
            cmd("A"),
            "--b-cmd",
            cmd("B"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    barrier_path = ROOT / "runs" / f"SEQ-01-{mode}.json"
    barrier = json.loads(barrier_path.read_text(encoding="utf-8")) if barrier_path.exists() else {}
    a_body = parse_curl_json((barrier.get("results") or {}).get("A", {}).get("stdout", ""))
    b_body = parse_curl_json((barrier.get("results") or {}).get("B", {}).get("stdout", ""))
    after = db_snapshot(env, pid)

    success_orders = [o for o in after["orders"] if o["status"] == "PLACED"]
    # winner by message
    def ok(body: dict) -> bool:
        return isinstance(body, dict) and body.get("message") == "下单成功" and body.get("code") == 0

    a_ok, b_ok = ok(a_body), ok(b_body)
    winner = "A" if a_ok and not b_ok else ("B" if b_ok and not a_ok else ("BOTH" if a_ok and b_ok else "NONE"))

    # loser cart should still exist (confirm consumed? or order path clears only winner)
    # Spec: failure leaves cart unchanged. After success, winner cart line cleared by remainder rules.
    carts = {c["username"]: c for c in after["carts_for_product"]}
    loser_user = None
    if winner == "A":
        loser_user = "b030_buyer_b"
    elif winner == "B":
        loser_user = "b030_buyer_a"

    stock = str(after["product"]["stock"])
    assertions = {
        "exactly_one_success_http": (a_ok ^ b_ok),
        "exactly_one_placed_order": len(success_orders) == 1,
        "stock_is_zero": stock == "0",
        "no_half_orders": len(after["orders"]) == 1 and len(after["order_items"]) == 1,
        "loser_cart_not_miscleared": (
            loser_user is not None and loser_user in carts and str(carts[loser_user]["quantity"]) == "1"
        )
        if loser_user
        else False,
        "winner": winner,
        "stock": stock,
        "order_count": len(after["orders"]),
    }
    assertions["pass"] = all(
        [
            assertions["exactly_one_success_http"],
            assertions["exactly_one_placed_order"],
            assertions["stock_is_zero"],
            assertions["no_half_orders"],
            assertions["loser_cart_not_miscleared"],
        ]
    )

    evidence = {
        "seq": "SEQ-01",
        "mode": mode,
        "sut_sha": env.get("B030_SUT_SHA"),
        "db": env.get("B030_DB_NAME"),
        "productId": pid,
        "barrier_returncode": p.returncode,
        "responses": {"A": a_body, "B": b_body},
        "before": before,
        "after": after,
        "assertions": assertions,
        "note": "tokens redacted; dual_confirm tokens not stored",
    }
    return redact_obj(evidence)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {"modes": {}, "all_pass": True}
    for mode in MODES:
        print("running", mode, flush=True)
        ev = run_mode(mode)
        path = OUT_DIR / f"{mode}.json"
        path.write_text(dumps_redacted(ev, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        summary["modes"][mode] = {
            "pass": ev["assertions"]["pass"],
            "winner": ev["assertions"]["winner"],
            "stock": ev["assertions"]["stock"],
            "assertions": ev["assertions"],
            "file": str(path.relative_to(ROOT)),
        }
        summary["all_pass"] = summary["all_pass"] and bool(ev["assertions"]["pass"])
        print(mode, "pass=", ev["assertions"]["pass"], "winner=", ev["assertions"]["winner"])
        time.sleep(0.2)

    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(
        dumps_redacted(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    # human markdown
    lines = [
        "# SEQ-01 三模式终态证据",
        "",
        f"- SUT：develop / `{load_env().get('B030_SUT_SHA')}`",
        f"- DB：`{load_env().get('B030_DB_NAME')}`",
        f"- all_pass：`{summary['all_pass']}`",
        "",
        "| mode | pass | winner | stock | 一单成功 | 失败方车保留 |",
        "|---|---|---|---|---|---|",
    ]
    for mode, m in summary["modes"].items():
        a = m["assertions"]
        lines.append(
            f"| {mode} | {m['pass']} | {m['winner']} | {m['stock']} | "
            f"{a['exactly_one_placed_order']} | {a['loser_cart_not_miscleared']} |"
        )
    lines += ["", "明细 JSON：`review/seq01/<mode>.json`", ""]
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0 if summary["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
