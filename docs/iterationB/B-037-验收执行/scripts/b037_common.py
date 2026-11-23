#!/usr/bin/env python3
"""Shared helpers for B-037 (fixed prompts / persistence / security negatives)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

B037_ROOT = Path(__file__).resolve().parents[1]
ITERB = B037_ROOT.parent
B030_ROOT = next(p for p in ITERB.iterdir() if p.name.startswith("B-030-"))
B033_ROOT = next(p for p in ITERB.iterdir() if p.name.startswith("B-033-"))

sys.path.insert(0, str(B033_ROOT / "scripts"))
sys.path.insert(0, str(B030_ROOT / "scripts"))
sys.path.insert(0, str(B037_ROOT / "scripts"))

from b033_common import (  # noqa: E402
    advance, auth_headers, cancel, conjunct, counts, http_json, login_customer,
    login_seller, now_cst, now_utc, place, product_db, query, reset, write_json,
)
from b030_common import base_url, load_env as b030_load_env  # noqa: E402
from helpers_lib import cart_add, checkout_confirm, checkout_submit, product_id  # noqa: E402

RUNS = B037_ROOT / "runs"


def load_b037_env() -> dict[str, str]:
    local = RUNS / ".env.local"
    if local.exists():
        for line in local.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    return b030_load_env()


def call(env: dict, method: str, path: str, token: str | None = None,
         body: dict | None = None, idem: str | None = None,
         headers: dict | None = None) -> tuple[int, dict]:
    h = dict(headers or {})
    if token:
        h.update(auth_headers(token, idem))
    return http_json(method, f"{base_url(env)}{path}", body, h)


def msg(resp: tuple) -> str:
    return (resp[1] or {}).get("message", "") if isinstance(resp, tuple) else ""


def expect(checks: list, label: str, resp, http: int | tuple[int, ...],
           contains: str | None = None) -> None:
    codes = http if isinstance(http, tuple) else (http,)
    if isinstance(resp, dict):
        got, m = resp.get("http"), resp.get("message", "")
    else:
        got, m = resp[0], msg(resp)
    ok = got in codes and (contains is None or contains in m)
    checks.append(conjunct(label, ok, f"{codes} / {contains or 'any'}", [got, m]))


def all_text(messages: list[str]) -> str:
    return " ".join(messages)
