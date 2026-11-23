#!/usr/bin/env python3
"""B-031: prepare fixtures + execute PB-B08/09/10/11 (21 ACs) in ONE unified run."""
from __future__ import annotations

import json
import mimetypes
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b031_common import (  # noqa: E402
    ROOT,
    auth,
    base_url,
    code_of,
    connect_mysql,
    fe_url,
    http_json,
    load_env,
    login_customer,
    login_seller,
    msg,
    new_key,
    redact,
    require_db,
)

SEED = ROOT / "fixtures" / "seed.png"
SEED2 = ROOT / "fixtures" / "seed2.png"
EVID = ROOT / "evidence"
SHOTS = EVID / "screenshots"
PW_DIR = "/tmp/oxstore-develop/frontend"
BE_DIR = "/tmp/oxstore-develop/backend"
RESTART_PROOF_PATH = EVID / "restart-proof.json"


def multipart_post(url: str, fields: dict, files: list, headers: dict):
    from urllib import error, request

    boundary = f"----B031{uuid.uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())
    for field, path in files:
        data = path.read_bytes()
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{field}"; filename="{path.name}"\r\n'.encode()
        )
        body.extend(f"Content-Type: {ctype}\r\n\r\n".encode())
        body.extend(data)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    req = request.Request(
        url,
        data=bytes(body),
        headers={**headers, "Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None
    except error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return e.code, {"raw": raw}


PRODUCTS = {
    "P-ON-10": {"name": "B031-在售-10", "price": "12.50", "stock": "10", "status": "ONLINE"},
    "P-ON-5": {"name": "B031-在售-5", "price": "8.00", "stock": "5", "status": "ONLINE"},
    "P-OFF-M": {
        "name": "B031-人工下架-5",
        "price": "15.00",
        "stock": "5",
        "status": "OFFLINE",
        "offline_reason": "MANUAL",
    },
    "P-ZERO": {
        "name": "B031-零库存下架",
        "price": "9.90",
        "stock": "0",
        "status": "OFFLINE",
        "offline_reason": "AUTO_ZERO",
    },
}


def _product_row(env: dict, pid: str) -> dict:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, offline_reason, stock, name, price FROM product WHERE id=%s",
                (pid,),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"product {pid} missing")
            return row
    finally:
        conn.close()


def align_product(env: dict, seller: str, pid: str, spec: dict) -> None:
    target = spec["stock"]
    patch = "1" if target == "0" else target
    code, body = http_json(
        "PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": patch}, auth(seller)
    )
    if code != 200:
        raise RuntimeError(f"PATCH stock {spec['name']}: {code} {body}")
    row = _product_row(env, pid)
    if spec["status"] == "ONLINE":
        if row["status"] != "ONLINE":
            code, body = http_json(
                "POST", f"{base_url(env)}/api/admin/products/{pid}/online", headers=auth(seller)
            )
            if code != 200:
                raise RuntimeError(f"online {spec['name']}: {code} {body}")
        return
    if spec.get("offline_reason") == "MANUAL":
        if str(row["stock"]) == "0":
            http_json(
                "PATCH",
                f"{base_url(env)}/api/admin/products/{pid}",
                {"stock": "5"},
                auth(seller),
            )
        row = _product_row(env, pid)
        if row["status"] != "OFFLINE" or row["offline_reason"] != "MANUAL":
            code, body = http_json(
                "POST",
                f"{base_url(env)}/api/admin/products/{pid}/offline",
                headers=auth(seller),
            )
            if code != 200:
                raise RuntimeError(f"offline {spec['name']}: {code} {body}")
        code, body = http_json(
            "PATCH",
            f"{base_url(env)}/api/admin/products/{pid}",
            {"stock": target},
            auth(seller),
        )
        if code != 200:
            raise RuntimeError(f"final stock manual {spec['name']}: {code} {body}")
        return
    code, body = http_json(
        "PATCH",
        f"{base_url(env)}/api/admin/products/{pid}",
        {"stock": "0"},
        auth(seller),
    )
    if code != 200:
        raise RuntimeError(f"stock0 {spec['name']}: {code} {body}")


def fav_items(body) -> list:
    data = (body or {}).get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("items") or data.get("content") or []
    return []


def cart_items(body) -> list:
    data = (body or {}).get("data")
    if isinstance(data, dict):
        return data.get("items") or []
    return []


def fav_count(env, username, product_id) -> int:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) c FROM favorite f JOIN customer c ON c.id=f.customer_id "
                "WHERE c.username=%s AND f.product_id=%s",
                (username, product_id),
            )
            return int(cur.fetchone()["c"])
    finally:
        conn.close()


def fav_db_row(env, username, product_id):
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT f.id, f.product_id, f.created_at FROM favorite f "
                "JOIN customer c ON c.id=f.customer_id "
                "WHERE c.username=%s AND f.product_id=%s",
                (username, product_id),
            )
            return cur.fetchone()
    finally:
        conn.close()


def cart_count(env, username, product_id=None) -> int:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            if product_id is None:
                cur.execute(
                    "SELECT COUNT(*) c FROM cart_item ci JOIN customer c ON c.id=ci.customer_id "
                    "WHERE c.username=%s",
                    (username,),
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) c FROM cart_item ci JOIN customer c ON c.id=ci.customer_id "
                    "WHERE c.username=%s AND ci.product_id=%s",
                    (username, product_id),
                )
            return int(cur.fetchone()["c"])
    finally:
        conn.close()


def cart_db_qty(env, username, product_id):
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ci.id, ci.quantity, ci.product_id FROM cart_item ci "
                "JOIN customer c ON c.id=ci.customer_id "
                "WHERE c.username=%s AND ci.product_id=%s",
                (username, product_id),
            )
            return cur.fetchone()
    finally:
        conn.close()


def product_image_path(env, pid: str) -> str | None:
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT image_path FROM product_image WHERE product_id=%s ORDER BY id LIMIT 1",
                (pid,),
            )
            row = cur.fetchone()
            return row["image_path"] if row else None
    finally:
        conn.close()


def db_update_product_live(env, pid: str, name: str, price: str, image_path: str | None = None):
    """Fixture setup only: Admin publish-after PATCH cannot mutate name/price/image."""
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE product SET name=%s, price=%s WHERE id=%s", (name, price, pid))
            if image_path:
                cur.execute(
                    "SELECT id FROM product_image WHERE product_id=%s ORDER BY id LIMIT 1", (pid,)
                )
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "UPDATE product_image SET image_path=%s WHERE id=%s",
                        (image_path, row["id"]),
                    )
    finally:
        conn.close()


def shop_app_pids() -> list[str]:
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "com.team.shop.ShopApplication"], text=True
        ).strip()
        return [p for p in out.split() if p.isdigit()]
    except subprocess.CalledProcessError:
        return []


def listen_pid_8080() -> str | None:
    """Resolve :8080 listener PID via lsof/netstat, else ShopApplication JVM pid."""
    import re

    try:
        out = subprocess.check_output(
            ["lsof", "-iTCP:8080", "-sTCP:LISTEN", "-t"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            return out.splitlines()[0].strip()
    except Exception:
        pass
    for cmd in (["ss", "-tlnp"], ["netstat", "-tlnp"]):
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        except Exception:
            continue
        for line in out.splitlines():
            if ":8080" in line and "LISTEN" in line:
                m = re.search(r"pid=(\d+)", line) or re.search(r",(\d+)/", line)
                if m:
                    return m.group(1)
    pids = shop_app_pids()
    return pids[0] if pids else None


def port_accepts(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def health_login_ok(env) -> bool:
    code, _ = http_json(
        "POST",
        f"{base_url(env)}/api/admin/auth/login",
        {"username": "admin", "password": env.get("B031_SELLER_PASSWORD")},
    )
    return code == 200


def prepare(env: dict) -> dict:
    require_db(env["B031_DB_NAME"])
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE() AS db")
            db = cur.fetchone()["db"]
            cur.execute(
                "SELECT c.id FROM category c JOIN category p ON c.parent_id=p.id "
                "WHERE p.parent_id IS NULL ORDER BY c.id LIMIT 1"
            )
            cat = str(cur.fetchone()["id"])
            cur.execute("SELECT id, name FROM product WHERE name LIKE 'B031-%'")
            existing = {r["name"]: str(r["id"]) for r in cur.fetchall()}
    finally:
        conn.close()
    if db != env["B031_DB_NAME"]:
        raise RuntimeError(f"DB mismatch {db}")

    seller = login_seller(env)
    ta = login_customer(env, "b031_buyer_a", "B031-BuyerA-Pass9")
    tb = login_customer(env, "b031_buyer_b", "B031-BuyerB-Pass9")

    pids = {}
    for code, spec in PRODUCTS.items():
        if spec["name"] in existing:
            pid = existing[spec["name"]]
        else:
            create_stock = "1" if spec["stock"] == "0" else spec["stock"]
            http, body = multipart_post(
                f"{base_url(env)}/api/admin/products",
                {
                    "name": spec["name"],
                    "price": spec["price"],
                    "category2Id": cat,
                    "stock": create_stock,
                    "sellingMode": "FIXED_PRICE",
                    "descriptionHtml": f"<p>{code}</p>",
                },
                [("images", SEED)],
                auth(seller),
            )
            if http not in (200, 201):
                raise RuntimeError(f"create {code}: {http} {body}")
            pid = str(body["data"].get("productId") or body["data"].get("id"))
        align_product(env, seller, pid, spec)
        pids[code] = pid

    pids["P-GONE"] = "999999999"
    out = {
        "ready": True,
        "db": db,
        "sut_sha": env.get("B031_SUT_SHA"),
        "base": base_url(env),
        "fe": fe_url(env),
        "products": pids,
        "category2Id": cat,
        "accounts": {"A": "b031_buyer_a", "B": "b031_buyer_b"},
    }
    (ROOT / "runs" / "fixture-ids.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {**out, "tokens": {"A": ta, "B": tb, "S": seller}, "_restart_proof": None}


def reset_ns(env: dict):
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            for sql in [
                "DELETE oi FROM order_item oi JOIN shop_order so ON so.id=oi.order_id JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b031_%'",
                "DELETE so FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b031_%'",
                "DELETE ci FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username LIKE 'b031_%'",
                "DELETE t FROM cart_item_tombstone t JOIN customer c ON c.id=t.customer_id WHERE c.username LIKE 'b031_%'",
                "DELETE f FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username LIKE 'b031_%'",
                "DELETE fm FROM favorite_mutation fm JOIN customer c ON c.id=fm.customer_id WHERE c.username LIKE 'b031_%'",
                "DELETE cci FROM checkout_confirmation_item cci JOIN checkout_confirmation cc ON cc.id=cci.confirmation_id JOIN customer c ON c.id=cc.customer_id WHERE c.username LIKE 'b031_%'",
                "DELETE cc FROM checkout_confirmation cc JOIN customer c ON c.id=cc.customer_id WHERE c.username LIKE 'b031_%'",
                "DELETE r FROM operation_receipt r JOIN customer c ON c.id=r.customer_id WHERE c.username LIKE 'b031_%'",
            ]:
                try:
                    cur.execute(sql)
                except Exception:
                    pass
            for name, stock, status, reason, price, alts in [
                ("B031-在售-10", "10", "ONLINE", None, "12.50", ["B031-在售-10-LIVE"]),
                ("B031-在售-5", "5", "ONLINE", None, "8.00", ["B031-在售-5-LIVE"]),
                ("B031-人工下架-5", "5", "OFFLINE", "MANUAL", "15.00", []),
                ("B031-零库存下架", "0", "OFFLINE", "AUTO_ZERO", "9.90", []),
            ]:
                names = [name, *alts]
                placeholders = ",".join(["%s"] * len(names))
                if reason is None:
                    cur.execute(
                        f"UPDATE product SET name=%s, price=%s, stock=%s, status=%s, offline_reason=NULL "
                        f"WHERE name IN ({placeholders})",
                        (name, price, stock, status, *names),
                    )
                else:
                    cur.execute(
                        f"UPDATE product SET name=%s, price=%s, stock=%s, status=%s, offline_reason=%s "
                        f"WHERE name IN ({placeholders})",
                        (name, price, stock, status, reason, *names),
                    )
    finally:
        conn.close()


def result(ac_id: str, verdict: str, detail: dict) -> dict:
    return {"ac_id": ac_id, "verdict": verdict, "detail": redact(detail)}


def expect(cond: bool, detail: dict, ac_id: str, fail_reason: str = "") -> dict:
    if cond:
        return result(ac_id, "PASS", detail)
    detail = {**detail, "fail_reason": fail_reason or "assertion failed"}
    return result(ac_id, "FAIL", detail)


def run_node(js: str, name: str) -> dict:
    path = ROOT / "runs" / f"_{name}.js"
    path.write_text(js, encoding="utf-8")
    proc = subprocess.run(
        ["node", str(path)],
        cwd=PW_DIR,
        capture_output=True,
        text=True,
        timeout=180,
    )
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    try:
        return json.loads(lines[-1] if lines else "{}")
    except Exception:
        return {"ok": False, "raw": proc.stdout[-1200:], "err": proc.stderr[-600:]}


def load_be_env() -> dict:
    p = ROOT / "runs" / "be.env"
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def wait_be(env, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if health_login_ok(env):
            return True
        time.sleep(1.5)
    return False


def restart_backend_proven(env: dict, *, favorite_product_id: str, cart_product_id: str) -> dict:
    """One real BE restart with PID/downtime/health/persistence proof for favorites+cart."""
    be = load_be_env()
    pid_before = listen_pid_8080()
    fav_before = fav_db_row(env, "b031_buyer_a", favorite_product_id)
    cart_before = cart_db_qty(env, "b031_buyer_a", cart_product_id)
    health_before = health_login_ok(env)
    kill_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    kill_mono = time.monotonic()
    killed = []
    for pat in ("com.team.shop.ShopApplication", "spring-boot:run"):
        try:
            out = subprocess.check_output(["pgrep", "-f", pat], text=True).strip().split()
        except subprocess.CalledProcessError:
            out = []
        for pid in out:
            try:
                os.kill(int(pid), signal.SIGTERM)
                killed.append(pid)
            except ProcessLookupError:
                pass
    time.sleep(2)
    for pid in list(killed):
        try:
            os.kill(int(pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
    # prove downtime: port closed + health unavailable
    down_deadline = time.time() + 30
    downtime_observed = False
    health_during_down = None
    while time.time() < down_deadline:
        accepting = port_accepts("127.0.0.1", 8080, 0.5)
        if not accepting:
            health_during_down = health_login_ok(env)
            downtime_observed = not health_during_down
            if downtime_observed:
                break
        time.sleep(0.3)
    mid_pid = listen_pid_8080()
    start_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    start_mono = time.monotonic()
    envp = os.environ.copy()
    envp.update(
        {
            "DB_HOST": be.get("DB_HOST", "127.0.0.1"),
            "DB_PORT": be.get("DB_PORT", "3306"),
            "DB_NAME": be.get("DB_NAME", env["B031_DB_NAME"]),
            "DB_USERNAME": be.get("DB_USERNAME", env.get("B031_DB_USER", "oxstore_test")),
            "DB_PASSWORD": be.get("DB_PASSWORD", env.get("B031_DB_PASSWORD", "")),
            "JWT_SECRET": be.get("JWT_SECRET", "b031-test-jwt-secret-please-change-32b"),
            "ADMIN_INITIAL_PASSWORD": be.get(
                "ADMIN_INITIAL_PASSWORD", env.get("B031_SELLER_PASSWORD", "")
            ),
        }
    )
    log_path = "/tmp/b031-backend-restart.log"
    log = open(log_path, "a", encoding="utf-8")
    log.write(f"\n==== restart start {start_at} kill_at={kill_at} pid_before={pid_before} ====\n")
    log.flush()
    proc = subprocess.Popen(
        ["./mvnw", "-q", "-DskipTests", "spring-boot:run"],
        cwd=BE_DIR,
        env=envp,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    started = wait_be(env, timeout=120)
    ready_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ready_mono = time.monotonic()
    pid_after = listen_pid_8080()
    # verify old JVM gone: pid_after != pid_before (when both known)
    old_gone = True
    if pid_before:
        try:
            os.kill(int(pid_before), 0)
            # still alive?
            old_gone = pid_after is not None and pid_after != pid_before
        except ProcessLookupError:
            old_gone = True
        except PermissionError:
            old_gone = pid_after != pid_before
    fav_after = fav_db_row(env, "b031_buyer_a", favorite_product_id) if started else None
    cart_after = cart_db_qty(env, "b031_buyer_a", cart_product_id) if started else None
    health_after = health_login_ok(env) if started else False
    shop_pids_after = shop_app_pids()
    # Prefer explicit listener PID; fall back to ShopApplication JVM identity.
    if not pid_before and killed:
        pid_before = killed[0]
    if not pid_after:
        pid_after = listen_pid_8080() or (shop_pids_after[0] if shop_pids_after else None)
    pid_changed = bool(pid_before and pid_after and str(pid_before) != str(pid_after))
    proof = {
        "feasible": bool(
            started
            and downtime_observed
            and old_gone
            and health_after
            and (pid_changed or (killed and shop_pids_after and str(killed[0]) not in shop_pids_after))
        ),
        "pid_before": pid_before,
        "pid_mid_downtime": mid_pid,
        "pid_after": pid_after,
        "shop_app_pids_after": shop_pids_after,
        "pid_changed": pid_changed,
        "mvnw_pid": proc.pid,
        "killed_pids": killed,
        "kill_at": kill_at,
        "start_at": start_at,
        "ready_at": ready_at,
        "elapsed_kill_to_ready_sec": round(ready_mono - kill_mono, 3),
        "elapsed_start_to_ready_sec": round(ready_mono - start_mono, 3),
        "downtime_observed": downtime_observed,
        "health_before": health_before,
        "health_during_down": health_during_down,
        "health_after": health_after,
        "old_jvm_gone": old_gone,
        "db": envp["DB_NAME"],
        "log_path": log_path,
        "favorite_before": {
            "id": str(fav_before["id"]) if fav_before else None,
            "product_id": str(fav_before["product_id"]) if fav_before else None,
            "created_at": str(fav_before["created_at"]) if fav_before else None,
        },
        "favorite_after": {
            "id": str(fav_after["id"]) if fav_after else None,
            "product_id": str(fav_after["product_id"]) if fav_after else None,
            "created_at": str(fav_after["created_at"]) if fav_after else None,
        },
        "cart_before": {
            "id": str(cart_before["id"]) if cart_before else None,
            "quantity": str(cart_before["quantity"]) if cart_before else None,
            "product_id": str(cart_before["product_id"]) if cart_before else None,
        },
        "cart_after": {
            "id": str(cart_after["id"]) if cart_after else None,
            "quantity": str(cart_after["quantity"]) if cart_after else None,
            "product_id": str(cart_after["product_id"]) if cart_after else None,
        },
        "favorite_persisted": bool(
            fav_before
            and fav_after
            and str(fav_before["id"]) == str(fav_after["id"])
            and str(fav_before["created_at"]) == str(fav_after["created_at"])
        ),
        "cart_persisted": bool(
            cart_before
            and cart_after
            and str(cart_before["id"]) == str(cart_after["id"])
            and str(cart_before["quantity"]) == str(cart_after["quantity"])
        ),
    }
    RESTART_PROOF_PATH.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return proof


def ensure_page_products(env, fx, n: int = 12) -> list[str]:
    """Create/reuse B031-PAGE-00.. for pagination (>10 favorites)."""
    seller = fx["tokens"]["S"]
    cat = fx["category2Id"]
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM product WHERE name LIKE 'B031-PAGE-%'")
            existing = {r["name"]: str(r["id"]) for r in cur.fetchall()}
    finally:
        conn.close()
    pids = []
    for i in range(n):
        name = f"B031-PAGE-{i:02d}"
        if name in existing:
            pid = existing[name]
            # ensure online
            row = _product_row(env, pid)
            if row["status"] != "ONLINE":
                http_json(
                    "POST",
                    f"{base_url(env)}/api/admin/products/{pid}/online",
                    headers=auth(seller),
                )
        else:
            http, body = multipart_post(
                f"{base_url(env)}/api/admin/products",
                {
                    "name": name,
                    "price": f"{10 + i}.00",
                    "category2Id": cat,
                    "stock": "20",
                    "sellingMode": "FIXED_PRICE",
                    "descriptionHtml": f"<p>{name}</p>",
                },
                [("images", SEED)],
                auth(seller),
            )
            if http not in (200, 201):
                raise RuntimeError(f"create {name}: {http} {body}")
            pid = str(body["data"].get("productId") or body["data"].get("id"))
        pids.append(pid)
    return pids


def create_seed2_image_product(env, fx) -> dict:
    """Create a real product with seed2.png via Admin multipart; return stored image_path."""
    seller = fx["tokens"]["S"]
    name = f"B031-SEED2-{uuid.uuid4().hex[:8]}"
    http, body = multipart_post(
        f"{base_url(env)}/api/admin/products",
        {
            "name": name,
            "price": "1.00",
            "category2Id": fx["category2Id"],
            "stock": "1",
            "sellingMode": "FIXED_PRICE",
            "descriptionHtml": "<p>seed2 donor</p>",
        },
        [("images", SEED2)],
        auth(seller),
    )
    if http not in (200, 201):
        raise RuntimeError(f"seed2 donor: {http} {body}")
    pid = str(body["data"].get("productId") or body["data"].get("id"))
    path = product_image_path(env, pid)
    return {"donor_product_id": pid, "image_path": path, "name": name, "http": http}


def run_ac(env, fx, ac_id: str) -> dict:
    ta, tb, ts = fx["tokens"]["A"], fx["tokens"]["B"], fx["tokens"]["S"]
    p = fx["products"]
    base = base_url(env)
    fe = fe_url(env)
    reset_ns(env)
    try:
        ta = login_customer(env, "b031_buyer_a", "B031-BuyerA-Pass9")
        tb = login_customer(env, "b031_buyer_b", "B031-BuyerB-Pass9")
        ts = login_seller(env)
        fx["tokens"] = {"A": ta, "B": tb, "S": ts}
    except Exception as e:
        return result(ac_id, "FAIL", {"exception": f"relogin: {e}"})

    if ac_id == "PB-B08-AC1":
        # API model: /api/me/favorites/{productId} is caller-scoped; no foreign favoriteId resource.
        api_model = {
            "favorites_resource": "/api/me/favorites/{productId}",
            "addressable_by": "caller's own productId namespace only",
            "foreign_favorite_id_endpoint": None,
            "note": "No API exposes another user's favorite row id for direct mutate/delete.",
        }
        c1, b1 = http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}")
        c2, b2 = http_json(
            "PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth("invalid.token.value")
        )
        c3, b3 = http_json(
            "PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ts)
        )
        c4, b4 = http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        a_before = fav_count(env, "b031_buyer_a", p["P-ON-10"])
        a_row = fav_db_row(env, "b031_buyer_a", p["P-ON-10"])
        # B DELETE same productId → B's namespace (未收藏); must NOT remove A's favorite
        c5, b5 = http_json(
            "DELETE", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(tb)
        )
        a_after_b = fav_count(env, "b031_buyer_a", p["P-ON-10"])
        b_after = fav_count(env, "b031_buyer_b", p["P-ON-10"])
        # B GET state for same productId is B's state, not A's
        c_st, b_st = http_json(
            "GET", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(tb)
        )
        # Cross-user cart ownership (NOT favorites proof) — labeled separately
        http_json(
            "POST",
            f"{base}/api/me/cart/items",
            {"productId": p["P-ON-5"]},
            headers=auth(ta, new_key()),
        )
        c_cart, b_cart = http_json("GET", f"{base}/api/me/cart", headers=auth(ta))
        a_item = (cart_items(b_cart) or [{}])[0].get("cartItemId")
        c6, b6 = http_json(
            "POST",
            f"{base}/api/me/cart/move-to-favorites",
            {"cartItemIds": [str(a_item)]},
            headers=auth(tb, new_key()),
        )
        cart_a_after = cart_count(env, "b031_buyer_a", p["P-ON-5"])
        c7, b7 = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(tb))
        foreign = [i for i in fav_items(b7) if str(i.get("productId")) == p["P-ON-10"]]
        seller_msg = msg(b3)
        seller_ok = seller_msg == "无此权限"  # PO exact contract
        isolation_ok = (
            msg(b5) == "未收藏"
            and a_before == a_after_b == 1
            and b_after == 0
            and len(foreign) == 0
            and a_row is not None
        )
        cart_cross_ok = msg(b6) == "无权操作" and cart_a_after == 1
        basic = (
            msg(b1) == "请先登录"
            and msg(b2) == "请重新登录"
            and msg(b4) == "已收藏"
            and c4 == 200
        )
        detail = {
            "api_model": api_model,
            "unauth": b1,
            "invalid_auth": b2,
            "seller": b3,
            "ok": b4,
            "b_delete_own_namespace": {
                "response": b5,
                "message": msg(b5),
                "a_fav_count_before": a_before,
                "a_fav_count_after": a_after_b,
                "b_fav_count_after": b_after,
                "a_db_row": {
                    "id": str(a_row["id"]) if a_row else None,
                    "created_at": str(a_row["created_at"]) if a_row else None,
                },
            },
            "b_state_for_same_productId": b_st,
            "cart_ownership_cross_move_NOT_favorites_proof": {
                "response": b6,
                "message": msg(b6),
                "a_cart_count_after": cart_a_after,
                "note": "Tests cart line ownership via move-to-favorites; not a foreign-favorite mutate.",
            },
            "b_list_has_a_product": len(foreign),
            "expected_seller_message": "无此权限",
            "actual_seller_message": seller_msg,
            "seller_code": code_of(b3),
            "observations": {
                "foreign_favorite_mutate_endpoint_exists": False,
                "tested_isolation_paths": [
                    "B DELETE /api/me/favorites/{productId} only affects B namespace (未收藏)",
                    "A favorite row count/id unchanged after B DELETE",
                    "B list does not contain A's favorited product solely via B namespace ops",
                    "cart move-to-favorites with foreign cartItemId → 无权操作 (cart proof only)",
                ],
            },
        }
        if not (basic and isolation_ok and cart_cross_ok and seller_ok):
            reasons = []
            if not seller_ok:
                reasons.append(
                    f"商家访问期望「无此权限」，实得「{seller_msg}」/code={code_of(b3)}"
                )
            if not isolation_ok:
                reasons.append("favorites namespace isolation failed")
            if not cart_cross_ok:
                reasons.append(f"cart cross 无权操作 failed: {msg(b6)}")
            if not basic:
                reasons.append("login/basic assertions")
            return expect(False, detail, ac_id, "; ".join(reasons))
        return expect(True, detail, ac_id)

    if ac_id == "PB-B08-AC2":
        conn = connect_mysql(env)
        with conn.cursor() as cur:
            cur.execute("SELECT stock, status FROM product WHERE id=%s", (p["P-ON-10"],))
            before = cur.fetchone()
        c, b = http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        with conn.cursor() as cur:
            cur.execute("SELECT stock, status FROM product WHERE id=%s", (p["P-ON-10"],))
            after = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) c FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username='b031_buyer_a'"
            )
            orders = cur.fetchone()["c"]
        conn.close()
        ok = msg(b) == "已收藏" and before == after and orders == 0
        return expect(ok, {"before": before, "after": after, "orders": orders, "resp": b}, ac_id)

    if ac_id == "PB-B08-AC3":
        c1, b1 = http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        created = (b1.get("data") or {}).get("createdAt")
        c2, b2 = http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        created2 = (b2.get("data") or {}).get("createdAt")
        cnt = fav_count(env, "b031_buyer_a", p["P-ON-10"])
        ok = msg(b1) == "已收藏" and msg(b2) == "已收藏" and created == created2 and cnt == 1
        return expect(ok, {"first": b1, "second": b2, "count": cnt}, ac_id)

    if ac_id == "PB-B08-AC4":
        c1, b1 = http_json("PUT", f"{base}/api/me/favorites/{p['P-OFF-M']}", headers=auth(ta))
        c2, b2 = http_json("PUT", f"{base}/api/me/favorites/{p['P-ZERO']}", headers=auth(ta))
        c3, b3 = http_json("PUT", f"{base}/api/me/favorites/{p['P-GONE']}", headers=auth(ta))
        ok = msg(b1) == "商品已下架" and msg(b2) == "商品已下架" and msg(b3) == "商品不存在"
        return expect(ok, {"offline": b1, "zero": b2, "gone": b3}, ac_id)

    if ac_id == "PB-B08-AC5":
        SHOTS.mkdir(parents=True, exist_ok=True)
        search_kw = "B031-在售-10"
        js = f"""
const {{ chromium }} = require('{PW_DIR}/node_modules/playwright');
(async () => {{
  const b = await chromium.launch({{ headless: true }});
  const page = await b.newPage();
  try {{
    await page.goto('{fe}/login', {{ waitUntil: 'networkidle' }});
    await page.locator('#username').fill('b031_buyer_a');
    await page.locator('#password').fill('B031-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{ timeout: 15000 }});
    await page.goto('{fe}/', {{ waitUntil: 'networkidle' }});
    const listFav = await page.getByRole('button', {{ name: /收\\s*藏|取消\\s*收\\s*藏/ }}).count();
    await page.screenshot({{ path: '{SHOTS}/b08ac5-list-logged-in.png', fullPage: true }});
    const search = page.locator('input[aria-label="商品关键词"]');
    await search.fill('{search_kw}');
    await page.waitForTimeout(900);
    await page.waitForLoadState('networkidle');
    const searchFav = await page.getByRole('button', {{ name: /收\\s*藏|取消\\s*收\\s*藏/ }}).count();
    const searchCards = await page.locator('.ant-card').count();
    await page.screenshot({{ path: '{SHOTS}/b08ac5-search-results.png', fullPage: true }});
    // enter detail from a search card link
    await page.locator('a[href*="/products/{p['P-ON-10']}"]').first().click();
    await page.waitForURL(u => String(u).includes('/products/{p['P-ON-10']}'), {{ timeout: 10000 }});
    const favToggle = page.getByRole('button', {{ name: /收\\s*藏|取消\\s*收\\s*藏/ }});
    await favToggle.waitFor({{ timeout: 10000 }});
    // ensure starting from unfavorited for state screenshot
    if ((await favToggle.innerText()).includes('取消')) {{
      await favToggle.click();
      await page.waitForTimeout(600);
      await favToggle.waitFor({{ timeout: 10000 }});
    }}
    const unfavText = await favToggle.innerText();
    const unfav = /取消/.test(unfavText) ? 0 : 1;
    await page.screenshot({{ path: '{SHOTS}/b08ac5-detail-unfavorited.png', fullPage: true }});
    await favToggle.click();
    await page.waitForTimeout(700);
    await favToggle.waitFor({{ timeout: 10000 }});
    const favText = await favToggle.innerText();
    const fav = /取消/.test(favText) ? 1 : 0;
    await page.screenshot({{ path: '{SHOTS}/b08ac5-detail-favorited.png', fullPage: true }});
    console.log(JSON.stringify({{ ok:true, listFav, searchFav, searchCards, unfav, fav, unfavText, favText, url: page.url() }}));
  }} catch(e) {{ console.log(JSON.stringify({{ ok:false, error:String(e) }})); }}
  finally {{ await b.close(); }}
}})();
"""
        ui = run_node(js, "ui_b08ac5")
        shots = [
            "evidence/screenshots/b08ac5-list-logged-in.png",
            "evidence/screenshots/b08ac5-search-results.png",
            "evidence/screenshots/b08ac5-detail-unfavorited.png",
            "evidence/screenshots/b08ac5-detail-favorited.png",
        ]
        ok = (
            ui.get("ok")
            and ui.get("listFav", 1) == 0
            and ui.get("searchFav", 1) == 0
            and ui.get("searchCards", 0) >= 1
            and ui.get("unfav", 0) >= 1
            and ui.get("fav", 0) >= 1
        )
        return expect(
            ok,
            {"ui": ui, "screenshots": shots, "search_keyword": search_kw},
            ac_id,
            "list/search absence or detail state",
        )

    if ac_id == "PB-B09-AC1":
        # Primary lifecycle on P-ON-10 WITHOUT cancel before re-online
        c_put, b_put = http_json(
            "PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta)
        )
        orig = b_put.get("data") or {}
        orig_fid = str(orig.get("favoriteId") or "")
        orig_ts = orig.get("createdAt")
        db_orig = fav_db_row(env, "b031_buyer_a", p["P-ON-10"])
        http_json("POST", f"{base}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(ts))
        c, b = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
        hit = next((i for i in fav_items(b) if str(i.get("productId")) == p["P-ON-10"]), None)
        retained = hit and hit.get("invalidLabel") == "已下架" and hit.get("valid") is False
        # UI: click offline name (span) — stay on favorites; Tag 已下架; no buyable link
        js = f"""
const {{ chromium }} = require('{PW_DIR}/node_modules/playwright');
(async () => {{
  const b = await chromium.launch({{ headless: true }});
  const page = await b.newPage();
  try {{
    await page.goto('{fe}/login', {{ waitUntil: 'networkidle' }});
    await page.locator('#username').fill('b031_buyer_a');
    await page.locator('#password').fill('B031-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{ timeout: 15000 }});
    await page.goto('{fe}/me/favorites', {{ waitUntil: 'networkidle' }});
    const labelTag = await page.getByText('已下架', {{ exact: true }}).count();
    const links = await page.locator('a[href*="/products/{p['P-ON-10']}"]').count();
    // click the non-link product name cell
    const nameCell = page.locator('table tbody tr').filter({{ hasText: '已下架' }}).locator('td').first();
    await nameCell.click();
    await page.waitForTimeout(400);
    const urlAfterClick = page.url();
    const stillFavorites = urlAfterClick.includes('/me/favorites');
    await page.screenshot({{ path: '{SHOTS}/b09ac1-offline-favorite.png', fullPage: true }});
    // forced detail must surface exact UI tip「已下架」; alternate Empty copy is NOT a substitute
    await page.goto('{fe}/products/{p['P-ON-10']}', {{ waitUntil: 'networkidle' }});
    const unavailableEmpty = await page.getByText('商品当前不可查看').count();
    const tipOfflineExact = await page.getByText('已下架', {{ exact: true }}).count();
    const addBtn = await page.getByRole('button', {{ name: /加入购物车/ }}).count();
    await page.screenshot({{ path: '{SHOTS}/b09ac1-offline-detail-nobuy.png', fullPage: true }});
    console.log(JSON.stringify({{ ok:true, labelTag, buyableLinks: links, stillFavorites, urlAfterClick, unavailableEmpty, tipOfflineExact, addBtn }}));
  }} catch(e) {{ console.log(JSON.stringify({{ ok:false, error:String(e) }})); }}
  finally {{ await b.close(); }}
}})();
"""
        ui = run_node(js, "ui_b09ac1")
        # API message observed for documentation only — does NOT substitute UI tip「已下架」
        c_det, b_det = http_json("GET", f"{base}/api/products/{p['P-ON-10']}")
        api_offline_tip = msg(b_det)  # recorded; exact UI tip required separately
        # Re-online SAME original favorite — no cancel/refavorite
        http_json("POST", f"{base}/api/admin/products/{p['P-ON-10']}/online", headers=auth(ts))
        c2, b2 = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
        hit2 = next((i for i in fav_items(b2) if str(i.get("productId")) == p["P-ON-10"]), None)
        db_after = fav_db_row(env, "b031_buyer_a", p["P-ON-10"])
        same_identity = (
            hit2 is not None
            and str(hit2.get("favoriteId")) == orig_fid
            and hit2.get("createdAt") == orig_ts
            and hit2.get("valid") is True
            and hit2.get("invalidLabel") is None
            and db_orig
            and db_after
            and str(db_orig["id"]) == str(db_after["id"])
            and str(db_orig["created_at"]) == str(db_after["created_at"])
        )
        # Cancel proof on SEPARATE fixture P-ON-5 (offline)
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-5']}", headers=auth(ta))
        http_json("POST", f"{base}/api/admin/products/{p['P-ON-5']}/offline", headers=auth(ts))
        c_can, b_can = http_json(
            "DELETE", f"{base}/api/me/favorites/{p['P-ON-5']}", headers=auth(ta)
        )
        cancellable_separate = msg(b_can) == "已取消收藏"
        http_json("POST", f"{base}/api/admin/products/{p['P-ON-5']}/online", headers=auth(ts))
        # Republish NEW product — original favorite identity stays on old productId
        http, body = multipart_post(
            f"{base}/api/admin/products",
            {
                "name": "B031-REPUB-" + uuid.uuid4().hex[:8],
                "price": "12.50",
                "category2Id": fx["category2Id"],
                "stock": "10",
                "sellingMode": "FIXED_PRICE",
                "descriptionHtml": "<p>republish</p>",
            },
            [("images", SEED)],
            auth(ts),
        )
        new_pid = str((body or {}).get("data", {}).get("productId") or "")
        # primary still offline? we re-onlined P-ON-10 above — offline again for republish check
        http_json("POST", f"{base}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(ts))
        c3, b3 = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
        hit3 = next((i for i in fav_items(b3) if str(i.get("productId")) == p["P-ON-10"]), None)
        no_redirect = (
            hit3
            and str(hit3.get("favoriteId")) == orig_fid
            and str(hit3.get("productId")) == p["P-ON-10"]
            and str(hit3.get("productId")) != new_pid
            and not any(str(i.get("productId")) == new_pid for i in fav_items(b3))
            and hit3.get("invalidLabel") == "已下架"
        )
        # restore P-ON-10 online for later ACs
        http_json("POST", f"{base}/api/admin/products/{p['P-ON-10']}/online", headers=auth(ts))
        # Exact UI tip「已下架」required on forced-detail path (tipOfflineExact).
        # Alternate copy「商品当前不可查看」/ API「商品已下架」MUST NOT substitute.
        tip_exact_ok = ui.get("ok") and ui.get("tipOfflineExact", 0) >= 1
        ok = (
            retained
            and same_identity
            and cancellable_separate
            and no_redirect
            and ui.get("ok")
            and ui.get("labelTag", 0) >= 1  # favorites Tag exact「已下架」
            and ui.get("buyableLinks", 1) == 0
            and ui.get("stillFavorites") is True
            and tip_exact_ok
            and ui.get("addBtn", 1) == 0
            and http in (200, 201)
        )
        fail_reason = ""
        if not tip_exact_ok:
            fail_reason = (
                f"期望强制详情 UI tip「已下架」，tipOfflineExact={ui.get('tipOfflineExact', 0)}；"
                f"「商品当前不可查看」(unavailableEmpty={ui.get('unavailableEmpty', 0)})/"
                f"API「{api_offline_tip}」不能替代"
            )
        elif not ok:
            fail_reason = "offline retain / same-id reonline / cancel-separate / republish"
        return expect(
            ok,
            {
                "orig_favorite": {"favoriteId": orig_fid, "createdAt": orig_ts},
                "hit_offline": hit,
                "api_detail_offline_tip": b_det,
                "ui_click": ui,
                "ui_tip_rule": {
                    "required": "已下架",
                    "tipOfflineExact": ui.get("tipOfflineExact"),
                    "unavailableEmpty_not_substitute": True,
                    "api_message_not_substitute": True,
                },
                "hit_reonline_same": hit2,
                "db_before": {
                    "id": str(db_orig["id"]) if db_orig else None,
                    "created_at": str(db_orig["created_at"]) if db_orig else None,
                },
                "db_after_reonline": {
                    "id": str(db_after["id"]) if db_after else None,
                    "created_at": str(db_after["created_at"]) if db_after else None,
                },
                "cancel_separate_fixture": b_can,
                "new_pid": new_pid,
                "hit_after_republish": hit3,
                "screenshots": [
                    "evidence/screenshots/b09ac1-offline-favorite.png",
                    "evidence/screenshots/b09ac1-offline-detail-nobuy.png",
                ],
            },
            ac_id,
            fail_reason or "offline retain / same-id reonline / cancel-separate / republish",
        )

    if ac_id == "PB-B09-AC2":
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-5']}", headers=auth(ta))
        c0, b0 = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
        before = next((i for i in fav_items(b0) if str(i.get("productId")) == p["P-ON-5"]), None)
        before_img = (before or {}).get("mainImageUrl")
        # Prove Admin PATCH cannot change name/price/image
        c_patch, b_patch = http_json(
            "PATCH",
            f"{base}/api/admin/products/{p['P-ON-5']}",
            {"stock": "5", "name": "SHOULD-NOT-APPLY", "price": "99.99"},
            auth(ts),
        )
        img_after_patch = product_image_path(env, p["P-ON-5"])
        row_after_patch = _product_row(env, p["P-ON-5"])
        # Real different image via Admin create with seed2.png
        donor = create_seed2_image_product(env, fx)
        new_img = donor["image_path"]
        new_name = "B031-在售-5-LIVE"
        new_price = "18.88"
        mutation = {
            "admin_api_supports_name_price_image_after_publish": False,
            "admin_patch_observation": {
                "http": c_patch,
                "body": b_patch,
                "name_unchanged": row_after_patch["name"] != "SHOULD-NOT-APPLY",
                "image_unchanged": img_after_patch == before_img or img_after_patch == product_image_path(env, p["P-ON-5"]),
            },
            "channel": "fixture_setup_db_copy_from_seed2_admin_created_product",
            "seed2_donor": donor,
            "before_mainImageUrl": before_img,
            "target_image_path": new_img,
        }
        if not new_img or new_img == before_img:
            return result(
                ac_id,
                "FAIL",
                {
                    "before": before,
                    "mutation": mutation,
                    "fail_reason": "seed2 image path not distinct from before",
                },
            )
        db_update_product_live(env, p["P-ON-5"], new_name, new_price, image_path=new_img)
        c, b = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
        hit = next((i for i in fav_items(b) if str(i.get("productId")) == p["P-ON-5"]), None)
        ok = (
            hit is not None
            and hit.get("productName") == new_name
            and str(hit.get("unitPrice")) == new_price
            and hit.get("mainImageUrl") == new_img
            and hit.get("mainImageUrl") != before_img
        )
        mutation["after"] = hit
        # restore canonical product fields + original image
        db_update_product_live(
            env, p["P-ON-5"], "B031-在售-5", "8.00", image_path=before_img
        )
        return expect(ok, {"before": before, "mutation": mutation}, ac_id, "live name/price/image binding")

    if ac_id == "PB-B09-AC3":
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        c1, b1 = http_json("DELETE", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        c2, b2 = http_json("DELETE", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        ok = msg(b1) == "已取消收藏" and msg(b2) == "未收藏"
        return expect(ok, {"first": b1, "second": b2}, ac_id)

    if ac_id == "PB-B09-AC4":
        reset_ns(env)
        js = f"""
const {{ chromium }} = require('{PW_DIR}/node_modules/playwright');
(async () => {{
  const b = await chromium.launch({{ headless: true }});
  const page = await b.newPage();
  try {{
    await page.goto('{fe}/login', {{ waitUntil: 'networkidle' }});
    await page.locator('#username').fill('b031_buyer_a');
    await page.locator('#password').fill('B031-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{ timeout: 15000 }});
    await page.goto('{fe}/me/favorites', {{ waitUntil: 'networkidle' }});
    const emptyText = await page.getByText('暂无收藏').count();
    await page.screenshot({{ path: '{SHOTS}/b09ac4-empty-favorites.png', fullPage: true }});
    console.log(JSON.stringify({{ ok:true, emptyText }}));
  }} catch(e) {{ console.log(JSON.stringify({{ ok:false, error:String(e) }})); }}
  finally {{ await b.close(); }}
}})();
"""
        ui = run_node(js, "ui_b09ac4")
        page_pids = ensure_page_products(env, fx, 12)
        created_meta = []
        for pid in page_pids:
            time.sleep(0.02)
            c_put, b_put = http_json("PUT", f"{base}/api/me/favorites/{pid}", headers=auth(ta))
            created_meta.append(
                {
                    "productId": pid,
                    "favoriteId": str((b_put.get("data") or {}).get("favoriteId") or ""),
                    "createdAt": (b_put.get("data") or {}).get("createdAt"),
                    "message": msg(b_put),
                }
            )
        c1, b1 = http_json("GET", f"{base}/api/me/favorites?page=1&size=10", headers=auth(ta))
        c2, b2 = http_json("GET", f"{base}/api/me/favorites?page=2&size=10", headers=auth(ta))
        d1 = (b1 or {}).get("data") or {}
        d2 = (b2 or {}).get("data") or {}
        items1 = fav_items(b1)
        items2 = fav_items(b2)
        page_meta = {
            "page1": {
                "page": d1.get("page"),
                "size": d1.get("size"),
                "total": d1.get("total"),
                "pages": d1.get("pages"),
                "count": len(items1),
                "createdAts": [i.get("createdAt") for i in items1],
                "productIds": [str(i.get("productId")) for i in items1],
            },
            "page2": {
                "page": d2.get("page"),
                "size": d2.get("size"),
                "total": d2.get("total"),
                "pages": d2.get("pages"),
                "count": len(items2),
                "createdAts": [i.get("createdAt") for i in items2],
                "productIds": [str(i.get("productId")) for i in items2],
            },
        }
        # descending createdAt across page1 (newest first)
        ats = [i.get("createdAt") for i in items1 if i.get("createdAt")]
        desc_ok = ats == sorted(ats, reverse=True) and len(ats) == 10
        page_ok = (
            d1.get("size") == 10
            and d1.get("page") == 1
            and int(d1.get("total") or 0) >= 12
            and int(d1.get("pages") or 0) >= 2
            and len(items1) == 10
            and len(items2) >= 2
        )
        # idempotent repeat preserves timestamp/order for first page top item
        top_pid = str(items1[0].get("productId"))
        top_ts = items1[0].get("createdAt")
        top_fid = str(items1[0].get("favoriteId"))
        c_idemp, b_idemp = http_json(
            "PUT", f"{base}/api/me/favorites/{top_pid}", headers=auth(ta)
        )
        idemp_ts = (b_idemp.get("data") or {}).get("createdAt")
        c1b, b1b = http_json("GET", f"{base}/api/me/favorites?page=1&size=10", headers=auth(ta))
        items1b = fav_items(b1b)
        idemp_ok = (
            idemp_ts == top_ts
            and str(items1b[0].get("favoriteId")) == top_fid
            and str(items1b[0].get("productId")) == top_pid
            and items1b[0].get("createdAt") == top_ts
        )
        # cancel + re-favorite updates time/order
        http_json("DELETE", f"{base}/api/me/favorites/{top_pid}", headers=auth(ta))
        time.sleep(0.05)
        c_ref, b_ref = http_json("PUT", f"{base}/api/me/favorites/{top_pid}", headers=auth(ta))
        ref_ts = (b_ref.get("data") or {}).get("createdAt")
        c1c, b1c = http_json("GET", f"{base}/api/me/favorites?page=1&size=10", headers=auth(ta))
        items1c = fav_items(b1c)
        reorder_ok = (
            ref_ts is not None
            and ref_ts != top_ts
            and str(items1c[0].get("productId")) == top_pid
            and items1c[0].get("createdAt") == ref_ts
        )
        ok = ui.get("emptyText", 0) >= 1 and page_ok and desc_ok and idemp_ok and reorder_ok
        return expect(
            ok,
            {
                "ui": ui,
                "created_meta_count": len(created_meta),
                "page_meta": page_meta,
                "idempotent": {"before_ts": top_ts, "after_ts": idemp_ts, "resp": b_idemp},
                "cancel_refavorite": {"old_ts": top_ts, "new_ts": ref_ts, "resp": b_ref},
                "screenshots": ["evidence/screenshots/b09ac4-empty-favorites.png"],
            },
            ac_id,
            "empty/page/sort/idempotent/reorder",
        )

    if ac_id == "PB-B09-AC5":
        # dual independent sessions with list payloads
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        ta2 = login_customer(env, "b031_buyer_a", "B031-BuyerA-Pass9")
        c_s1, b_s1 = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
        c_s2, b_s2 = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta2))
        dual = (
            any(str(i.get("productId")) == p["P-ON-10"] for i in fav_items(b_s1))
            and any(str(i.get("productId")) == p["P-ON-10"] for i in fav_items(b_s2))
        )
        # browser refresh + logout/relogin
        js = f"""
const {{ chromium }} = require('{PW_DIR}/node_modules/playwright');
(async () => {{
  const b = await chromium.launch({{ headless: true }});
  const page = await b.newPage();
  try {{
    await page.goto('{fe}/login', {{ waitUntil: 'networkidle' }});
    await page.locator('#username').fill('b031_buyer_a');
    await page.locator('#password').fill('B031-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{ timeout: 15000 }});
    await page.goto('{fe}/me/favorites', {{ waitUntil: 'networkidle' }});
    const before = await page.locator('table tbody tr').count();
    await page.reload({{ waitUntil: 'networkidle' }});
    const afterRefresh = await page.locator('table tbody tr').count();
    await page.goto('{fe}/', {{ waitUntil: 'networkidle' }});
    await page.getByRole('button', {{ name: '退出登录' }}).click();
    await page.waitForTimeout(500);
    await page.goto('{fe}/login', {{ waitUntil: 'networkidle' }});
    await page.locator('#username').fill('b031_buyer_a');
    await page.locator('#password').fill('B031-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{ timeout: 15000 }});
    await page.goto('{fe}/me/favorites', {{ waitUntil: 'networkidle' }});
    const afterRelogin = await page.locator('table tbody tr').count();
    console.log(JSON.stringify({{ ok:true, before, afterRefresh, afterRelogin }}));
  }} catch(e) {{ console.log(JSON.stringify({{ ok:false, error:String(e) }})); }}
  finally {{ await b.close(); }}
}})();
"""
        ui = run_node(js, "ui_b09ac5_refresh")
        # concurrent favorite/cancel with DB count + write order
        reset_ns(env)
        barrier = threading.Barrier(2)
        box = {}

        def put_then():
            barrier.wait()
            t0 = time.time()
            code, body = http_json(
                "PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta)
            )
            box["put"] = {"http": code, "message": msg(body), "t": t0, "t_done": time.time(), "body": body}

        def del_later():
            barrier.wait()
            time.sleep(0.15)
            t0 = time.time()
            code, body = http_json(
                "DELETE", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta)
            )
            box["del"] = {"http": code, "message": msg(body), "t": t0, "t_done": time.time(), "body": body}

        t1 = threading.Thread(target=put_then)
        t2 = threading.Thread(target=del_later)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        final_cnt = fav_count(env, "b031_buyer_a", p["P-ON-10"])
        final_row = fav_db_row(env, "b031_buyer_a", p["P-ON-10"])
        concurrent_ok = (
            final_cnt == 0
            and final_row is None
            and box.get("del", {}).get("t", 0) >= box.get("put", {}).get("t", 0)
            and box.get("put", {}).get("http") == 200
            and box.get("del", {}).get("http") == 200
        )
        # seed favorite + cart then ONE proven restart (shared with B11AC3)
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-5']}", headers=auth(ta))
        http_json(
            "POST",
            f"{base}/api/me/cart/items",
            {"productId": p["P-ON-10"]},
            headers=auth(ta, new_key()),
        )
        proof = restart_backend_proven(
            env, favorite_product_id=p["P-ON-5"], cart_product_id=p["P-ON-10"]
        )
        fx["_restart_proof"] = proof
        if proof.get("feasible") and proof.get("health_after"):
            fx["tokens"]["A"] = login_customer(env, "b031_buyer_a", "B031-BuyerA-Pass9")
            fx["tokens"]["B"] = login_customer(env, "b031_buyer_b", "B031-BuyerB-Pass9")
            fx["tokens"]["S"] = login_seller(env)
            ta = fx["tokens"]["A"]
            c3, b3 = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
            after_api = any(str(i.get("productId")) == p["P-ON-5"] for i in fav_items(b3))
        else:
            after_api = False
        if not proof.get("feasible"):
            return result(
                ac_id,
                "BLOCKED",
                {
                    "dual_session_payloads": {"s1": b_s1, "s2": b_s2},
                    "ui_refresh_logout": ui,
                    "concurrent": box,
                    "final_cnt": final_cnt,
                    "final_row": final_row,
                    "restart_proof": proof,
                    "reason": "genuine BE restart with downtime/PID proof not feasible",
                },
            )
        ok = (
            dual
            and ui.get("ok")
            and ui.get("afterRefresh", 0) >= 1
            and ui.get("afterRelogin", 0) >= 1
            and concurrent_ok
            and proof.get("feasible")
            and proof.get("favorite_persisted")
            and proof.get("cart_persisted")
            and after_api
            and proof.get("downtime_observed")
            and proof.get("pid_changed")
        )
        return expect(
            ok,
            {
                "dual_session_payloads": {
                    "session1_total": ((b_s1 or {}).get("data") or {}).get("total"),
                    "session2_total": ((b_s2 or {}).get("data") or {}).get("total"),
                    "both_have_product": dual,
                },
                "ui_refresh_logout": ui,
                "concurrent": {
                    "writes": box,
                    "final_cnt": final_cnt,
                    "final_row": final_row,
                    "order": "delete_after_put",
                },
                "restart_proof": proof,
                "after_restart_api_has_favorite": after_api,
                "restart_proof_path": "evidence/restart-proof.json",
            },
            ac_id,
            "dual/refresh/concurrent/restart persistence",
        )

    if ac_id == "PB-B10-AC1":
        c1, b1 = http_json(
            "POST",
            f"{base}/api/me/cart/items",
            {"productId": p["P-ON-10"]},
            headers={"Idempotency-Key": new_key()},
        )
        c2, b2 = http_json(
            "POST",
            f"{base}/api/me/cart/items",
            {"productId": p["P-ON-10"]},
            headers=auth("bad.token", new_key()),
        )
        c3, b3 = http_json(
            "POST",
            f"{base}/api/me/cart/items",
            {"productId": p["P-ON-10"]},
            headers=auth(ta, new_key()),
        )
        cid = (b3.get("data") or {}).get("cartItemId")
        before = cart_count(env, "b031_buyer_a", p["P-ON-10"])
        c4, b4 = http_json(
            "PATCH",
            f"{base}/api/me/cart/items/{cid}",
            {"quantity": "2"},
            headers=auth(tb),
        )
        after = cart_count(env, "b031_buyer_a", p["P-ON-10"])
        c5, b5 = http_json(
            "POST",
            f"{base}/api/me/cart/items",
            {"productId": p["P-ON-5"]},
            headers=auth(ts, new_key()),
        )
        seller_msg = msg(b5)
        # AC only requires refuse for authenticated seller; do NOT accept 请先登录.
        # Distinct from PB-B08-AC1 PO rule requiring exact「无此权限」for favorites.
        seller_refused = seller_msg not in ("", None) and seller_msg != "请先登录" and c5 != 200
        ok = (
            msg(b1) == "请先登录"
            and msg(b2) == "请重新登录"
            and msg(b3) == "已加入购物车"
            and msg(b4) == "无权操作"
            and before == after == 1
            and seller_refused
        )
        return expect(
            ok,
            {
                "unauth": b1,
                "bad": b2,
                "ok": b3,
                "cross": b4,
                "seller_add": b5,
                "seller_observed_message": seller_msg,
                "seller_http": c5,
                "seller_ruling_note": (
                    "Authenticated seller refused (observed text recorded). "
                    "Not subject to PB-B08-AC1 exact「无此权限」PO ruling; "
                    "「请先登录」not accepted for authenticated seller."
                ),
            },
            ac_id,
        )

    if ac_id == "PB-B10-AC2":
        c1, b1 = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-ON-10"]}, headers=auth(ta, new_key())
        )
        k = new_key()
        c2, b2 = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-ON-5"]}, headers=auth(ta, k)
        )
        c3, b3 = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-ON-5"]}, headers=auth(ta, k)
        )
        c4, b4 = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-ON-10"]}, headers=auth(ta, new_key())
        )
        conn = connect_mysql(env)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ci.product_id, ci.quantity FROM cart_item ci "
                "JOIN customer c ON c.id=ci.customer_id WHERE c.username='b031_buyer_a'"
            )
            rows = cur.fetchall()
        conn.close()
        by_p = {str(r["product_id"]): str(r["quantity"]) for r in rows}
        ok = (
            msg(b1) == "已加入购物车"
            and msg(b2) == "已加入购物车"
            and msg(b3) == "已加入购物车"
            and (b2.get("data") or {}).get("cartItemId") == (b3.get("data") or {}).get("cartItemId")
            and str((b3.get("data") or {}).get("quantity") or "1") == "1"
            and by_p.get(p["P-ON-10"]) == "2"
            and len(by_p) == 2
        )
        return expect(ok, {"rows": rows, "b1": b1, "b2": b2, "b3": b3, "b4": b4}, ac_id)

    if ac_id == "PB-B10-AC3":
        conn = connect_mysql(env)
        with conn.cursor() as cur:
            cur.execute("SELECT stock FROM product WHERE id=%s", (p["P-ON-10"],))
            before = cur.fetchone()["stock"]
        c, b = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-ON-10"]}, headers=auth(ta, new_key())
        )
        cid = (b.get("data") or {}).get("cartItemId")
        http_json("PATCH", f"{base}/api/me/cart/items/{cid}", {"quantity": "7"}, headers=auth(ta))
        with conn.cursor() as cur:
            cur.execute("SELECT stock FROM product WHERE id=%s", (p["P-ON-10"],))
            after = cur.fetchone()["stock"]
            cur.execute(
                "SELECT COUNT(*) c FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username='b031_buyer_a'"
            )
            orders = cur.fetchone()["c"]
        conn.close()
        ok = str(before) == str(after) and orders == 0 and msg(b) == "已加入购物车"
        return expect(ok, {"before": before, "after": after, "orders": orders}, ac_id)

    if ac_id == "PB-B10-AC4":
        c, b = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-ON-10"]}, headers=auth(ta, new_key())
        )
        cid = (b.get("data") or {}).get("cartItemId")
        c1, b1 = http_json(
            "PATCH", f"{base}/api/me/cart/items/{cid}", {"quantity": "99"}, headers=auth(ta)
        )
        c2, b2 = http_json(
            "PATCH", f"{base}/api/me/cart/items/{cid}", {"quantity": "-1"}, headers=auth(ta)
        )
        c3, b3 = http_json(
            "PATCH", f"{base}/api/me/cart/items/{cid}", {"quantity": "1.5"}, headers=auth(ta)
        )
        c4, b4 = http_json(
            "PATCH", f"{base}/api/me/cart/items/{cid}", {"quantity": "0"}, headers=auth(ta)
        )
        ok = (
            msg(b1) == "已更新"
            and str((b1.get("data") or {}).get("quantity")) == "99"
            and msg(b2) == "数量无效，请输入正整数"
            and msg(b3) == "数量无效，请输入正整数"
            and msg(b4) == "已移除"
        )
        return expect(ok, {"hi": b1, "neg": b2, "dec": b3, "zero": b4}, ac_id)

    if ac_id == "PB-B10-AC5":
        SHOTS.mkdir(parents=True, exist_ok=True)
        # ensure clean cart
        reset_ns(env)
        ta = login_customer(env, "b031_buyer_a", "B031-BuyerA-Pass9")
        search_kw = "B031-在售-10"
        js = f"""
const {{ chromium }} = require('{PW_DIR}/node_modules/playwright');
(async () => {{
  const b = await chromium.launch({{ headless: true }});
  const page = await b.newPage();
  try {{
    await page.goto('{fe}/login', {{ waitUntil: 'networkidle' }});
    await page.locator('#username').fill('b031_buyer_a');
    await page.locator('#password').fill('B031-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{ timeout: 15000 }});
    await page.goto('{fe}/', {{ waitUntil: 'networkidle' }});
    const listAdd = await page.getByRole('button', {{ name: /加入购物车/ }}).count();
    await page.screenshot({{ path: '{SHOTS}/b10ac5-list.png', fullPage: true }});
    const search = page.locator('input[aria-label="商品关键词"]');
    await search.fill('{search_kw}');
    await page.waitForTimeout(900);
    await page.waitForLoadState('networkidle');
    const searchAdd = await page.getByRole('button', {{ name: /加入购物车/ }}).count();
    await page.screenshot({{ path: '{SHOTS}/b10ac5-search-results.png', fullPage: true }});
    await page.locator('a[href*="/products/{p['P-ON-10']}"]').first().click();
    await page.waitForURL(u => String(u).includes('/products/{p['P-ON-10']}'), {{ timeout: 10000 }});
    const addBtn = page.getByRole('button', {{ name: /加入购物车/ }});
    await addBtn.waitFor({{ timeout: 10000 }});
    const detailAdd = await addBtn.count();
    const qtyInputs = await page.locator('input[type="number"]').count();
    await page.screenshot({{ path: '{SHOTS}/b10ac5-detail-before-add.png', fullPage: true }});
    await addBtn.click();
    await page.waitForTimeout(900);
    await page.screenshot({{ path: '{SHOTS}/b10ac5-detail-after-add.png', fullPage: true }});
    console.log(JSON.stringify({{ ok:true, listAdd, searchAdd, detailAdd, qtyInputs }}));
  }} catch(e) {{ console.log(JSON.stringify({{ ok:false, error:String(e) }})); }}
  finally {{ await b.close(); }}
}})();
"""
        ui = run_node(js, "ui_b10ac5")
        db_row = cart_db_qty(env, "b031_buyer_a", p["P-ON-10"])
        c_api, b_api = http_json("GET", f"{base}/api/me/cart", headers=auth(ta))
        api_hit = next(
            (i for i in cart_items(b_api) if str(i.get("productId")) == p["P-ON-10"]), None
        )
        qty_ok = (
            db_row is not None
            and str(db_row["quantity"]) == "1"
            and api_hit is not None
            and str(api_hit.get("quantity")) == "1"
        )
        ok = (
            ui.get("ok")
            and ui.get("listAdd", 1) == 0
            and ui.get("searchAdd", 1) == 0
            and ui.get("detailAdd", 0) >= 1
            and qty_ok
        )
        return expect(
            ok,
            {
                "ui": ui,
                "db_row": {
                    "id": str(db_row["id"]) if db_row else None,
                    "quantity": str(db_row["quantity"]) if db_row else None,
                },
                "api_item": api_hit,
                "screenshots": [
                    "evidence/screenshots/b10ac5-list.png",
                    "evidence/screenshots/b10ac5-search-results.png",
                    "evidence/screenshots/b10ac5-detail-before-add.png",
                    "evidence/screenshots/b10ac5-detail-after-add.png",
                ],
                "note": "Each named screenshot captured in this AC step (not reused from B08).",
            },
            ac_id,
            "list/search absence or click-add qty!=1",
        )

    if ac_id == "PB-B10-AC6":
        c1, b1 = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-OFF-M"]}, headers=auth(ta, new_key())
        )
        c2, b2 = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-ZERO"]}, headers=auth(ta, new_key())
        )
        c3, b3 = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-GONE"]}, headers=auth(ta, new_key())
        )
        ok = msg(b1) == "商品已下架" and msg(b2) == "商品已下架" and msg(b3) == "商品不存在"
        return expect(ok, {"off": b1, "zero": b2, "gone": b3}, ac_id)

    if ac_id == "PB-B11-AC1":
        c, b = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-ON-10"]}, headers=auth(ta, new_key())
        )
        cid = (b.get("data") or {}).get("cartItemId")
        http_json("PATCH", f"{base}/api/me/cart/items/{cid}", {"quantity": "3"}, headers=auth(ta))
        http_json("POST", f"{base}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(ts))
        c2, b2 = http_json("GET", f"{base}/api/me/cart", headers=auth(ta))
        hit = next((i for i in cart_items(b2) if str(i.get("cartItemId")) == str(cid)), None)
        offline_ok = hit and str(hit.get("quantity")) == "3" and hit.get("invalidLabel") == "已下架"
        reset_ns(env)
        ta = login_customer(env, "b031_buyer_a", "B031-BuyerA-Pass9")
        ts = login_seller(env)
        http_json(
            "PATCH", f"{base}/api/admin/products/{p['P-ON-10']}", {"stock": "2"}, auth(ts)
        )
        if _product_row(env, p["P-ON-10"])["status"] != "ONLINE":
            http_json("POST", f"{base}/api/admin/products/{p['P-ON-10']}/online", headers=auth(ts))
        c3, b3 = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-ON-10"]}, headers=auth(ta, new_key())
        )
        cid2 = (b3.get("data") or {}).get("cartItemId")
        http_json("PATCH", f"{base}/api/me/cart/items/{cid2}", {"quantity": "3"}, headers=auth(ta))
        c4, b4 = http_json("GET", f"{base}/api/me/cart", headers=auth(ta))
        hit2 = next((i for i in cart_items(b4) if str(i.get("cartItemId")) == str(cid2)), None)
        understock_ok = (
            hit2
            and str(hit2.get("quantity")) == "3"
            and hit2.get("invalidLabel") is None
            and hit2.get("online") is True
        )
        c5, b5 = http_json(
            "POST",
            f"{base}/api/me/checkout/confirmations",
            {"cartItemIds": [str(cid2)]},
            headers=auth(ta, new_key()),
        )
        return expect(
            offline_ok and understock_ok,
            {
                "offline_item": hit,
                "understock_item": hit2,
                "checkout_probe": b5,
            },
            ac_id,
        )

    if ac_id == "PB-B11-AC2":
        c0, b0 = http_json("GET", f"{base}/api/me/cart", headers=auth(ta))
        empty_api = len(cart_items(b0)) == 0
        http_json(
            "POST",
            f"{base}/api/me/cart/items",
            {"productId": p["P-ON-10"]},
            headers=auth(ta, new_key()),
        )
        stock_before = str(_product_row(env, p["P-ON-10"])["stock"])
        js = f"""
const {{ chromium }} = require('{PW_DIR}/node_modules/playwright');
(async () => {{
  const b = await chromium.launch({{ headless: true }});
  const page = await b.newPage();
  try {{
    await page.goto('{fe}/login', {{ waitUntil: 'networkidle' }});
    await page.locator('#username').fill('b031_buyer_a');
    await page.locator('#password').fill('B031-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{ timeout: 15000 }});
    await page.goto('{fe}/me/cart', {{ waitUntil: 'networkidle' }});
    await page.getByRole('button', {{ name: '清空购物车' }}).click();
    await page.locator('.ant-modal-confirm-title').waitFor({{ timeout: 5000 }});
    const title = await page.locator('.ant-modal-confirm-title').innerText();
    await page.locator('.ant-modal-confirm-btns .ant-btn-primary').click();
    await page.getByText('购物车是空的').waitFor({{ timeout: 10000 }});
    // wait for confirm modal to fully close
    await page.locator('.ant-modal-confirm').waitFor({{ state: 'detached', timeout: 5000 }}).catch(() => {{}});
    await page.waitForTimeout(300);
    const emptyVisible = await page.getByText('购物车是空的').isVisible();
    const modalLeft = await page.locator('.ant-modal-confirm').count();
    await page.screenshot({{ path: '{SHOTS}/b11ac2-empty-cart.png', fullPage: true }});
    console.log(JSON.stringify({{ ok:true, title, emptyVisible, modalLeft }}));
  }} catch(e) {{ console.log(JSON.stringify({{ ok:false, error:String(e) }})); }}
  finally {{ await b.close(); }}
}})();
"""
        ui = run_node(js, "ui_b11ac2")
        left = cart_count(env, "b031_buyer_a")
        stock_after = str(_product_row(env, p["P-ON-10"])["stock"])
        ok = (
            empty_api
            and ui.get("ok")
            and ("确定清空购物车" in str(ui.get("title", "")))
            and ui.get("emptyVisible") is True
            and ui.get("modalLeft", 1) == 0
            and left == 0
            and stock_before == stock_after
        )
        return expect(
            ok,
            {
                "empty_api": b0,
                "ui": ui,
                "stock": [stock_before, stock_after],
                "screenshots": ["evidence/screenshots/b11ac2-empty-cart.png"],
            },
            ac_id,
        )

    if ac_id == "PB-B11-AC3":
        http_json(
            "POST",
            f"{base}/api/me/cart/items",
            {"productId": p["P-ON-10"]},
            headers=auth(ta, new_key()),
        )
        ta2 = login_customer(env, "b031_buyer_a", "B031-BuyerA-Pass9")
        c_s1, b_s1 = http_json("GET", f"{base}/api/me/cart", headers=auth(ta))
        c_s2, b_s2 = http_json("GET", f"{base}/api/me/cart", headers=auth(ta2))
        dual = any(str(i.get("productId")) == p["P-ON-10"] for i in cart_items(b_s1)) and any(
            str(i.get("productId")) == p["P-ON-10"] for i in cart_items(b_s2)
        )
        js = f"""
const {{ chromium }} = require('{PW_DIR}/node_modules/playwright');
(async () => {{
  const b = await chromium.launch({{ headless: true }});
  const page = await b.newPage();
  try {{
    await page.goto('{fe}/login', {{ waitUntil: 'networkidle' }});
    await page.locator('#username').fill('b031_buyer_a');
    await page.locator('#password').fill('B031-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{ timeout: 15000 }});
    await page.goto('{fe}/me/cart', {{ waitUntil: 'networkidle' }});
    const before = await page.locator('.ant-card-small').count();
    await page.reload({{ waitUntil: 'networkidle' }});
    const afterRefresh = await page.locator('.ant-card-small').count();
    await page.goto('{fe}/', {{ waitUntil: 'networkidle' }});
    await page.getByRole('button', {{ name: '退出登录' }}).click();
    await page.waitForTimeout(500);
    await page.goto('{fe}/login', {{ waitUntil: 'networkidle' }});
    await page.locator('#username').fill('b031_buyer_a');
    await page.locator('#password').fill('B031-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => !String(u).includes('/login'), {{ timeout: 15000 }});
    await page.goto('{fe}/me/cart', {{ waitUntil: 'networkidle' }});
    const afterRelogin = await page.locator('.ant-card-small').count();
    console.log(JSON.stringify({{ ok:true, before, afterRefresh, afterRelogin }}));
  }} catch(e) {{ console.log(JSON.stringify({{ ok:false, error:String(e) }})); }}
  finally {{ await b.close(); }}
}})();
"""
        ui = run_node(js, "ui_b11ac3_refresh")
        proof = fx.get("_restart_proof")
        if proof is None and RESTART_PROOF_PATH.exists():
            proof = json.loads(RESTART_PROOF_PATH.read_text(encoding="utf-8"))
        if not proof or not proof.get("feasible"):
            return result(
                ac_id,
                "BLOCKED",
                {
                    "dual": dual,
                    "ui_refresh_logout": ui,
                    "restart_proof": proof,
                    "reason": "shared genuine restart proof missing/infeasible (see B09AC5)",
                },
            )
        # Re-verify cart still present after the earlier shared restart (seeded again above for dual/UI).
        # The persistence claim for cart across restart is taken from shared proof.cart_persisted.
        ok = (
            dual
            and ui.get("ok")
            and ui.get("afterRefresh", 0) >= 1
            and ui.get("afterRelogin", 0) >= 1
            and proof.get("feasible")
            and proof.get("cart_persisted")
            and proof.get("downtime_observed")
            and proof.get("pid_changed")
        )
        return expect(
            ok,
            {
                "dual_session_payloads": {
                    "s1_items": len(cart_items(b_s1)),
                    "s2_items": len(cart_items(b_s2)),
                    "dual": dual,
                },
                "ui_refresh_logout": ui,
                "shared_restart_proof": proof,
                "restart_proof_path": "evidence/restart-proof.json",
                "note": "Single genuine BE restart executed in PB-B09-AC5; cart persistence proven there and referenced here.",
            },
            ac_id,
            "dual/refresh/shared-restart cart persistence",
        )

    if ac_id == "PB-B11-AC4":
        c, b = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-ON-10"]}, headers=auth(ta, new_key())
        )
        cid = (b.get("data") or {}).get("cartItemId")
        barrier = threading.Barrier(2)
        box = {}

        def early_2():
            barrier.wait()
            code, body = http_json(
                "PATCH", f"{base}/api/me/cart/items/{cid}", {"quantity": "2"}, headers=auth(ta)
            )
            box["early"] = {"http": code, "body": body, "t": time.time(), "message": msg(body)}

        def late_9():
            barrier.wait()
            time.sleep(0.2)
            code, body = http_json(
                "PATCH", f"{base}/api/me/cart/items/{cid}", {"quantity": "9"}, headers=auth(ta)
            )
            box["late"] = {"http": code, "body": body, "t": time.time(), "message": msg(body)}

        t1 = threading.Thread(target=early_2)
        t2 = threading.Thread(target=late_9)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        c2, b2 = http_json("GET", f"{base}/api/me/cart", headers=auth(ta))
        hit = next((i for i in cart_items(b2) if str(i.get("cartItemId")) == str(cid)), None)
        db_after_qty = cart_db_qty(env, "b031_buyer_a", p["P-ON-10"])
        lines = cart_count(env, "b031_buyer_a", p["P-ON-10"])
        qty_ok = (
            hit is not None
            and str(hit.get("quantity")) == "9"
            and lines == 1
            and db_after_qty is not None
            and str(db_after_qty["quantity"]) == "9"
            and box.get("late", {}).get("t", 0) >= box.get("early", {}).get("t", 0)
        )

        barrier2 = threading.Barrier(2)
        box2 = {}

        def patch_5():
            barrier2.wait()
            code, body = http_json(
                "PATCH", f"{base}/api/me/cart/items/{cid}", {"quantity": "5"}, headers=auth(ta)
            )
            box2["patch"] = {"http": code, "body": body, "t": time.time(), "message": msg(body)}

        def del_later():
            barrier2.wait()
            time.sleep(0.2)
            code, body = http_json(
                "DELETE", f"{base}/api/me/cart/items/{cid}", headers=auth(ta)
            )
            box2["del"] = {"http": code, "body": body, "t": time.time(), "message": msg(body)}

        th1 = threading.Thread(target=patch_5)
        th2 = threading.Thread(target=del_later)
        th1.start()
        th2.start()
        th1.join()
        th2.join()
        lines2 = cart_count(env, "b031_buyer_a", p["P-ON-10"])
        db_after_del = cart_db_qty(env, "b031_buyer_a", p["P-ON-10"])
        delete_last_ok = (
            lines2 == 0
            and db_after_del is None
            and box2.get("del", {}).get("t", 0) >= box2.get("patch", {}).get("t", 0)
        )
        ok = qty_ok and delete_last_ok
        return expect(
            ok,
            {
                "concurrent_qty": box,
                "final_qty_api": (hit or {}).get("quantity"),
                "final_qty_db": str(db_after_qty["quantity"]) if db_after_qty else None,
                "lines_after_qty": lines,
                "completion_order_qty": "late_9_after_early_2",
                "delete_race": box2,
                "lines_after_delete": lines2,
                "db_after_delete": db_after_del,
                "completion_order_delete": "delete_after_patch",
            },
            ac_id,
        )

    if ac_id == "PB-B11-AC5":
        c, b = http_json(
            "POST", f"{base}/api/me/cart/items", {"productId": p["P-ON-10"]}, headers=auth(ta, new_key())
        )
        cid = (b.get("data") or {}).get("cartItemId")
        http_json("DELETE", f"{base}/api/me/cart/items/{cid}", headers=auth(ta))
        c2, b2 = http_json(
            "PATCH", f"{base}/api/me/cart/items/{cid}", {"quantity": "2"}, headers=auth(ta)
        )
        lines = cart_count(env, "b031_buyer_a", p["P-ON-10"])
        stock = str(_product_row(env, p["P-ON-10"])["stock"])
        ok = msg(b2) == "该商品已不在购物车，请刷新页面后查看。" and lines == 0 and stock == "10"
        return expect(ok, {"patch": b2, "lines": lines, "stock": stock}, ac_id)

    return result(ac_id, "BLOCKED", {"reason": "no runner for ac"})


def main() -> int:
    EVID.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    if RESTART_PROOF_PATH.exists():
        RESTART_PROOF_PATH.unlink()
    env = load_env()
    window = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sut_sha": env.get("B031_SUT_SHA"),
        "db": env.get("B031_DB_NAME"),
    }
    print("preparing…", flush=True)
    fx = prepare(env)
    print("fixtures ready", fx["products"], flush=True)
    acs = json.loads((ROOT / "acs-21.json").read_text(encoding="utf-8"))
    results = []
    for ac in acs:
        ac_id = ac["ac_id"]
        print("running", ac_id, flush=True)
        try:
            r = run_ac(env, fx, ac_id)
        except Exception as e:
            r = result(ac_id, "FAIL", {"exception": str(e)})
        results.append({**r, "criteria": ac["criteria"], "pb_id": ac["pb_id"]})
        print(" ", r["verdict"], flush=True)

    window["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    summary = {
        "execution_window": window,
        "sut_sha": env.get("B031_SUT_SHA"),
        "sut_branch": env.get("B031_SUT_BRANCH"),
        "db": env.get("B031_DB_NAME"),
        "base": base_url(env),
        "fe": fe_url(env),
        "total": len(results),
        "pass": sum(1 for r in results if r["verdict"] == "PASS"),
        "fail": sum(1 for r in results if r["verdict"] == "FAIL"),
        "blocked": sum(1 for r in results if r["verdict"] == "BLOCKED"),
        "results": results,
    }
    (EVID / "results.json").write_text(
        json.dumps(redact(summary), ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    lines = [
        "# B-031 21 AC 执行结果（统一单次执行）",
        "",
        f"- 执行窗口：`{window['started_at']}` → `{window['ended_at']}`",
        f"- SUT：`{summary['sut_branch']}@{summary['sut_sha']}`",
        f"- DB：`{summary['db']}` · BE：`{summary['base']}` · FE：`{summary['fe']}`",
        f"- PASS {summary['pass']} / FAIL {summary['fail']} / BLOCKED {summary['blocked']} / TOTAL {summary['total']}",
        "",
        "| AC | 结论 | 摘要 |",
        "|---|---|---|",
    ]
    for r in results:
        d = r.get("detail") or {}
        brief = d.get("fail_reason") or d.get("exception") or d.get("reason") or r["verdict"]
        if r["verdict"] == "PASS":
            brief = "符合预期"
        lines.append(f"| {r['ac_id']} | **{r['verdict']}** | {brief} |")
    lines.append("")
    (EVID / "results.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("pass", "fail", "blocked", "total")}, indent=2))
    return 0 if summary["blocked"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
