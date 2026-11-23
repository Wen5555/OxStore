#!/usr/bin/env python3
"""Shared helpers for B-032 acceptance (checkout atomicity / confirm / concurrency)."""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ("oxstore_b032_", "oxstore_test_")
JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


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


def require_db(name: str) -> str:
    if not name or not any(name.startswith(p) for p in ALLOWED):
        raise SystemExit(f"Refusing DB '{name}'. Must start with {ALLOWED}")
    return name


def base_url(env: dict) -> str:
    return env.get("B032_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def fe_url(env: dict) -> str:
    return env.get("B032_FE_URL", "http://127.0.0.1:5173").rstrip("/")


def http_json(method: str, url: str, body=None, headers=None, timeout=60.0):
    data = None
    hdrs = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        hdrs["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=hdrs, method=method.upper())
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
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


def connect_mysql(env: dict):
    import pymysql

    db = require_db(env.get("B032_DB_NAME", ""))
    return pymysql.connect(
        host=env.get("B032_DB_HOST", "127.0.0.1"),
        port=int(env.get("B032_DB_PORT", "3306")),
        user=env.get("B032_DB_USER", "oxstore_test"),
        password=env.get("B032_DB_PASSWORD", ""),
        database=db,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def auth(token: str, idem: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {token}"}
    if idem:
        h["Idempotency-Key"] = idem
    return h


def new_key() -> str:
    return str(uuid.uuid4())


def login_customer(env: dict, username: str, password: str, phone: str) -> str:
    code, body = http_json(
        "POST", f"{base_url(env)}/api/auth/login", {"username": username, "password": password}
    )
    if code != 200:
        http_json(
            "POST",
            f"{base_url(env)}/api/auth/register",
            {
                "username": username,
                "password": password,
                "phone": phone,
                "location": "B032",
            },
        )
        code, body = http_json(
            "POST", f"{base_url(env)}/api/auth/login", {"username": username, "password": password}
        )
    if code != 200:
        raise RuntimeError(f"login {username}: {code} {body}")
    return body["data"]["token"]


def login_seller(env: dict) -> str:
    pwd = env.get("B032_SELLER_PASSWORD")
    code, body = http_json(
        "POST", f"{base_url(env)}/api/admin/auth/login", {"username": "admin", "password": pwd}
    )
    if code != 200:
        raise RuntimeError(f"seller login: {code} {body}")
    return body["data"]["token"]


def redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            kl = k.lower()
            if kl in ("token", "accesstoken", "refreshtoken", "authorization", "jwt") or kl.endswith(
                "_token"
            ):
                out[k] = "<jwt-redacted>"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, str):
        return JWT_RE.sub("<jwt-redacted>", obj)
    return obj


def msg(body) -> str:
    return (body or {}).get("message") if isinstance(body, dict) else ""


def code_of(body) -> int | None:
    return (body or {}).get("code") if isinstance(body, dict) else None
