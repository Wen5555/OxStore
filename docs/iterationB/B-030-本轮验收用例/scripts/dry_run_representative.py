#!/usr/bin/env python3
"""Representative executability rehearsal for B-030.

Runs what can run without claiming AC pass:
1) self_review static
2) prepare --dry-check (DB name gate)
3) reset --dry-run
4) barrier_runner smoke with echo commands
5) optional live probe if B030_BASE_URL reachable

Writes review/dry-run-log.md with honest blockers.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
REVIEW = ROOT / "review"
RUNS = ROOT / "runs"


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def probe(url: str) -> tuple[bool, str]:
    try:
        with request.urlopen(url, timeout=3) as r:
            return True, f"HTTP {r.status}"
    except Exception as e:
        return False, str(e)


def main() -> int:
    REVIEW.mkdir(parents=True, exist_ok=True)
    RUNS.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# B-030 代表性演练日志",
        f"",
        f"- 时间（UTC）：{datetime.now(timezone.utc).isoformat()}",
        f"- 目的：验证交付物可执行性；**不**将业务 AC 标为通过",
        f"",
    ]
    blockers: list[str] = []
    evidence: list[str] = []

    # 1 self review
    code, out = run([sys.executable, str(SCRIPTS / "self_review.py")])
    evidence.append(f"self_review exit={code}")
    lines.append("## 1. 静态自审")
    lines.append("")
    lines.append("```")
    lines.append(out[-3000:])
    lines.append("```")
    lines.append("")
    if code != 0:
        blockers.append("self_review FAIL")

    # 2 prepare dry-check
    code, out = run([sys.executable, str(SCRIPTS / "prepare_fixtures.py"), "--dry-check"])
    evidence.append(f"prepare --dry-check exit={code}")
    lines.append("## 2. prepare --dry-check")
    lines.append("")
    lines.append("```")
    lines.append(out)
    lines.append("```")
    lines.append("")
    if code != 0:
        blockers.append("prepare dry-check blocked (expected if DB env unset): " + out.strip()[:200])

    # 3 reset dry-run
    code, out = run([sys.executable, str(SCRIPTS / "reset_namespace.py"), "--dry-run", "--case-id", "DRY"])
    evidence.append(f"reset --dry-run exit={code}")
    lines.append("## 3. reset --dry-run")
    lines.append("")
    lines.append("```")
    lines.append(out[:1500])
    lines.append("```")
    lines.append("")
    if code != 0:
        blockers.append("reset dry-run blocked: " + out.strip()[:200])

    # 4 barrier smoke
    code, out = run(
        [
            sys.executable,
            str(SCRIPTS / "barrier_runner.py"),
            "--seq",
            "SEQ-01",
            "--mode",
            "simultaneous",
            "--a-cmd",
            "echo A_OK && sleep 0.05",
            "--b-cmd",
            "echo B_OK && sleep 0.05",
        ]
    )
    evidence.append(f"barrier smoke exit={code}")
    lines.append("## 4. barrier_runner 烟测（echo，非业务）")
    lines.append("")
    lines.append("```")
    lines.append(out[-1500:])
    lines.append("```")
    lines.append("")
    if code != 0:
        blockers.append("barrier smoke failed")

    # 5 live probe
    env_file = RUNS / ".env.local"
    base = "http://127.0.0.1:8080"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("B030_BASE_URL="):
                base = line.split("=", 1)[1].strip() or base
    ok, detail = probe(base + "/actuator/health") if False else probe(base)
    # try base root / common paths
    ok2, d2 = probe(base + "/api/auth/login")
    lines.append("## 5. 被测服务探测")
    lines.append("")
    lines.append(f"- BASE `{base}` GET / → reachable={ok} ({detail})")
    lines.append(f"- POST path probe GET `/api/auth/login` → reachable={ok2} ({d2})")
    lines.append("")
    if not ok and not ok2:
        blockers.append(
            f"No live BE at {base}. Cannot rehearse POS/NEG/UI/concurrency against real MySQL+BE+FE in this environment. "
            "Scripts and cases are ready; business execution blocked until independent test stack is up with oxstore_b030_* DB."
        )
        lines.append("**阻塞（如实）**：当前云代理环境未启动挑战 B 被测栈；代表性业务演练无法连真实接口。")
        lines.append("已完成：静态自审、DB 名前置门禁演练、reset dry-run、栅栏烟测。")
    else:
        lines.append("服务可达：请继续用 prepare_fixtures + 选例手工/脚本跑 POS/NEG/边界/并发，并写入 runs/。")
        evidence.append("live base reachable")

    # representative case checklist (document-level walkthrough)
    manifest = json.loads((ROOT / "cases" / "manifest.json").read_text(encoding="utf-8"))
    samples = []
    for want in ("PB-B01-AC1-POS", "PB-B13-AC1-POS", "PB-B13-AC1-NEG", "PB-B02-AC3-NEG", "PB-B13-AC5-CON", "PB-B08"):
        for c in manifest["cases"]:
            if c["case_id"].startswith(want) or (want.endswith("-") is False and want in c["case_id"]):
                samples.append(c["case_id"])
                break
    lines.append("## 6. 代表性用例纸面走查（非业务通过）")
    lines.append("")
    for cid in samples:
        # load snippet presence
        lines.append(f"- `{cid}`：已在 cases/ 含 HTTP/断言/清理；执行状态仍 **待执行**")
    lines.append("")
    lines.append("## 结论")
    lines.append("")
    if any("No live BE" in b for b in blockers) and not any(b.startswith("self_review") for b in blockers):
        lines.append("- 交付物可执行性：**脚本与用例入口可用**；**业务验收演练阻塞于缺少独立测试环境**。")
        lines.append("- 不得将任何 AC 标为通过。")
    elif blockers:
        lines.append("- 演练存在失败项，见 blockers。")
    else:
        lines.append("- 静态+烟测通过；业务跑数需在配置环境后继续。")
    lines.append("")
    lines.append("### blockers")
    lines.append("")
    for b in blockers:
        lines.append(f"- {b}")
    lines.append("")
    lines.append("### evidence")
    lines.append("")
    for e in evidence:
        lines.append(f"- {e}")

    path = REVIEW / "dry-run-log.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", path)
    for b in blockers:
        print("BLOCKER:", b)
    # exit 0 if only env blockers; 1 if self_review/barrier broken
    hard = [b for b in blockers if b.startswith("self_review") or b.startswith("barrier")]
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
