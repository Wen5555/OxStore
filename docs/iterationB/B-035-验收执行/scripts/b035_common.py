#!/usr/bin/env python3
"""Shared helpers for B-035 (legacy fixed-price archive + auction regression).

Reuses the B-030/B-033 contract helpers, adds:
- legacy purchase_intent seed / cleanup and the real V8 migration runner;
- auction publish/bid/snapshot/notification/SSE probes against the live SUT.
"""
from __future__ import annotations

import http.client
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

B035_ROOT = Path(__file__).resolve().parents[1]
ITERB = B035_ROOT.parent
B030_ROOT = next(p for p in ITERB.iterdir() if p.name.startswith("B-030-"))
B033_ROOT = next(p for p in ITERB.iterdir() if p.name.startswith("B-033-"))

sys.path.insert(0, str(B033_ROOT / "scripts"))
sys.path.insert(0, str(B030_ROOT / "scripts"))
sys.path.insert(0, str(B035_ROOT / "scripts"))

from b033_common import (  # noqa: E402
    auth_headers,
    base_url,
    connect_mysql,
    conjunct,
    http_json,
    login_customer,
    login_seller,
    now_cst,
    now_utc,
    product_db,
    query,
    race,
    redact,
    write_json,
)
from b030_common import load_env as b030_load_env  # noqa: E402
from prepare_fixtures import multipart_post, SEED_PNG  # noqa: E402

CST = __import__("datetime").timezone(timedelta(hours=8))
MYSQL_EXE = r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe"
V8_SQL = (Path(r"C:\Users\闪电\Desktop\仓库\OxStore-sut") / "backend/src/main/resources/db/migrations"
          / "V8__close_legacy_fixed_price_intents.sql")


def load_b035_env() -> dict[str, str]:
    import os

    local = B035_ROOT / "runs" / ".env.local"
    if local.exists():
        for line in local.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
    return b030_load_env()


def mysql_cli(env: dict, sql: str, database: str | None = None, stdin_file: Path | None = None) -> str:
    user = env.get("B035_ROOT_USER", "root")
    pwd = env.get("B035_ROOT_PASSWORD", "root")
    args = [MYSQL_EXE, "-u", user, f"-p{pwd}", "--default-character-set=utf8mb4", "-N", "-B"]
    if database:
        args.append(database)
    if stdin_file:
        with open(stdin_file, "rb") as fh:
            proc = subprocess.run(args, stdin=fh, capture_output=True)
    else:
        proc = subprocess.run(args, input=sql.encode("utf-8"), capture_output=True)
    out = proc.stdout.decode("utf-8", errors="replace")
    err = proc.stderr.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"mysql failed rc={proc.returncode}: {err.strip()}\nSQL: {sql[:300]}")
    return out


def apply_v8(env: dict, database: str) -> dict:
    out = mysql_cli(env, "", database=database, stdin_file=V8_SQL)
    return {"stdout": out.strip(), "sql_file": str(V8_SQL)}


def cleanup_namespace(env: dict) -> None:
    """Remove B035-* auction products and b030_* legacy rows. Safe to call repeatedly."""
    stmts = [
        "DELETE n FROM auction_notification n JOIN auction_session s ON s.id=n.auction_id "
        "JOIN product p ON p.id=s.product_id WHERE p.name LIKE 'B035-%'",
        "DELETE b FROM auction_bid b JOIN auction_session s ON s.id=b.auction_id "
        "JOIN product p ON p.id=s.product_id WHERE p.name LIKE 'B035-%'",
        "DELETE e FROM product_status_event e JOIN product p ON p.id=e.product_id WHERE p.name LIKE 'B035-%'",
        "DELETE t FROM trade_attempt t JOIN purchase_intent i ON i.id=t.intent_id "
        "JOIN product p ON p.id=i.product_id WHERE p.name LIKE 'B035-%'",
        "DELETE i FROM purchase_intent i JOIN product p ON p.id=i.product_id WHERE p.name LIKE 'B035-%'",
        "DELETE s FROM auction_session s JOIN product p ON p.id=s.product_id WHERE p.name LIKE 'B035-%'",
        "DELETE pi FROM product_image pi JOIN product p ON p.id=pi.product_id WHERE p.name LIKE 'B035-%'",
        "DELETE p FROM product p WHERE p.name LIKE 'B035-%'",
        "DELETE t FROM trade_attempt t JOIN purchase_intent i ON i.id=t.intent_id "
        "JOIN customer c ON c.id=i.customer_id WHERE c.username LIKE 'b030\\_%'",
        "DELETE i FROM purchase_intent i JOIN customer c ON c.id=i.customer_id WHERE c.username LIKE 'b030\\_%'",
        "DELETE t FROM trade_attempt t JOIN purchase_intent i ON i.id=t.intent_id "
        "JOIN product p ON p.id=i.product_id WHERE p.name LIKE 'B030-%'",
        "DELETE i FROM purchase_intent i JOIN product p ON p.id=i.product_id WHERE p.name LIKE 'B030-%'",
    ]
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            for s in stmts:
                try:
                    cur.execute(s)
                except Exception:
                    pass
    finally:
        conn.close()


def ids(env: dict) -> dict:
    rows = query(env, "SELECT name, id, stock, status, offline_reason, selling_mode FROM product "
                      "WHERE name LIKE 'B030-%'")
    by_name = {r["name"]: r for r in rows}
    cust = query(env, "SELECT username, id FROM customer WHERE username LIKE 'b030\\_%'")
    return {"products": by_name, "customers": {c["username"]: c["id"] for c in cust}}


LEGACY = {
    "trade": {"product": "B030-在售足库存-10", "stock": "10", "snapshot": "B030-在售足库存-10"},
    "intrans": {"product": "B030-在售足库存-5", "stock": "5", "snapshot": "B030-在售足库存-5"},
    "manual": {"product": "B030-低库存-1", "stock": "1", "snapshot": "B030-低库存-1"},
    "history": {"product": "B030-大整数库存", "stock": "9007199254740993", "snapshot": "B030-大整数库存"},
}


def seed_legacy(env: dict) -> dict:
    """Freeze products and insert QUEUING / IN_TRANSACTION / SUCCESS legacy intents."""
    ref = ids(env)
    a = ref["customers"]["b030_buyer_a"]
    b = ref["customers"]["b030_buyer_b"]
    sql = f"""
UPDATE product SET status='FROZEN', freeze_source='TRADE', offline_reason=NULL
 WHERE name='{LEGACY["trade"]["product"]}';
UPDATE product SET status='FROZEN', freeze_source='TRADE', offline_reason=NULL
 WHERE name='{LEGACY["intrans"]["product"]}';
UPDATE product SET status='FROZEN', freeze_source='MANUAL', offline_reason=NULL
 WHERE name='{LEGACY["manual"]["product"]}';

INSERT INTO purchase_intent
 (product_id, customer_id, product_name_snapshot, buyer_name, buyer_phone, status, submitted_at, queue_seq)
SELECT p.id, {a}, '{LEGACY["trade"]["snapshot"]}', 'b030_buyer_a', '13803000001',
       'QUEUING', NOW(6) - INTERVAL 3 MINUTE, 1
FROM product p WHERE p.name='{LEGACY["trade"]["product"]}';

INSERT INTO purchase_intent
 (product_id, customer_id, product_name_snapshot, buyer_name, buyer_phone, status, submitted_at, queue_seq)
SELECT p.id, {b}, '{LEGACY["intrans"]["snapshot"]}', 'b030_buyer_b', '13803000002',
       'IN_TRANSACTION', NOW(6) - INTERVAL 2 MINUTE, 2
FROM product p WHERE p.name='{LEGACY["intrans"]["product"]}';

INSERT INTO purchase_intent
 (product_id, customer_id, product_name_snapshot, buyer_name, buyer_phone, status, submitted_at, queue_seq)
SELECT p.id, {a}, '{LEGACY["history"]["snapshot"]}', 'b030_buyer_a', '13803000001',
       'SUCCESS', NOW(6) - INTERVAL 1 DAY, 3
FROM product p WHERE p.name='{LEGACY["history"]["product"]}';

INSERT INTO trade_attempt (intent_id, started_at)
SELECT i.id, NOW(6) - INTERVAL 2 MINUTE FROM purchase_intent i
 JOIN product p ON p.id=i.product_id
 WHERE p.name='{LEGACY["intrans"]["product"]}' AND i.status='IN_TRANSACTION';
"""
    mysql_cli(env, sql, database=env["B030_DB_NAME"])
    return {"customers": {"a": a, "b": b}, "seeded": LEGACY}


def legacy_state(env: dict) -> dict:
    intents = query(env, """
        SELECT i.id, p.name AS product_name, c.username, i.status AS original_status,
               i.product_name_snapshot, i.legacy_closed_at, i.legacy_close_reason, i.submitted_at
          FROM purchase_intent i
          JOIN product p ON p.id=i.product_id
          JOIN customer c ON c.id=i.customer_id
         WHERE c.username LIKE 'b030\\_%'
         ORDER BY i.submitted_at DESC
    """)
    attempts = query(env, """
        SELECT t.id, i.id AS intent_id, t.finished_at, t.result, t.legacy_closed_at
          FROM trade_attempt t JOIN purchase_intent i ON i.id=t.intent_id
          JOIN customer c ON c.id=i.customer_id
         WHERE c.username LIKE 'b030\\_%'
    """)
    def norm(row, extras):
        out = {}
        for k, v in row.items():
            if k == "id" or k in extras:
                out[k] = None if v is None else str(v)
            else:
                out[k] = v
        return out

    return {
        "intents": [norm(r, ("legacy_closed_at", "submitted_at")) for r in intents],
        "attempts": [norm(r, ("intent_id", "finished_at", "legacy_closed_at")) for r in attempts],
    }


def archive(env: dict, token: str, seller: bool = False, params: str = "") -> tuple[int, dict]:
    base = "/api/admin/legacy-intents" if seller else "/api/me/legacy-intents"
    return http_json("GET", f"{base_url(env)}{base}{params}", headers=auth_headers(token))


def create_auction(env: dict, seller: str, name: str, start: str, increment: str,
                   ends_in_seconds: int) -> dict:
    cats = query(env, "SELECT c.id FROM category c JOIN category p ON c.parent_id=p.id "
                      "WHERE p.parent_id IS NULL ORDER BY c.id LIMIT 1")
    ends_at = (datetime.now(CST) + timedelta(seconds=ends_in_seconds)).strftime("%Y-%m-%dT%H:%M:%S")
    fields = {
        "name": name, "price": start, "category2Id": str(cats[0]["id"]),
        "sellingMode": "AUCTION", "startPrice": start, "minIncrement": increment,
        "endsAt": ends_at, "descriptionHtml": f"<p>{name}</p>",
    }
    code, body = multipart_post(f"{base_url(env)}/api/admin/products", fields,
                                [("images", SEED_PNG)], auth_headers(seller))
    return {"http": code, "body": body, "endsAt": ends_at}


def auction_snapshot(env: dict, pid: str, token: str | None = None) -> tuple[int, dict]:
    headers = auth_headers(token) if token else {}
    return http_json("GET", f"{base_url(env)}/api/products/{pid}/auction", headers=headers)


def auction_bid(env: dict, pid: str, token: str, amount: str) -> tuple[int, dict]:
    return http_json("POST", f"{base_url(env)}/api/products/{pid}/auction/bids",
                     {"amount": amount}, auth_headers(token))


def wait_auction_status(env: dict, pid: str, token: str, targets: set[str],
                        timeout: float = 45.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        code, body = auction_snapshot(env, pid, token)
        last = (code, body)
        data = (body or {}).get("data") or {} if isinstance(body, dict) else {}
        st = data.get("auctionStatus") or data.get("status")
        if st in targets:
            return {"http": code, "body": body, "status": st}
        time.sleep(2)
    return {"http": last[0] if last else None, "body": last[1] if last else None, "status": None}


def notifications(env: dict, token: str, seller: bool = False) -> tuple[int, dict]:
    base = "/api/admin/auction-notifications" if seller else "/api/me/auction-notifications"
    return http_json("GET", f"{base_url(env)}{base}?page=1&size=20", headers=auth_headers(token))


def sse_probe(env: dict, pid: str, token: str, timeout: float = 10.0) -> dict:
    """Open the auction SSE stream and read the first event (line-oriented, never blocks for 600 bytes)."""
    host = base_url(env).replace("http://", "").replace("https://", "")
    conn = http.client.HTTPConnection(host, timeout=timeout)
    buf = ""
    status = None
    try:
        conn.request("GET", f"/api/products/{pid}/auction/stream",
                     headers={"Authorization": f"Bearer {token}", "Accept": "text/event-stream"})
        resp = conn.getresponse()
        status = resp.status
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = resp.readline()
            if not line:
                break
            buf += line.decode("utf-8", errors="replace")
            if buf.endswith("\n\n"):
                break
        return {"status": status, "chunk": redact(buf[:800])}
    except Exception as e:  # noqa: BLE001 - timeout still carries the received prefix
        return {"status": status, "chunk": redact(buf[:800]), "error": type(e).__name__}
    finally:
        conn.close()
