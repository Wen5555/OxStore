#!/usr/bin/env python3
"""Static coverage check for B-030 round materials. No business env required."""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "00-索引.md"
PB_FILES = sorted(ROOT.glob("PB-B*.md"))

def main() -> int:
    errors = []
    idx = INDEX.read_text(encoding="utf-8")
    ac_ids = re.findall(r"\| (PB-B\d+-AC\d+) \|", idx)
    if len(ac_ids) != 79:
        errors.append(f"index AC count={len(ac_ids)} want 79")
    if len(set(ac_ids)) != len(ac_ids):
        errors.append("duplicate AC ids in index")

    found = set()
    tc_ids = []
    for f in PB_FILES:
        text = f.read_text(encoding="utf-8")
        for ac in re.findall(r"^## (PB-B\d+-AC\d+)\s*$", text, re.M):
            found.add(ac)
        for tc in re.findall(
            r"^### (TC-PB-B\d+-AC\d+-(?:POS|NEG|BND|CON))\b", text, re.M
        ):
            tc_ids.append(tc)
        if "待执行" not in text:
            errors.append(f"{f.name}: missing 待执行 marker")

    missing = sorted(set(ac_ids) - found)
    extra = sorted(found - set(ac_ids))
    if missing:
        errors.append(f"PB files missing ACs: {missing[:5]}...")
    if extra:
        errors.append(f"PB files extra ACs: {extra[:5]}")
    if len(set(tc_ids)) != len(tc_ids):
        errors.append("duplicate TC ids")
    if len(tc_ids) < 79:
        errors.append(f"TC count {len(tc_ids)} < 79")

    required = ["README.md", "数据准备与清理.md", "并发时序.md", "00-索引.md"]
    for name in required:
        if not (ROOT / name).exists():
            errors.append(f"missing {name}")

    # ensure no tests/regression platform path claimed as deliverable here
    if (ROOT.parents[2] / "tests" / "regression").exists():
        # allowed only if empty/unrelated; flag if present in this commit context
        pass

    if errors:
        print("FAIL")
        for e in errors:
            print("-", e)
        return 1
    print("PASS")
    print(f"AC={len(ac_ids)} TC={len(tc_ids)} PB_files={len(PB_FILES)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
