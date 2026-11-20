#!/usr/bin/env python3
"""Executability self-review for B-030 rewritten materials.

Fails on placeholder wording, mechanical forbidden-tip misuse, missing fixtures/scripts.
Does NOT claim business AC pass.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "cases" / "manifest.json").read_text(encoding="utf-8"))
ACS = json.loads((ROOT / "acs-79.json").read_text(encoding="utf-8"))

PLACEHOLDERS = [
    "按 AC 描述的合法路径",
    "查询 DB 验证不变量",
    "准备满足本 AC 的在售",
    "行为符合上方「验收标准原文」",
    "可选自动化映射见文末",
]

# If these appear as required_messages for an AC that prohibits them — fail
ALWAYS_FORBIDDEN_TIPS = {
    "失败",
    "每笔数量固定为 1",
    "订单已生成但购物车未清理",
    "库存已扣但清车未完成",
    "订单成功、清车未完成、客户重试时只清车",
}


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    ac_ids = {a["ac_id"] for a in ACS}
    covered = {c["ac_id"] for c in MANIFEST["cases"]}
    if covered != ac_ids:
        errors.append(f"AC coverage mismatch missing={sorted(ac_ids-covered)[:10]} extra={sorted(covered-ac_ids)[:10]}")

    # every AC has >=1 case
    from collections import Counter
    cnt = Counter(c["ac_id"] for c in MANIFEST["cases"])
    for a in ac_ids:
        if cnt[a] < 1:
            errors.append(f"{a}: no cases")

    for c in MANIFEST["cases"]:
        for tip in c.get("required_messages") or []:
            if tip in ALWAYS_FORBIDDEN_TIPS:
                errors.append(f"{c['case_id']}: forbidden tip listed as required: {tip}")
        for tip in c.get("forbidden") or []:
            if tip in (c.get("required_messages") or []):
                errors.append(f"{c['case_id']}: tip both required and forbidden: {tip}")

    # scan markdown for placeholders
    for md in (ROOT / "cases").glob("PB-B*.md"):
        text = md.read_text(encoding="utf-8")
        for p in PLACEHOLDERS:
            if p in text:
                errors.append(f"{md.name}: placeholder still present: {p}")
        # old mechanical pattern: 提示文案必须为原文之一：「失败」
        if re.search(r"提示文案必须为原文之一：.*「失败」", text):
            errors.append(f"{md.name}: mechanical tip requires 「失败」")
        if "待执行" not in text:
            errors.append(f"{md.name}: missing 待执行")
        # must have HTTP or barrier or helper ref
        if "HTTP `" not in text and "barrier" not in text and "helper:" not in text:
            errors.append(f"{md.name}: no executable HTTP/barrier/helper steps found")

    required_files = [
        ROOT / "fixtures" / "catalog.json",
        ROOT / "fixtures" / "env.example",
        ROOT / "scripts" / "prepare_fixtures.py",
        ROOT / "scripts" / "reset_namespace.py",
        ROOT / "scripts" / "barrier_runner.py",
        ROOT / "scripts" / "b030_common.py",
        ROOT / "concurrency" / "SEQ.md",
        ROOT / "execution" / "B031.md",
        ROOT / "execution" / "B037.md",
        ROOT / "README.md",
        ROOT / "00-索引.md",
    ]
    for f in required_files:
        if not f.exists():
            errors.append(f"missing required file: {f.relative_to(ROOT)}")

    # syntax-check scripts
    import py_compile
    for py in (ROOT / "scripts").glob("*.py"):
        try:
            py_compile.compile(str(py), doraise=True)
        except Exception as e:
            errors.append(f"syntax error {py.name}: {e}")

    report = {
        "ac_count": len(ACS),
        "case_count": MANIFEST["case_count"],
        "errors": errors,
        "warnings": warnings,
        "result": "FAIL" if errors else "PASS_STATIC_REVIEW",
        "note": "PASS_STATIC_REVIEW ≠ business acceptance. Unrun cases stay 待执行.",
    }
    out = ROOT / "review" / "self-review.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
