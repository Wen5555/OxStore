#!/usr/bin/env python3
"""B-031: prepare fixtures + execute PB-B08/09/10/11 (21 ACs) in ONE unified run."""
from __future__ import annotations

import json
import mimetypes
import os
import signal
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


def db_update_product_live(env, pid: str, name: str, price: str, image_path: str | None = None):
    """Admin publish-after API only allows stock/category; live name/price/image via DB for AC binding proof."""
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE product SET name=%s, price=%s WHERE id=%s", (name, price, pid))
            if image_path:
                cur.execute("SELECT id FROM product_image WHERE product_id=%s ORDER BY id LIMIT 1", (pid,))
                row = cur.fetchone()
                if row:
                    cur.execute(
                        "UPDATE product_image SET image_path=%s WHERE id=%s",
                        (image_path, row["id"]),
                    )
    finally:
        conn.close()


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
    return {**out, "tokens": {"A": ta, "B": tb, "S": seller}}


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
            # restore the four canonical fixture products by exact name / drifted live names
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


def wait_be(env, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        code, body = http_json(
            "POST",
            f"{base_url(env)}/api/admin/auth/login",
            {"username": "admin", "password": env.get("B031_SELLER_PASSWORD")},
        )
        if code == 200:
            return True
        time.sleep(1.5)
    return False


def restart_backend(env: dict) -> dict:
    """Kill ShopApplication + maven wrapper; relaunch spring-boot:run with same isolated DB."""
    be = load_be_env()
    info = {"killed": [], "started": False}
    for pat in ("com.team.shop.ShopApplication", "spring-boot:run"):
        try:
            out = subprocess.check_output(["pgrep", "-f", pat], text=True).strip().split()
        except subprocess.CalledProcessError:
            out = []
        for pid in out:
            try:
                os.kill(int(pid), signal.SIGTERM)
                info["killed"].append(pid)
            except ProcessLookupError:
                pass
    time.sleep(2)
    for pid in list(info["killed"]):
        try:
            os.kill(int(pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
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
    log = open("/tmp/b031-backend-restart.log", "a", encoding="utf-8")
    proc = subprocess.Popen(
        ["./mvnw", "-q", "-DskipTests", "spring-boot:run"],
        cwd=BE_DIR,
        env=envp,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    info["pid"] = proc.pid
    info["started"] = wait_be(env, timeout=120)
    info["db"] = envp["DB_NAME"]
    return info


# ---------- AC implementations ----------


def run_ac(env, fx, ac_id: str) -> dict:
    ta, tb, ts = fx["tokens"]["A"], fx["tokens"]["B"], fx["tokens"]["S"]
    p = fx["products"]
    base = base_url(env)
    fe = fe_url(env)
    reset_ns(env)
    # refresh tokens after possible prior restart in earlier AC
    try:
        ta = login_customer(env, "b031_buyer_a", "B031-BuyerA-Pass9")
        tb = login_customer(env, "b031_buyer_b", "B031-BuyerB-Pass9")
        ts = login_seller(env)
        fx["tokens"] = {"A": ta, "B": tb, "S": ts}
    except Exception as e:
        return result(ac_id, "FAIL", {"exception": f"relogin: {e}"})

    if ac_id == "PB-B08-AC1":
        c1, b1 = http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}")
        c2, b2 = http_json(
            "PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth("invalid.token.value")
        )
        c3, b3 = http_json(
            "PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ts)
        )
        c4, b4 = http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        before = fav_count(env, "b031_buyer_a", p["P-ON-10"])
        # B tries to cancel A's product favorite (own namespace) — A's row must stay
        c5, b5 = http_json(
            "DELETE", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(tb)
        )
        after_b_del = fav_count(env, "b031_buyer_a", p["P-ON-10"])
        # Cross-user via move-to-favorites with A's cart line under B token → 无权操作
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
        c7, b7 = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(tb))
        foreign = [i for i in fav_items(b7) if str(i.get("productId")) == p["P-ON-10"]]
        seller_ok = msg(b3) == "无此权限"
        cross_ok = msg(b6) == "无权操作" and after_b_del == before == 1 and len(foreign) == 0
        basic = (
            msg(b1) == "请先登录"
            and msg(b2) == "请重新登录"
            and msg(b4) == "已收藏"
            and c4 == 200
        )
        # FE: login return does not auto-favorite (optional practical check)
        js = f"""
const {{ chromium }} = require('{PW_DIR}/node_modules/playwright');
(async () => {{
  const b = await chromium.launch({{ headless: true }});
  const page = await b.newPage();
  const msgs = [];
  page.on('console', () => {{}});
  try {{
    await page.goto('{fe}/products/{p['P-ON-10']}', {{ waitUntil: 'networkidle' }});
    await page.getByRole('button', {{ name: /收\\s*藏/ }}).click();
    await page.waitForURL(u => String(u).includes('/login'), {{ timeout: 10000 }});
    await page.locator('#username').fill('b031_buyer_a');
    await page.locator('#password').fill('B031-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(u => String(u).includes('/products/'), {{ timeout: 15000 }});
    await page.waitForTimeout(800);
    const toastAuto = await page.getByText('已收藏').count();
    const btn = await page.getByRole('button', {{ name: /收\\s*藏|取消\\s*收\\s*藏/ }}).innerText();
    console.log(JSON.stringify({{ ok:true, toastAuto, btn, url: page.url() }}));
  }} catch(e) {{ console.log(JSON.stringify({{ ok:false, error:String(e) }})); }}
  finally {{ await b.close(); }}
}})();
"""
        ui = run_node(js, "ui_b08ac1_noredo")
        # After login return, button may already show 取消收藏 if prior API favorite exists — check no NEW auto toast from click-less redo.
        # Clear A favorite first for cleaner UI? Already favorited via API. Re-reset for UI:
        detail = {
            "unauth": b1,
            "invalid_auth": b2,
            "seller": b3,
            "ok": b4,
            "b_delete": b5,
            "cross_move": b6,
            "b_list": b7,
            "a_fav_count_before_after": [before, after_b_del],
            "expected_seller_message": "无此权限",
            "actual_seller_message": msg(b3),
            "ui_no_autoredo": ui,
            "gap1": {
                "cross_user_无权操作": msg(b6) == "无权操作",
                "a_data_unchanged": after_b_del == 1,
            },
        }
        if not (basic and cross_ok and seller_ok):
            reasons = []
            if not seller_ok:
                reasons.append(
                    f"商家访问期望「无此权限」，实得「{msg(b3)}」/code={code_of(b3)}"
                )
            if not cross_ok:
                reasons.append(f"越权期望「无权操作」实得「{msg(b6)}」或A数据被改")
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
    await page.goto('{fe}/products/{p['P-ON-10']}', {{ waitUntil: 'networkidle' }});
    const unfav = await page.getByRole('button', {{ name: /^收\\s*藏$/ }}).count();
    await page.screenshot({{ path: '{SHOTS}/b08ac5-detail-unfavorited.png', fullPage: true }});
    await page.getByRole('button', {{ name: /^收\\s*藏$/ }}).click();
    await page.waitForTimeout(600);
    const fav = await page.getByRole('button', {{ name: /取消\\s*收\\s*藏/ }}).count();
    await page.screenshot({{ path: '{SHOTS}/b08ac5-detail-favorited.png', fullPage: true }});
    console.log(JSON.stringify({{ ok:true, listFav, unfav, fav }}));
  }} catch(e) {{ console.log(JSON.stringify({{ ok:false, error:String(e) }})); }}
  finally {{ await b.close(); }}
}})();
"""
        ui = run_node(js, "ui_b08ac5")
        shots = [
            "evidence/screenshots/b08ac5-list-logged-in.png",
            "evidence/screenshots/b08ac5-detail-unfavorited.png",
            "evidence/screenshots/b08ac5-detail-favorited.png",
        ]
        ok = ui.get("ok") and ui.get("listFav", 1) == 0 and ui.get("unfav", 0) >= 1 and ui.get("fav", 0) >= 1
        return expect(ok, {"ui": ui, "screenshots": shots, "gap2": True}, ac_id, "UI entrance/state")

    if ac_id == "PB-B09-AC1":
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        http_json("POST", f"{base}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(ts))
        c, b = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
        hit = next((i for i in fav_items(b) if str(i.get("productId")) == p["P-ON-10"]), None)
        retained = hit and hit.get("invalidLabel") == "已下架" and hit.get("valid") is False
        # UI while still favorited+offline: no buyable link; shows 已下架
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
    const label = await page.getByText('已下架').count();
    const links = await page.locator('a[href*="/products/{p['P-ON-10']}"]').count();
    await page.screenshot({{ path: '{SHOTS}/b09ac1-offline-favorite.png', fullPage: true }});
    console.log(JSON.stringify({{ ok:true, label, buyableLinks: links }}));
  }} catch(e) {{ console.log(JSON.stringify({{ ok:false, error:String(e) }})); }}
  finally {{ await b.close(); }}
}})();
"""
        ui = run_node(js, "ui_b09ac1")
        c_can, b_can = http_json(
            "DELETE", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta)
        )
        cancellable = msg(b_can) == "已取消收藏"
        # re-online + re-favorite → label clears
        http_json("POST", f"{base}/api/admin/products/{p['P-ON-10']}/online", headers=auth(ts))
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        c2, b2 = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
        hit2 = next((i for i in fav_items(b2) if str(i.get("productId")) == p["P-ON-10"]), None)
        cleared = hit2 and hit2.get("valid") is True and hit2.get("invalidLabel") is None
        # offline again then republish as NEW product — old fav stays on old id
        http_json("POST", f"{base}/api/admin/products/{p['P-ON-10']}/offline", headers=auth(ts))
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
        c3, b3 = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
        hit3 = next((i for i in fav_items(b3) if str(i.get("productId")) == p["P-ON-10"]), None)
        no_auto_move = (
            hit3
            and hit3.get("invalidLabel") == "已下架"
            and str(hit3.get("productId")) != new_pid
            and not any(str(i.get("productId")) == new_pid for i in fav_items(b3))
        )
        ok = (
            retained
            and cancellable
            and ui.get("label", 0) >= 1
            and ui.get("buyableLinks", 1) == 0
            and cleared
            and no_auto_move
            and http in (200, 201)
        )
        return expect(
            ok,
            {
                "hit_offline": hit,
                "cancel": b_can,
                "ui": ui,
                "hit_reonline": hit2,
                "new_pid": new_pid,
                "hit_after_republish": hit3,
                "screenshots": ["evidence/screenshots/b09ac1-offline-favorite.png"],
                "gap3": True,
            },
            ac_id,
            "offline retain/relist/republish",
        )

    if ac_id == "PB-B09-AC2":
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-5']}", headers=auth(ta))
        c0, b0 = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
        before = next((i for i in fav_items(b0) if str(i.get("productId")) == p["P-ON-5"]), None)
        new_name = "B031-在售-5-LIVE"
        new_price = "18.88"
        # change live fields (publish API cannot rename; DB update simulates merchant catalog change)
        db_update_product_live(env, p["P-ON-5"], new_name, new_price, image_path="uploads/b031-live.png")
        c, b = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
        hit = next((i for i in fav_items(b) if str(i.get("productId")) == p["P-ON-5"]), None)
        ok = (
            hit is not None
            and hit.get("productName") == new_name
            and str(hit.get("unitPrice")) == new_price
            and hit.get("mainImageUrl") is not None
            and hit.get("productName") != (before or {}).get("productName")
        )
        # restore name for later ACs
        db_update_product_live(env, p["P-ON-5"], "B031-在售-5", "8.00")
        return expect(ok, {"before": before, "after": hit, "gap4": True}, ac_id)

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
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        time.sleep(0.05)
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-5']}", headers=auth(ta))
        http_json("DELETE", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        time.sleep(0.05)
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        c, b = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta))
        items = fav_items(b)
        ids = [str(i.get("productId")) for i in items]
        order_ok = len(ids) >= 2 and ids[0] == p["P-ON-10"]
        size_ok = ((b or {}).get("data") or {}).get("size") == 10
        ok = ui.get("emptyText", 0) >= 1 and order_ok and size_ok
        return expect(
            ok,
            {
                "ui": ui,
                "ids": ids,
                "screenshots": ["evidence/screenshots/b09ac4-empty-favorites.png"],
                "gap5": True,
            },
            ac_id,
        )

    if ac_id == "PB-B09-AC5":
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta))
        ta2 = login_customer(env, "b031_buyer_a", "B031-BuyerA-Pass9")
        c, b = http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta2))
        dual = any(str(i.get("productId")) == p["P-ON-10"] for i in fav_items(b))
        # concurrent favorite+cancel barrier — last write wins, unique row
        reset_ns(env)
        barrier = threading.Barrier(2)
        box = {}

        def put_then():
            barrier.wait()
            code, body = http_json(
                "PUT", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta)
            )
            box["put"] = {"http": code, "body": body, "t": time.time()}

        def del_later():
            barrier.wait()
            time.sleep(0.15)
            code, body = http_json(
                "DELETE", f"{base}/api/me/favorites/{p['P-ON-10']}", headers=auth(ta)
            )
            box["del"] = {"http": code, "body": body, "t": time.time()}

        t1 = threading.Thread(target=put_then)
        t2 = threading.Thread(target=del_later)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        final_cnt = fav_count(env, "b031_buyer_a", p["P-ON-10"])
        # last writer is delete → 0 rows
        concurrent_ok = final_cnt == 0 and box.get("del", {}).get("t", 0) >= box.get("put", {}).get("t", 0)
        # service restart persistence
        http_json("PUT", f"{base}/api/me/favorites/{p['P-ON-5']}", headers=auth(ta))
        rst = restart_backend(env)
        ta3 = login_customer(env, "b031_buyer_a", "B031-BuyerA-Pass9") if rst.get("started") else None
        c3, b3 = (
            http_json("GET", f"{base}/api/me/favorites?page=1", headers=auth(ta3))
            if ta3
            else (0, None)
        )
        after_restart = any(str(i.get("productId")) == p["P-ON-5"] for i in fav_items(b3))
        # refresh tokens in fx after restart
        if rst.get("started"):
            fx["tokens"]["A"] = ta3
            fx["tokens"]["B"] = login_customer(env, "b031_buyer_b", "B031-BuyerB-Pass9")
            fx["tokens"]["S"] = login_seller(env)
        ok = dual and concurrent_ok and rst.get("started") and after_restart
        return expect(
            ok,
            {
                "dual_session": dual,
                "concurrent": box,
                "final_cnt": final_cnt,
                "restart": rst,
                "after_restart": after_restart,
                "gap6": True,
            },
            ac_id,
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
        # seller cannot add into customer cart via /api/me/cart
        c5, b5 = http_json(
            "POST",
            f"{base}/api/me/cart/items",
            {"productId": p["P-ON-5"]},
            headers=auth(ts, new_key()),
        )
        ok = (
            msg(b1) == "请先登录"
            and msg(b2) == "请重新登录"
            and msg(b3) == "已加入购物车"
            and msg(b4) == "无权操作"
            and before == after == 1
            and msg(b5) in ("无此权限", "角色无权访问", "请先登录")
        )
        return expect(
            ok,
            {
                "unauth": b1,
                "bad": b2,
                "ok": b3,
                "cross": b4,
                "seller_add": b5,
                "gap7": True,
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
    await page.goto('{fe}/products/{p['P-ON-10']}', {{ waitUntil: 'networkidle' }});
    const detailAdd = await page.getByRole('button', {{ name: /加入购物车/ }}).count();
    const qtyInputs = await page.locator('input[type="number"]').count();
    await page.screenshot({{ path: '{SHOTS}/b10ac5-detail.png', fullPage: true }});
    console.log(JSON.stringify({{ ok:true, listAdd, detailAdd, qtyInputs }}));
  }} catch(e) {{ console.log(JSON.stringify({{ ok:false, error:String(e) }})); }}
  finally {{ await b.close(); }}
}})();
"""
        ui = run_node(js, "ui_b10ac5")
        ok = ui.get("ok") and ui.get("listAdd", 1) == 0 and ui.get("detailAdd", 0) >= 1
        return expect(
            ok,
            {
                "ui": ui,
                "screenshots": [
                    "evidence/screenshots/b10ac5-list.png",
                    "evidence/screenshots/b10ac5-detail.png",
                ],
                "gap8": True,
            },
            ac_id,
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
        # restore online with stock 2 < qty 3
        http_json("POST", f"{base}/api/admin/products/{p['P-ON-10']}/online", headers=auth(ts))
        http_json(
            "PATCH", f"{base}/api/admin/products/{p['P-ON-10']}", {"stock": "2"}, auth(ts)
        )
        # re-add fresh line for understock case
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
        # optional checkout confirmation reject for inventory
        c5, b5 = http_json(
            "POST",
            f"{base}/api/me/checkout/confirmations",
            {"cartItemIds": [str(cid2)]},
            headers=auth(ta, new_key()),
        )
        # message may vary; accept conflict/insufficient as evidence if present
        return expect(
            offline_ok and understock_ok,
            {
                "offline_item": hit,
                "understock_item": hit2,
                "checkout_probe": b5,
                "gap9": True,
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
    await page.screenshot({{ path: '{SHOTS}/b11ac2-empty-cart.png', fullPage: true }});
    console.log(JSON.stringify({{ ok:true, title, empty: true }}));
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
                "gap10": True,
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
        c, b = http_json("GET", f"{base}/api/me/cart", headers=auth(ta2))
        dual = any(str(i.get("productId")) == p["P-ON-10"] for i in cart_items(b))
        rst = restart_backend(env)
        ta3 = login_customer(env, "b031_buyer_a", "B031-BuyerA-Pass9") if rst.get("started") else None
        c3, b3 = http_json("GET", f"{base}/api/me/cart", headers=auth(ta3)) if ta3 else (0, None)
        after = any(str(i.get("productId")) == p["P-ON-10"] for i in cart_items(b3))
        if rst.get("started"):
            fx["tokens"]["A"] = ta3
            fx["tokens"]["B"] = login_customer(env, "b031_buyer_b", "B031-BuyerB-Pass9")
            fx["tokens"]["S"] = login_seller(env)
        ok = dual and rst.get("started") and after
        return expect(ok, {"dual": dual, "restart": rst, "after": after, "gap11": True}, ac_id)

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
            box["early"] = {"http": code, "body": body, "t": time.time()}

        def late_9():
            barrier.wait()
            time.sleep(0.2)
            code, body = http_json(
                "PATCH", f"{base}/api/me/cart/items/{cid}", {"quantity": "9"}, headers=auth(ta)
            )
            box["late"] = {"http": code, "body": body, "t": time.time()}

        t1 = threading.Thread(target=early_2)
        t2 = threading.Thread(target=late_9)
        t1.start(); t2.start(); t1.join(); t2.join()
        c2, b2 = http_json("GET", f"{base}/api/me/cart", headers=auth(ta))
        hit = next((i for i in cart_items(b2) if str(i.get("cartItemId")) == str(cid)), None)
        lines = cart_count(env, "b031_buyer_a", p["P-ON-10"])
        qty_ok = hit is not None and str(hit.get("quantity")) == "9" and lines == 1

        barrier2 = threading.Barrier(2)
        box2 = {}

        def patch_5():
            barrier2.wait()
            code, body = http_json(
                "PATCH", f"{base}/api/me/cart/items/{cid}", {"quantity": "5"}, headers=auth(ta)
            )
            box2["patch"] = {"http": code, "body": body, "t": time.time()}

        def del_later():
            barrier2.wait()
            time.sleep(0.2)
            code, body = http_json(
                "DELETE", f"{base}/api/me/cart/items/{cid}", headers=auth(ta)
            )
            box2["del"] = {"http": code, "body": body, "t": time.time()}

        th1 = threading.Thread(target=patch_5)
        th2 = threading.Thread(target=del_later)
        th1.start(); th2.start(); th1.join(); th2.join()
        lines2 = cart_count(env, "b031_buyer_a", p["P-ON-10"])
        delete_last_ok = lines2 == 0 and box2.get("del", {}).get("t", 0) >= box2.get("patch", {}).get("t", 0)
        ok = qty_ok and delete_last_ok
        return expect(
            ok,
            {
                "concurrent_qty": box,
                "final_qty": (hit or {}).get("quantity"),
                "lines_after_qty": lines,
                "delete_race": box2,
                "lines_after_delete": lines2,
                "gap12": True,
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
        brief = d.get("fail_reason") or d.get("exception") or r["verdict"]
        if r["verdict"] == "PASS":
            brief = "符合预期"
        lines.append(f"| {r['ac_id']} | **{r['verdict']}** | {brief} |")
    lines.append("")
    (EVID / "results.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("pass", "fail", "blocked", "total")}, indent=2))
    return 0 if summary["blocked"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
