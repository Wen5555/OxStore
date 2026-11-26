#!/usr/bin/env python3
"""Shared helpers for B-030 prepare / reset / barrier / dry-run scripts.

Safety: refuses DB names that do not match the allowed test prefixes.
Does not DROP DATABASE. Namespace cleanup is limited to B030-prefixed rows.
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "fixtures" / "catalog.json").read_text(encoding="utf-8"))
ALLOWED_DB = tuple(CATALOG["safety"]["require_db_name_prefix"])


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    local = ROOT / "runs" / ".env.local"
    if local.exists():
        for line in local.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip())
    return env


def require_test_db(name: str) -> str:
    if not name or not any(name.startswith(p) for p in ALLOWED_DB):
        raise SystemExit(
            f"Refusing DB '{name}'. Must start with one of {ALLOWED_DB}. "
            "Never point these scripts at production."
        )
    return name


def base_url(env: dict[str, str]) -> str:
    return env.get("B030_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def http_json(
    method: str,
    url: str,
    body: dict | list | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, Any]:
    data = None
    hdrs = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=hdrs, method=method.upper())
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return e.code, parsed
    except error.URLError as e:
        return 0, {"error": str(e.reason)}


def new_idem_key() -> str:
    return str(uuid.uuid4())


def connect_mysql(env: dict[str, str]):
    try:
        import pymysql  # type: ignore
    except ImportError as e:
        raise SystemExit(
            "pymysql required for DB scripts: pip install pymysql"
        ) from e
    db = require_test_db(env.get("B030_DB_NAME", ""))
    return pymysql.connect(
        host=env.get("B030_DB_HOST", "127.0.0.1"),
        port=int(env.get("B030_DB_PORT", "3306")),
        user=env.get("B030_DB_USER", "oxstore_test"),
        password=env.get("B030_DB_PASSWORD", ""),
        database=db,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def login_customer(env: dict[str, str], account_key: str) -> str:
    acc = CATALOG["accounts"][account_key]
    code, body = http_json(
        "POST",
        f"{base_url(env)}/api/auth/login",
        {"username": acc["username"], "password": acc["password"]},
    )
    if code != 200:
        # try register once
        http_json("POST", f"{base_url(env)}/api/auth/register", acc["register"]["body"])
        code, body = http_json(
            "POST",
            f"{base_url(env)}/api/auth/login",
            {"username": acc["username"], "password": acc["password"]},
        )
    if code != 200 or not isinstance(body, dict):
        raise RuntimeError(f"customer login failed {account_key}: {code} {body}")
    token = body.get("data", {}).get("token") or body.get("data", {}).get("accessToken")
    if not token:
        raise RuntimeError(f"no token in login response: {body}")
    return token


def login_seller(env: dict[str, str]) -> str:
    pwd = env.get("B030_SELLER_PASSWORD")
    if not pwd:
        raise RuntimeError("B030_SELLER_PASSWORD not set")
    code, body = http_json(
        "POST",
        f"{base_url(env)}/api/admin/auth/login",
        {"username": "admin", "password": pwd},
    )
    if code != 200 or not isinstance(body, dict):
        raise RuntimeError(f"seller login failed: {code} {body}")
    token = body.get("data", {}).get("token") or body.get("data", {}).get("accessToken")
    if not token:
        raise RuntimeError(f"no seller token: {body}")
    return token


def auth_headers(token: str, idem: str | None = None) -> dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if idem:
        h["Idempotency-Key"] = idem
    return h


PRODUCT_NAME_RE = re.compile(r"^B030-")


def assert_namespace_product_name(name: str) -> None:
    if not PRODUCT_NAME_RE.match(name):
        raise SystemExit(f"Refusing non-namespace product name: {name}")
