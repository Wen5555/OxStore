#!/usr/bin/env python3
"""Redact JWTs and Authorization bearer tokens from evidence payloads."""
from __future__ import annotations
import json
import re
from typing import Any

JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
BEARER_RE = re.compile(r"(Bearer\s+)eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", re.I)


def redact_text(s: str) -> str:
    s = BEARER_RE.sub(r"\1<jwt-redacted>", s)
    return JWT_RE.sub("<jwt-redacted>", s)


def redact_obj(o: Any) -> Any:
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if isinstance(k, str) and ("token" in k.lower() or k.lower() in {"authorization", "authorization_header"}):
                out[k] = "<jwt-redacted>" if v else v
            else:
                out[k] = redact_obj(v)
        return out
    if isinstance(o, list):
        return [redact_obj(x) for x in o]
    if isinstance(o, str):
        return redact_text(o)
    return o


def dumps_redacted(obj: Any, **kwargs) -> str:
    return json.dumps(redact_obj(obj), **kwargs)
