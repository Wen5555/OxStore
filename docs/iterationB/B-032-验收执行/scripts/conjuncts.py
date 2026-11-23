#!/usr/bin/env python3
"""Explicit AC conjunct tracking — every sub-claim recorded; no silent OR/default PASS."""
from __future__ import annotations

from typing import Any


class ConjunctTracker:
    def __init__(self, ac_id: str):
        self.ac_id = ac_id
        self.items: list[dict[str, Any]] = []

    def check(
        self,
        name: str,
        cond: bool,
        evidence: Any = None,
        *,
        on_fail: str = "FAIL",
    ) -> bool:
        """Record one conjunct. on_fail is FAIL | NOT_EXECUTED | BLOCKED when cond is False."""
        ok = bool(cond)
        self.items.append(
            {
                "name": name,
                "pass": ok,
                "on_fail": on_fail,
                "evidence": evidence,
            }
        )
        return ok

    def skip(self, name: str, reason: str, *, disposition: str = "NOT_EXECUTED") -> None:
        self.items.append(
            {
                "name": name,
                "pass": False,
                "on_fail": disposition,
                "evidence": {"reason": reason},
            }
        )

    def all_pass(self) -> bool:
        return all(i["pass"] for i in self.items) and len(self.items) > 0

    def verdict(self) -> str:
        if not self.items:
            return "NOT_EXECUTED"
        if self.all_pass():
            return "PASS"
        # Prefer strongest failure among failed conjuncts
        failed = [i for i in self.items if not i["pass"]]
        ranks = {"FAIL": 3, "BLOCKED": 2, "NOT_EXECUTED": 1}
        worst = max(failed, key=lambda i: ranks.get(i["on_fail"], 0))
        return worst["on_fail"]

    def as_detail(self) -> dict:
        return {
            "conjuncts": [
                {
                    "name": i["name"],
                    "pass": i["pass"],
                    "disposition_if_fail": i["on_fail"],
                    "evidence": i["evidence"],
                }
                for i in self.items
            ],
            "conjunct_pass": sum(1 for i in self.items if i["pass"]),
            "conjunct_total": len(self.items),
            "conjunct_fail_names": [i["name"] for i in self.items if not i["pass"]],
        }


def finish(tracker: ConjunctTracker, result_fn, extra: dict | None = None):
    detail = {**(extra or {}), **tracker.as_detail()}
    v = tracker.verdict()
    if v != "PASS":
        detail["fail_reason"] = (
            "conjuncts failed: " + ", ".join(detail["conjunct_fail_names"])
            if detail["conjunct_fail_names"]
            else "no conjuncts executed"
        )
    return result_fn(tracker.ac_id, v, detail)
