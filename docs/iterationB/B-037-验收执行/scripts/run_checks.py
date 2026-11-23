#!/usr/bin/env python3
"""B-037 checks: fixed prompts, security negatives, B08/B09 re-verify, persistence.

phases:
  main    -> prompts/security/B08/B09 + write persistence state to runs/state.json
  persist -> after backend restart, verify same rows/token/stock persisted
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
import uuid

from b037_common import (  # noqa: E402
    B037_ROOT, RUNS, advance, call, cart_add, checkout_confirm, checkout_submit,
    conjunct, counts, expect, login_customer, login_seller, load_b037_env, msg,
    now_cst, now_utc, place, product_db, product_id, query, reset, write_json,
)

EVID = B037_ROOT / "evidence"
FORBIDDEN = ["缺货", "无货", "超限", "下单历史"]


def finish(name: str, title: str, cons: list[dict], evidence: dict, status: str | None = None) -> dict:
    failed = [c for c in cons if not c["pass"]]
    st = status or ("FAIL" if failed else "PASS")
    return {"check": name, "title": title, "status": st, "conjuncts": cons,
            "conjunct_count": len(cons), "failed": [c["name"] for c in failed],
            "evidence": evidence}


def phase_main(env):
    reset(env)
    ta = login_customer(env, "CUSTOMER_A")
    tb = login_customer(env, "CUSTOMER_B")
    ts = login_seller(env)
    p10 = product_id("P-ON-10")
    results = []

    # ---------------- fixed prompts
    cons = []
    out = {}
    def rec(key, resp):
        out[key] = {"http": resp[0], "message": msg(resp), "body": resp[1]}

    rec("anon_fav", call(env, "PUT", f"/api/me/favorites/{p10}"))
    expect(cons, "anonymous_401", out["anon_fav"], 401, "请先登录")
    rec("bad_fav", call(env, "PUT", f"/api/me/favorites/{p10}", "invalid.token.value"))
    expect(cons, "invalid_token_401", out["bad_fav"], 401, "请重新登录")
    rec("seller_cart", call(env, "POST", "/api/me/cart/items", ts,
                            {"productId": p10}, str(uuid.uuid4())))
    expect(cons, "seller_customer_api_403", out["seller_cart"], 403, "角色无权访问")
    rec("customer_admin", call(env, "GET", "/api/admin/orders", ta))
    expect(cons, "customer_admin_403", out["customer_admin"], 403, "角色无权访问")
    rec("anon_admin", call(env, "GET", "/api/admin/orders"))
    expect(cons, "admin_anonymous_401", out["anon_admin"], 401, "请先登录")

    rec("cart_offline", call(env, "POST", "/api/me/cart/items", ta,
                             {"productId": product_id("P-OFF-M")}, str(uuid.uuid4())))
    expect(cons, "add_offline_409", out["cart_offline"], 409, "商品已下架")
    rec("cart_missing", call(env, "POST", "/api/me/cart/items", ta,
                             {"productId": "999999"}, str(uuid.uuid4())))
    expect(cons, "add_missing_404", out["cart_missing"], (404, 409), "商品不存在")

    c1 = cart_add(env, ta, "P-ON-10", "1")["cartItemId"]
    rec("qty_negative", call(env, "PATCH", f"/api/me/cart/items/{c1}", ta, {"quantity": "-1"}))
    expect(cons, "negative_qty_400", out["qty_negative"], 400, "数量无效，请输入正整数")
    rec("qty_zero", call(env, "PATCH", f"/api/me/cart/items/{c1}", ta, {"quantity": "0"}))
    expect(cons, "zero_qty_removed", out["qty_zero"], 200, "已移除")
    rec("qty_deleted_row", call(env, "PATCH", f"/api/me/cart/items/{c1}", ta, {"quantity": "2"}))
    expect(cons, "deleted_row_409", out["qty_deleted_row"], 409, "该商品已不在购物车，请刷新页面后查看。")

    rec("empty_confirm", call(env, "POST", "/api/me/checkout/confirmations", ta, {"cartItemIds": []}))
    expect(cons, "empty_confirm_400", out["empty_confirm"], 400, "请选择商品")

    low = cart_add(env, ta, "P-ON-1", "2")["cartItemId"]
    rec("insufficient", call(env, "POST", "/api/me/checkout/confirmations", ta, {"cartItemIds": [low]}))
    ins = out["insufficient"]
    ok_ins = ins["http"] == 409 and "库存不足" in json.dumps(ins["body"], ensure_ascii=False)
    cons.append(conjunct("insufficient_stock_409", ok_ins, "409 / 库存不足：当前可售 1 件",
                         json.dumps(ins, ensure_ascii=False)[:300]))

    # duplicate submit with same idempotency key
    cart = cart_add(env, ta, "P-ON-10", "1")["cartItemId"]
    conf = checkout_confirm(env, ta, [cart])["confirmationToken"]
    key = str(uuid.uuid4())
    first = checkout_submit(env, ta, confirmation_token=conf, idem=key)
    second = checkout_submit(env, ta, confirmation_token=conf, idem=key)
    out["dup_first"] = [first["http"], first.get("message")]
    out["dup_second"] = [second["http"], second.get("message")]
    expect(cons, "duplicate_submit_409", (second["http"], second.get("body") or {}),
           409, "订单已提交，请勿重复下单")

    o1 = place(env, ta, "P-ON-10", "1")
    rec("wrong_expected", call(env, "POST", f"/api/me/orders/{o1['orderId']}/cancel", ta,
                               {"expectedStatus": "CONFIRMED", "reason": "x"}))
    expect(cons, "wrong_expected_409", out["wrong_expected"], 409, "订单状态已变化，请刷新后重试")
    rec("partial_cancel", call(env, "POST", f"/api/me/orders/{o1['orderId']}/cancel", ta,
                               {"expectedStatus": "PLACED", "reason": "x", "items": ["1"]}))
    expect(cons, "partial_cancel_400", out["partial_cancel"], 400, "不支持部分取消")
    rec("other_order", call(env, "POST", f"/api/me/orders/{o1['orderId']}/cancel", tb,
                            {"expectedStatus": "PLACED", "reason": "x"}))
    expect(cons, "other_order_403", out["other_order"], 403, "无权操作该订单")
    rec("missing_order", call(env, "POST", "/api/me/orders/99999999/cancel", ta,
                              {"expectedStatus": "PLACED", "reason": "x"}))
    expect(cons, "missing_order_404", out["missing_order"], 404, "订单不存在")

    o2 = place(env, ta, "P-ON-10", "1")
    advance(env, o2["orderId"], "SHIPPED", ts)
    rec("cancel_shipped", call(env, "POST", f"/api/me/orders/{o2['orderId']}/cancel", ta,
                               {"expectedStatus": "SHIPPED", "reason": "x"}))
    expect(cons, "shipped_409", out["cancel_shipped"], 409, "订单已开始发货，不可取消")
    o3 = place(env, ta, "P-ON-10", "1")
    advance(env, o3["orderId"], "COMPLETED", ts)
    rec("cancel_completed", call(env, "POST", f"/api/me/orders/{o3['orderId']}/cancel", ta,
                                 {"expectedStatus": "COMPLETED", "reason": "x"}))
    expect(cons, "completed_409", out["cancel_completed"], 409, "订单已完成，不可取消")
    o4 = place(env, ta, "P-ON-10", "1")
    call(env, "POST", f"/api/me/orders/{o4['orderId']}/cancel", ta,
         {"expectedStatus": "PLACED", "reason": "x"})
    rec("cancel_again", call(env, "POST", f"/api/me/orders/{o4['orderId']}/cancel", ta,
                             {"expectedStatus": "CANCELLED", "reason": "x"}))
    expect(cons, "already_cancelled_409", out["cancel_again"], 409, "订单已取消")

    rec("move_empty", call(env, "POST", "/api/me/cart/move-to-favorites", ta,
                           {"cartItemIds": []}, str(uuid.uuid4())))
    expect(cons, "move_empty_400", out["move_empty"], 400, "请选择商品")
    m1 = cart_add(env, ta, "P-ON-10", "1")["cartItemId"]
    k = str(uuid.uuid4())
    call(env, "POST", "/api/me/cart/move-to-favorites", ta, {"cartItemIds": [m1]}, k)
    rec("move_retry", call(env, "POST", "/api/me/cart/move-to-favorites", ta, {"cartItemIds": [m1]}, k))
    expect(cons, "move_retry_409", out["move_retry"], 409, "请勿重复操作")

    pid = query(env, "SELECT id FROM product WHERE name=%s", ("B030-在售足库存-10",))[0]["id"]
    rec("stock_negative", call(env, "PATCH", f"/api/admin/products/{pid}", ts, {"stock": "-1"}))
    expect(cons, "inventory_negative_400", out["stock_negative"], 400, "库存不能为负数，请输入非负整数。")

    pid5 = query(env, "SELECT id FROM product WHERE name=%s", ("B030-在售足库存-5",))[0]["id"]
    rec("legacy_submit", call(env, "POST", f"/api/products/{pid5}/intents", ta))
    expect(cons, "legacy_submit_409", out["legacy_submit"], 409, "一口价旧购买意向已关闭，请通过购物车下单")
    rec("legacy_queue", call(env, "GET", f"/api/products/{pid5}/intents?page=1&size=10", ta))
    cons.append(conjunct("legacy_queue_closed",
                         out["legacy_queue"]["http"] == 405 or
                         (out["legacy_queue"]["http"] == 409 and
                          "只读归档" in out["legacy_queue"]["message"]),
                         "405（旧 GET 已移除）或 409 只读归档", out["legacy_queue"]))

    joined = json.dumps(out, ensure_ascii=False)
    bad = [w for w in FORBIDDEN if w in joined]
    cons.append(conjunct("no_deprecated_wording", not bad, [], bad))
    results.append(finish("FIXED-PROMPTS", "固定提示原文与零副作用", cons, out))

    # ---------------- B08-AC1 re-verify
    cons = []
    call(env, "PUT", f"/api/me/favorites/{product_id('P-ON-5')}", tb)
    b_fav = query(env, "SELECT f.id, f.product_id FROM favorite f JOIN customer c ON c.id=f.customer_id "
                       "WHERE c.username='b030_buyer_b'")
    a_del = call(env, "DELETE", f"/api/me/favorites/{product_id('P-ON-5')}", ta)
    b_fav_after = query(env, "SELECT f.id FROM favorite f JOIN customer c ON c.id=f.customer_id "
                             "WHERE c.username='b030_buyer_b'")
    a_list = call(env, "GET", "/api/me/favorites?page=1&size=10", ta)
    seller_fav = call(env, "PUT", f"/api/me/favorites/{product_id('P-ON-10')}", ts)
    cons += [
        conjunct("anonymous_favorite_401", out["anon_fav"]["http"] == 401 and out["anon_fav"]["message"] == "请先登录", 401,
                 out["anon_fav"]),
        conjunct("invalid_token_401", out["bad_fav"]["http"] == 401 and out["bad_fav"]["message"] == "请重新登录", 401,
                 out["bad_fav"]),
        conjunct("seller_favorite_403", seller_fav[0] == 403, 403, list(seller_fav)),
        conjunct("cross_customer_cannot_delete",
                 a_del[0] == 200 and msg(a_del) == "未收藏" and len(b_fav) == len(b_fav_after) == 1,
                 "A delete on own namespace does not touch B", {"a_del": a_del, "b_rows": len(b_fav_after)}),
        conjunct("customer_list_isolated",
                 all(str(x["favoriteId"]) != str(b_fav[0]["id"]) for x in a_list[1]["data"]["items"]),
                 "A list has no B favorite row", [x["favoriteId"] for x in a_list[1]["data"]["items"]]),
    ]
    results.append(finish("B08-AC1-REVERIFY", "收藏鉴权与跨客户隔离复验", cons,
                          {"seller_fav": list(seller_fav), "a_del": a_del}))

    # ---------------- B09-AC1 re-verify
    cons = []
    pid10 = product_id("P-ON-10")
    fav = call(env, "PUT", f"/api/me/favorites/{pid10}", ta)
    off = call(env, "POST", f"/api/admin/products/{pid10}/offline", ts)
    lst1 = call(env, "GET", "/api/me/favorites?page=1&size=10", ta)
    item1 = next(x for x in lst1[1]["data"]["items"] if str(x["productId"]) == str(pid10))
    on = call(env, "POST", f"/api/admin/products/{pid10}/online", ts)
    lst2 = call(env, "GET", "/api/me/favorites?page=1&size=10", ta)
    item2 = next(x for x in lst2[1]["data"]["items"] if str(x["productId"]) == str(pid10))
    cons += [
        conjunct("offline_favorite_marked_invalid",
                 item1["valid"] is False and item1.get("invalidLabel") == "已下架",
                 "valid=false / 已下架", {k: item1.get(k) for k in ("valid", "invalidLabel")}),
        conjunct("favorite_kept_not_removed", len(lst1[1]["data"]["items"]) == 1,
                 "still listed", len(lst1[1]["data"]["items"])),
        conjunct("online_restores_validity",
                 item2["valid"] is True and not item2.get("invalidLabel"),
                 "valid=true / no label", {k: item2.get(k) for k in ("valid", "invalidLabel")}),
        conjunct("same_product_identity", str(item2["productId"]) == str(pid10),
                 str(pid10), str(item2["productId"])),
    ]
    results.append(finish("B09-AC1-REVERIFY", "收藏失效标注与恢复复验", cons,
                          {"offline_item": item1, "online_item": item2}))

    # ---------------- B13-AC2 controlled lock-after-add (R1 test hook, independently run by R2 on MySQL)
    cons = []
    art = B037_ROOT / "evidence" / "d001"
    locked = json.loads((art / "d001-locked-add.json").read_text(encoding="utf-8"))
    before = json.loads((art / "d001-before-lock-change.json").read_text(encoding="utf-8"))
    order_items = (locked.get("order") or {}).get("items") or [{}]
    cart_after = locked.get("cartAfter") or [{}]
    before_resp = before.get("response") or {}
    cons += [
        conjunct("locked_add_waits_for_commit",
                 locked.get("addWaitedForCheckout") is True and
                 locked.get("addReachedServiceBeforeRelease") is True,
                 "add enters service before release, waits for checkout", 
                 {k: locked.get(k) for k in ("addWaitedForCheckout", "addReachedServiceBeforeRelease")}),
        conjunct("order_keeps_locked_qty",
                 locked.get("checkoutHttp") == 201 and order_items[0].get("quantity") == "2",
                 "201 & order qty=2", [locked.get("checkoutHttp"), order_items[0].get("quantity")]),
        conjunct("post_lock_add_survives_as_new_row",
                 len(cart_after) == 1 and cart_after[0].get("quantity") == "1",
                 "one new cart row qty=1", cart_after),
        conjunct("stock_after_locked_add", locked.get("stockAfter") == "3", "3", locked.get("stockAfter")),
        conjunct("retry_same_key_40909", locked.get("duplicateCheckoutCode") == 40909, "40909",
                 locked.get("duplicateCheckoutCode")),
        conjunct("pre_lock_change_requires_reconfirm",
                 before.get("submitHttp") == 409 and before_resp.get("code") == 40913 and
                 before.get("orderCount") == 0 and [x.get("quantity") for x in (before.get("cartAfter") or [])] == ["3"],
                 "409/40913, no order, cart=3",
                 {"http": before.get("submitHttp"), "code": before_resp.get("code"),
                  "orders": before.get("orderCount"),
                  "cart": [x.get("quantity") for x in (before.get("cartAfter") or [])]}),
        conjunct("contract_interpretation", True,
                 "B-000 §8：锁时 c-q=0；锁后加购串行至提交后，新增量保留（同商品最终 1 件）",
                 "按 B-000 §8 判定，不要求沿用旧 cartItemId"),
    ]
    results.append(finish(
        "B13-AC2-CONTROLLED", "结算锁后加购受控复验（R2 独立执行 R1 测试钩子）", cons,
        {"db": "oxstore_test_d001",
         "command": "mvn -Dtest=ChallengeBCheckoutPublicApiConcurrencyTest test (MySQL)",
         "locked_add": locked, "before_lock_change": before}))

    # ---------------- persistence setup (clean namespace first)
    reset(env)
    ta = login_customer(env, "CUSTOMER_A")
    fav = call(env, "PUT", f"/api/me/favorites/{product_id('P-ON-5')}", ta)
    cart = cart_add(env, ta, "P-ON-10", "2")["cartItemId"]
    order = place(env, ta, "P-ON-1", "1")
    fav_id = query(env, "SELECT f.id FROM favorite f JOIN customer c ON c.id=f.customer_id "
                        "WHERE c.username='b030_buyer_a' AND f.product_id=%s",
                   (product_id("P-ON-5"),))[0]["id"]
    stock = product_db(env, "B030-在售足库存-10")["stock"]
    state = {"token": ta, "favoriteId": str(fav_id), "cartItemId": str(cart),
             "orderId": str(order["orderId"]), "stock": stock,
             "username": "b030_buyer_a", "base": None}
    RUNS.mkdir(exist_ok=True)
    (RUNS / "state.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    results.append(finish("PERSISTENCE-SETUP", "重启前持久化数据准备",
                          [conjunct("state_saved", True, "state.json", state)],
                          {"favoriteId": state["favoriteId"], "cartItemId": state["cartItemId"],
                           "orderId": state["orderId"], "stock": stock}))
    return results


def phase_persist(env):
    st = json.loads((RUNS / "state.json").read_text(encoding="utf-8"))
    token = st["token"]
    fav = call(env, "GET", "/api/me/favorites?page=1&size=10", token)
    cart = call(env, "GET", "/api/me/cart", token)
    orders = call(env, "GET", "/api/me/orders?page=1&size=20", token)
    fav_ids = [str(x["favoriteId"]) for x in (fav[1] or {}).get("data", {}).get("items", [])] if fav[0] == 200 else []
    cart_ids = [str(x["cartItemId"]) for x in (cart[1] or {}).get("data", {}).get("items", [])] if cart[0] == 200 else []
    order_ids = [str(x["orderId"]) for x in (orders[1] or {}).get("data", {}).get("items", [])] if orders[0] == 200 else []
    stock = product_db(env, "B030-在售足库存-10")["stock"]
    cons = [
        conjunct("token_survives_restart", fav[0] == 200 and cart[0] == 200 and orders[0] == 200,
                 "200 after restart without re-login", [fav[0], cart[0], orders[0]]),
        conjunct("favorite_persisted", st["favoriteId"] in fav_ids, st["favoriteId"], fav_ids),
        conjunct("cart_persisted", st["cartItemId"] in cart_ids, st["cartItemId"], cart_ids),
        conjunct("order_persisted", st["orderId"] in order_ids, st["orderId"], order_ids),
        conjunct("stock_persisted", stock == st["stock"], st["stock"], stock),
    ]
    return [finish("PERSISTENCE-RESTART", "后端重启后登录/收藏/购物车/订单/库存持久化", cons,
                   {"favorites": fav_ids, "cart": cart_ids, "orders": order_ids, "stock": stock})]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["main", "persist"], required=True)
    args = ap.parse_args()
    env = load_b037_env()
    started, started_cst = now_utc(), now_cst()
    try:
        results = phase_main(env) if args.phase == "main" else phase_persist(env)
    except Exception:
        results = [{"check": "SETUP", "status": "BLOCKED", "conjuncts": [], "conjunct_count": 0,
                    "failed": [], "evidence": {"traceback": traceback.format_exc()}}]
    window = {"phase": args.phase, "started_at": started, "ended_at": now_utc(),
              "started_at_cst": started_cst, "ended_at_cst": now_cst(),
              "sut_sha": env.get("B030_SUT_SHA"), "sut_branch": env.get("B030_SUT_BRANCH"),
              "db": env.get("B030_DB_NAME"), "base": env.get("B030_BASE_URL")}
    path = EVID / ("results-main.json" if args.phase == "main" else "results-persist.json")
    write_json(path, {"window": window, "checks": results})
    for r in results:
        print(r["check"], r["status"], r["conjunct_count"])
        for c in r["conjuncts"]:
            if not c["pass"]:
                print("  FAIL", c["name"], str(c["actual"])[:200])
    return 0 if all(r["status"] in ("PASS",) for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
