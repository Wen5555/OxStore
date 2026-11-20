#!/usr/bin/env python3
"""Real representative rehearsal against live MySQL+BE (not echo).

Runs:
1) verify_api_db
2) reset + place_order POS
3) cart_qty oversell NEG path (checkout may fail)
4) dual_confirm + barrier SEQ-01 simultaneous
5) favorite then cancel
Logs to review/dry-run-log.md and runs/representative-*.json
Does NOT mark AC passed.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b030_common import load_env, base_url  # noqa: E402
from helpers_lib import (  # noqa: E402
    cancel_order,
    dual_confirm,
    load_fixtures,
    place_order,
    cart_add,
    checkout_submit,
    login_customer,
)
from b030_common import login_customer as lc  # noqa

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "review"
RUNS = ROOT / "runs"
SCRIPTS = ROOT / "scripts"


def sh(args: list[str]) -> tuple[int, str]:
    p = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    REVIEW.mkdir(exist_ok=True)
    RUNS.mkdir(exist_ok=True)
    env = load_env()
    lines = [
        "# B-030 代表性真实演练日志",
        "",
        f"- UTC：{datetime.now(timezone.utc).isoformat()}",
        f"- BASE：{base_url(env)}",
        f"- SUT_SHA：{env.get('B030_SUT_SHA')}",
        f"- DB：{env.get('B030_DB_NAME')}",
        "- 声明：本日志证明脚本/接口可跑；**不**将业务 AC 标为通过",
        "",
    ]
    results = {}

    # 0 self review for helper refs
    code, out = sh([sys.executable, str(SCRIPTS / "self_review.py")])
    results["self_review"] = {"code": code, "tail": out[-1500:]}
    lines += ["## 0. self_review", "```", out[-2000:], "```", ""]

    # 1 verify api db
    code, out = sh([sys.executable, str(SCRIPTS / "verify_api_db.py")])
    results["verify_api_db"] = {"code": code, "out": out[-2000:]}
    lines += ["## 1. verify_api_db", "```", out[-2000:], "```", ""]
    if code != 0:
        lines.append("**阻塞**：API↔DB 绑定失败，停止业务演练。")
        (REVIEW / "dry-run-log.md").write_text("\n".join(lines), encoding="utf-8")
        return 2

    fx = load_fixtures()
    if not fx.get("ready"):
        lines.append("**阻塞**：fixtures not ready")
        (REVIEW / "dry-run-log.md").write_text("\n".join(lines), encoding="utf-8")
        return 3

    # 2 reset + place_order
    sh([sys.executable, str(SCRIPTS / "reset_namespace.py"), "--case-id", "REP-POS"])
    try:
        placed = place_order(env, product="P-ON-10", qty="2")
        results["place_order"] = {"ok": True, "orderId": placed.get("orderId"), "message": placed.get("message"), "http": placed.get("http")}
        lines += ["## 2. place_order POS", f"- http={placed.get('http')} message={placed.get('message')} orderId={placed.get('orderId')}", ""]
    except Exception as e:
        results["place_order"] = {"ok": False, "error": str(e)}
        lines += ["## 2. place_order POS", f"- FAIL {e}", ""]

    # 3 NEG oversell — expect reject at confirm or submit (库存不足)
    sh([sys.executable, str(SCRIPTS / "reset_namespace.py"), "--case-id", "REP-NEG"])
    try:
        from b030_common import http_json, auth_headers, new_idem_key

        token = lc(env, "CUSTOMER_A")
        cart = cart_add(env, token, "P-ON-1", "5")
        code, body = http_json(
            "POST",
            f"{base_url(env)}/api/me/checkout/confirmations",
            {"cartItemIds": [cart["cartItemId"]]},
            auth_headers(token),
        )
        msg = (body or {}).get("message") if isinstance(body, dict) else None
        expected = code >= 400 or (isinstance(body, dict) and body.get("code") not in (0, None))
        results["oversell"] = {
            "http": code,
            "message": msg,
            "expected_reject": expected,
            "body": body,
        }
        lines += [
            "## 3. oversell NEG (qty5 vs stock1)",
            f"- http={code} message={msg} expected_reject={expected}",
            "",
        ]
        if not expected:
            lines.append("- WARN: oversell did not reject")
    except Exception as e:
        results["oversell"] = {"ok": False, "error": str(e)}
        lines += ["## 3. oversell NEG", f"- FAIL {e}", ""]

    # 4 SEQ-01 dual confirm + simultaneous submit via barrier
    sh([sys.executable, str(SCRIPTS / "reset_namespace.py"), "--case-id", "REP-SEQ01"])
    try:
        dual = dual_confirm(env, product="P-ON-1", qty="1")
        (RUNS / "seq01-dual.json").write_text(json.dumps(dual, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        base = base_url(env)
        cmd_a = (
            f"curl -sS -X POST '{base}/api/me/orders' "
            f"-H 'Authorization: Bearer {dual['A']['token']}' "
            f"-H 'Idempotency-Key: {dual['A']['idem']}' "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"confirmationToken\":\"{dual['A']['confirmationToken']}\"}}'"
        )
        cmd_b = (
            f"curl -sS -X POST '{base}/api/me/orders' "
            f"-H 'Authorization: Bearer {dual['B']['token']}' "
            f"-H 'Idempotency-Key: {dual['B']['idem']}' "
            f"-H 'Content-Type: application/json' "
            f"-d '{{\"confirmationToken\":\"{dual['B']['confirmationToken']}\"}}'"
        )
        code, out = sh(
            [
                sys.executable,
                str(SCRIPTS / "barrier_runner.py"),
                "--seq",
                "SEQ-01",
                "--mode",
                "simultaneous",
                "--a-cmd",
                cmd_a,
                "--b-cmd",
                cmd_b,
            ]
        )
        results["seq01"] = {"barrier_code": code, "out": out[-2500:]}
        lines += ["## 4. SEQ-01 simultaneous real curl", "```", out[-2500:], "```", ""]
    except Exception as e:
        results["seq01"] = {"ok": False, "error": str(e)}
        lines += ["## 4. SEQ-01", f"- FAIL {e}", ""]

    # 5 favorite
    sh([sys.executable, str(SCRIPTS / "reset_namespace.py"), "--case-id", "REP-FAV"])
    code, out = sh([sys.executable, str(SCRIPTS / "run_helper.py"), "favorite_then_offline", "--product", "P-ON-10"])
    results["favorite"] = {"code": code, "out": out[-1500:]}
    lines += ["## 5. favorite_then_offline", "```", out[-1500:], "```", ""]

    lines += [
        "## 结论",
        "",
        "- 已对 develop 候选做真实 API+DB 演练（见上）。",
        "- **未**将任何 AC 标记为通过；用例状态仍为待执行。",
        "- 若单项 FAIL，见 results JSON。",
        "",
    ]
    (RUNS / "representative-results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (REVIEW / "dry-run-log.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote", REVIEW / "dry-run-log.md")
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != 'out'}) for k, v in results.items()}, ensure_ascii=False, indent=2))
    # soft success if verify+place_order ok
    if results.get("verify_api_db", {}).get("code") == 0 and results.get("place_order", {}).get("ok"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
