#!/usr/bin/env python3
"""B-033 acceptance runner: PB-B04 x7 + PB-B05 x4 + PB-B06 x6 + PB-B07 x2 = 19 AC.

Executes the B-030 plan (cases/PB-B04..B07.md, concurrency/SEQ.md, execution/B033.md)
against a live SUT and records per-AC conjunct evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
import uuid
from pathlib import Path

from b033_common import (  # noqa: E402
    B033_ROOT,
    advance,
    allowed_actions,
    base_url,
    cancel,
    conjunct,
    http_json,
    list_orders,
    load_b034_env,
    login_customer,
    login_seller,
    now_cst,
    now_utc,
    order_db,
    order_detail,
    place,
    product_db,
    query,
    race,
    reset,
    write_json,
)

EVID = B033_ROOT / "evidence"
CASES = EVID / "cases"
B = None


def msg(res: tuple) -> str:
    return (res[1] or {}).get("message", "") if isinstance(res, tuple) else ""


def ok(res: tuple, message: str | None = None) -> bool:
    return res[0] == 200 and (message is None or msg(res) == message)


def status_of(order_id) -> str:
    return order_db(CTX["env"], order_id)["status"]


def finish_ac(ac: str, pb: str, title: str, cons: list[dict], evidence: dict) -> dict:
    failed = [c for c in cons if not c["pass"] and not c["disposition_if_fail"].startswith("DEFER")]
    deferred = [c for c in cons if c["disposition_if_fail"].startswith("DEFER")]
    if failed:
        status = "FAIL"
    elif deferred:
        status = "PASS_API_DEFERRED"
    else:
        status = "PASS"
    return {
        "ac": ac, "pb": pb, "title": title, "status": status,
        "conjuncts": cons, "conjunct_count": len(cons),
        "failed_conjuncts": [c["name"] for c in failed],
        "deferred_conjuncts": [c["name"] for c in deferred],
        "evidence": evidence,
    }


# ---------------------------------------------------------------- PB-B04


def b04_1_impl(c):
    env = c["env"]
    reset(env)
    o1 = place(env, c["ta"], "P-ON-10", "1")
    r1 = cancel(env, c["ta"], o1["orderId"], "PLACED")
    o2 = place(env, c["ta"], "P-ON-10", "1")
    advance(env, o2["orderId"], "CONFIRMED", c["ts"])
    r2 = cancel(env, c["ta"], o2["orderId"], "CONFIRMED")
    o3 = place(env, c["ta"], "P-ON-10", "1")
    advance(env, o3["orderId"], "PREPARED", c["ts"])
    r3 = cancel(env, c["ta"], o3["orderId"], "PREPARED")
    o4 = place(env, c["ta"], "P-ON-10", "1")
    advance(env, o4["orderId"], "SHIPPED", c["ts"])
    r4 = cancel(env, c["ta"], o4["orderId"], "SHIPPED")
    cons = [
        conjunct("cancel_placed", ok(r1) and status_of(o1["orderId"]) == "CANCELLED", "200 & CANCELLED", r1),
        conjunct("cancel_confirmed", ok(r2) and status_of(o2["orderId"]) == "CANCELLED", "200 & CANCELLED", r2),
        conjunct("cancel_prepared", ok(r3) and status_of(o3["orderId"]) == "CANCELLED", "200 & CANCELLED", r3),
        conjunct("shipped_rejected", r4[0] == 409 and msg(r4) == "订单已开始发货，不可取消",
                 "409 / 订单已开始发货，不可取消", r4),
        conjunct("server_state_is_authority", status_of(o4["orderId"]) == "SHIPPED", "SHIPPED stays", status_of(o4["orderId"])),
    ]
    reset(env)
    return finish_ac("PB-B04-AC1", "PB-B04", "客户可取消至备货完成；开始发货后不可取消", cons,
                     {"responses": [r1, r2, r3, r4]})


def b04_2(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "2")
    oid = o["orderId"]
    stock_before = product_db(env, "B030-在售足库存-10")["stock"]
    noauth = http_json("POST", f"{base_url(env)}/api/me/orders/{oid}/cancel",
                       {"expectedStatus": "PLACED", "reason": "x"}, {})
    invalid = cancel(env, "invalid.token.value", oid, "PLACED")
    other = cancel(env, c["tb"], oid, "PLACED")
    missing = cancel(env, c["ta"], 99999999, "PLACED")
    db = order_db(env, oid)
    stock_after = product_db(env, "B030-在售足库存-10")["stock"]
    cons = [
        conjunct("anonymous_401", noauth[0] == 401 and noauth[1]["message"] == "请先登录",
                 "401 / 请先登录", noauth),
        conjunct("invalid_token_401", invalid[0] == 401 and msg(invalid) == "请重新登录",
                 "401 / 请重新登录", invalid),
        conjunct("other_order_403", other[0] == 403 and msg(other) == "无权操作该订单",
                 "403 / 无权操作该订单", other),
        conjunct("missing_order_404", missing[0] == 404 and msg(missing) == "订单不存在",
                 "404 / 订单不存在", missing),
        conjunct("no_state_or_stock_change", db["status"] == "PLACED" and stock_before == stock_after,
                 "PLACED & stock unchanged", {"status": db["status"], "before": stock_before, "after": stock_after}),
    ]
    reset(env)
    return finish_ac("PB-B04-AC2", "PB-B04", "仅本人可取消；未登录/失效/他人/不存在均拒绝", cons,
                     {"oid": oid, "noauth": noauth, "invalid": invalid, "other": other, "missing": missing})


def b04_3(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "2")
    stock_before = product_db(env, "B030-在售足库存-10")["stock"]
    partial = cancel(env, c["ta"], o["orderId"], body={"expectedStatus": "PLACED",
                                                       "reason": "x", "items": ["1"]})
    db = order_db(env, o["orderId"])
    stock_after = product_db(env, "B030-在售足库存-10")["stock"]
    cons = [
        conjunct("partial_rejected", partial[0] == 400 and msg(partial) == "不支持部分取消",
                 "400 / 不支持部分取消", partial),
        conjunct("order_unchanged", db["status"] == "PLACED", "PLACED", db["status"]),
        conjunct("stock_unchanged", stock_before == stock_after, stock_before,
                 {"before": stock_before, "after": stock_after}),
    ]
    reset(env)
    return finish_ac("PB-B04-AC3", "PB-B04", "只能整单取消；部分取消整单拒绝", cons,
                     {"response": partial})


def b04_4(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "2")
    oid = o["orderId"]
    before = order_detail(env, c["ta"], oid)
    r = cancel(env, c["ta"], oid, "PLACED", body={"expectedStatus": "PLACED", "reason": "客户取消测试"})
    db = order_db(env, oid)
    after = order_detail(env, c["ta"], oid)
    listing = list_orders(env, c["ta"], page=1, size=10)
    items = (listing[1] or {}).get("data", {}).get("items", []) if listing[0] == 200 else []
    listed = next((x for x in items if str(x.get("orderId")) == str(oid)), None)
    cons = [
        conjunct("cancel_ok", ok(r), "200", r),
        conjunct("status_cancelled", db["status"] == "CANCELLED", "CANCELLED", db["status"]),
        conjunct("cancelled_by_customer", db["cancelled_by"] == "CUSTOMER", "CUSTOMER", db["cancelled_by"]),
        conjunct("cancelled_at_set", db["cancelled_at"] is not None, "not null", str(db["cancelled_at"])),
        conjunct("reason_kept", db["cancel_reason"] == "客户取消测试", "客户取消测试", db["cancel_reason"]),
        conjunct("total_amount_unchanged",
                 db["total_amount"] == before[1]["data"]["totalAmount"], before[1]["data"]["totalAmount"],
                 db["total_amount"]),
        conjunct("history_list_shows_cancelled", listed is not None and
                 listed.get("cancelledBy") == "CUSTOMER" and listed.get("cancelledAt"),
                 "listed with cancelledBy/At", listed),
    ]
    reset(env)
    return finish_ac("PB-B04-AC4", "PB-B04", "取消后终态与元数据可追溯，出现在订单历史", cons,
                     {"db": db, "detail": after[1], "listed": listed})


def b04_5(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "2")
    oid = o["orderId"]
    first = cancel(env, c["ta"], oid, "PLACED")
    stock_after_first = product_db(env, "B030-在售足库存-10")["stock"]
    again = cancel(env, c["ta"], oid, "CANCELLED")
    stock_after_again = product_db(env, "B030-在售足库存-10")["stock"]
    o2 = place(env, c["ta"], "P-ON-10", "1")
    advance(env, o2["orderId"], "SHIPPED", c["ts"])
    shipped_cancel = cancel(env, c["ta"], o2["orderId"], "SHIPPED")
    shipped_actions = allowed_actions(order_detail(env, c["ta"], o2["orderId"]))
    o3 = place(env, c["ta"], "P-ON-10", "1")
    advance(env, o3["orderId"], "COMPLETED", c["ts"])
    completed_cancel = cancel(env, c["ta"], o3["orderId"], "COMPLETED")
    cancelled_actions = allowed_actions(order_detail(env, c["ta"], oid))
    cons = [
        conjunct("repeat_cancel_409", again[0] == 409 and msg(again) == "订单已取消",
                 "409 / 订单已取消", again),
        conjunct("no_second_restock", stock_after_first == stock_after_again,
                 stock_after_first, {"first": stock_after_first, "again": stock_after_again}),
        conjunct("shipped_cancel_409", shipped_cancel[0] == 409 and
                 msg(shipped_cancel) == "订单已开始发货，不可取消", "409 / 已开始发货", shipped_cancel),
        conjunct("completed_cancel_409", completed_cancel[0] == 409 and
                 msg(completed_cancel) == "订单已完成，不可取消", "409 / 已完成", completed_cancel),
        conjunct("no_cancel_action_on_shipped_or_terminal",
                 "CANCEL" not in shipped_actions and cancelled_actions == [],
                 "SHIPPED allowedActions has no CANCEL; CANCELLED empty",
                 {"shipped": shipped_actions, "cancelled": cancelled_actions}),
        conjunct("cancel_entry_ui", False, "UI 仅可取消状态显示/启用取消入口（含二次确认）",
                 "deferred to B-036", "DEFER_TO_B036"),
    ]
    reset(env)
    return finish_ac("PB-B04-AC5", "PB-B04", "重复/发货后/完成后取消拒绝；不可取消状态不显示入口", cons,
                     {"repeat": again, "shipped": shipped_cancel, "completed": completed_cancel})


def b04_6(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "1")
    no_reason = cancel(env, c["ta"], o["orderId"], body={"expectedStatus": "PLACED"})
    db1 = order_db(env, o["orderId"])
    o2 = place(env, c["ta"], "P-ON-10", "1")
    with_reason = cancel(env, c["ta"], o2["orderId"],
                         body={"expectedStatus": "PLACED", "reason": "不想要了"})
    db2 = order_db(env, o2["orderId"])
    cons = [
        conjunct("cancel_without_reason_allowed", ok(no_reason) and db1["status"] == "CANCELLED",
                 "200 & CANCELLED", no_reason),
        conjunct("reason_null_ok", db1["cancel_reason"] is None, None, db1["cancel_reason"]),
        conjunct("cancel_with_reason_stored", ok(with_reason) and db2["cancel_reason"] == "不想要了",
                 "reason stored", with_reason),
        conjunct("cancel_confirm_dialog", False, "入口在列表/详情，二次确认",
                 "deferred to B-036", "DEFER_TO_B036"),
    ]
    reset(env)
    return finish_ac("PB-B04-AC6", "PB-B04", "取消原因选填；入口与二次确认属 UI", cons,
                     {"no_reason": no_reason, "with_reason": with_reason})


def b04_7(c):
    env = c["env"]
    reset(env)
    intents = query(env, "SELECT COUNT(*) c FROM purchase_intent")
    listing = list_orders(env, c["ta"], page=1, size=10)
    new_total = (listing[1] or {}).get("data", {}).get("total") if listing[0] == 200 else None
    legacy_cancel = cancel(env, c["ta"], 99999998, "PLACED")
    cons = [
        conjunct("no_legacy_intent_in_new_orders", new_total == 0, "new order list total=0", new_total),
        conjunct("closed_intent_has_no_new_cancel_path", legacy_cancel[0] == 404 and
                 msg(legacy_cancel) == "订单不存在", "404 / 订单不存在", legacy_cancel),
        conjunct("legacy_intent_fixture", False,
                 "已关闭旧意向（purchase_intent.legacy_closed）不可取消，需 V8 归档数据",
                 f"purchase_intent rows={intents[0]['c']}; deferred to B-035", "DEFER_TO_B035"),
    ]
    reset(env)
    return finish_ac("PB-B04-AC7", "PB-B04", "旧意向不进入新取消流程", cons,
                     {"legacy_cancel": legacy_cancel, "purchase_intent": intents})


# ---------------------------------------------------------------- PB-B05


def b05_1(c):
    env = c["env"]
    reset(env)
    before = product_db(env, "B030-在售足库存-10")["stock"]
    o = place(env, c["ta"], "P-ON-10", "2")
    after_order = product_db(env, "B030-在售足库存-10")["stock"]
    r1 = cancel(env, c["ta"], o["orderId"], "PLACED")
    after_cancel = product_db(env, "B030-在售足库存-10")["stock"]
    r2 = cancel(env, c["ta"], o["orderId"], "CANCELLED")
    r3 = cancel(env, c["ta"], o["orderId"], "CANCELLED")
    after_triple = product_db(env, "B030-在售足库存-10")["stock"]
    cart = query(env, "SELECT COUNT(*) c FROM cart_item ci JOIN customer c2 ON c2.id=ci.customer_id "
                      "WHERE c2.username='b030_buyer_a'")[0]["c"]
    cons = [
        conjunct("order_deducts_snapshot_qty", int(after_order) == int(before) - 2,
                 f"{before}-2", after_order),
        conjunct("cancel_restores_exactly_snapshot", int(after_cancel) == int(before),
                 before, after_cancel),
        conjunct("repeat_and_triple_do_not_restock",
                 r2[0] == 409 and r3[0] == 409 and after_triple == after_cancel,
                 "409/409 & stock stable", {"r2": r2, "r3": r3, "stock": after_triple}),
        conjunct("no_auto_return_to_cart", cart == 0, "cart=0", cart),
    ]
    reset(env)
    return finish_ac("PB-B05-AC1", "PB-B05", "按快照回补一次；不回车、不重复回补", cons,
                     {"before": before, "after_order": after_order, "after_cancel": after_cancel})


def b05_2(c):
    env = c["env"]
    reset(env)
    o1 = place(env, c["ta"], "P-ON-1", "1")
    auto_before = product_db(env, "B030-低库存-1")
    r1 = cancel(env, c["ta"], o1["orderId"], "PLACED")
    auto_after = product_db(env, "B030-低库存-1")
    o2 = place(env, c["ta"], "P-ON-10", "1")
    http_json("POST", f"{base_url(env)}/api/admin/products/{query(env, 'SELECT id FROM product WHERE name=%s', ('B030-在售足库存-10',))[0]['id']}/offline",
              headers={"Authorization": f"Bearer {c['ts']}"})
    manual_before = product_db(env, "B030-在售足库存-10")
    r2 = cancel(env, c["ta"], o2["orderId"], "PLACED")
    manual_after = product_db(env, "B030-在售足库存-10")
    cons = [
        conjunct("auto_zero_offline_on_depletion",
                 auto_before["stock"] == "0" and auto_before["status"] == "OFFLINE" and
                 auto_before["offline_reason"] == "AUTO_ZERO", "0/OFFLINE/AUTO_ZERO", auto_before),
        conjunct("cancel_auto_restores_online",
                 ok(r1) and auto_after["stock"] == "1" and auto_after["status"] == "ONLINE" and
                 auto_after["offline_reason"] is None, "1/ONLINE/null", auto_after),
        conjunct("manual_offline_stays_offline",
                 manual_before["status"] == "OFFLINE" and manual_before["offline_reason"] == "MANUAL" and
                 ok(r2) and manual_after["status"] == "OFFLINE" and
                 manual_after["offline_reason"] == "MANUAL", "OFFLINE/MANUAL after restock", manual_after),
        conjunct("manual_stock_added_back", int(manual_after["stock"]) == int(manual_before["stock"]) + 1,
                 f"{manual_before['stock']}+1", manual_after["stock"]),
    ]
    reset(env)
    return finish_ac("PB-B05-AC2", "PB-B05", "取消回补只在 AUTO_ZERO 时自动上架；手动下架保持", cons,
                     {"auto": {"before": auto_before, "after": auto_after},
                      "manual": {"before": manual_before, "after": manual_after}})


def b05_3(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "2")
    advance(env, o["orderId"], "PREPARED", c["ts"])
    stock_before = product_db(env, "B030-在售足库存-10")["stock"]
    a, b = race(
        lambda: cancel(env, c["ta"], o["orderId"], "PREPARED"),
        lambda: http_json("POST", f"{base_url(env)}/api/admin/orders/{o['orderId']}/actions",
                          {"action": "SHIP", "expectedStatus": "PREPARED"},
                          {"Authorization": f"Bearer {c['ts']}"}),
    )
    st = status_of(o["orderId"])
    stock_after = product_db(env, "B030-在售足库存-10")["stock"]
    legal = (st == "CANCELLED" and a[0] == 200 and b[0] == 409 and int(stock_after) == int(stock_before) + 2) or \
            (st == "SHIPPED" and b[0] == 200 and a[0] == 409 and stock_after == stock_before)
    cons = [
        conjunct("cancel_vs_ship_one_winner", legal, "CANCELLED+restock or SHIPPED+no restock",
                 {"a": a, "b": b, "status": st, "stock": [stock_before, stock_after]}),
        conjunct("loser_rejected_with_contract_message",
                 (a[0] == 409 and msg(a) in ("订单已取消", "订单已开始发货，不可取消")) or
                 (b[0] == 409), "loser 409", {"a": msg(a), "b": msg(b)}),
        conjunct("no_5xx", a[0] < 500 and b[0] < 500, "no 5xx", [a[0], b[0]]),
    ]
    reset(env)
    return finish_ac("PB-B05-AC3", "PB-B05", "取消 vs 开始发货：先成功者生效，库存只变一次", cons,
                     {"race": {"cancel": a, "ship": b}, "status": st})


def b05_4(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "1")
    a, b = race(
        lambda: cancel(env, c["ta"], o["orderId"], "PLACED"),
        lambda: http_json("POST", f"{base_url(env)}/api/admin/orders/{o['orderId']}/actions",
                          {"action": "CONFIRM", "expectedStatus": "PLACED"},
                          {"Authorization": f"Bearer {c['ts']}"}),
    )
    st = status_of(o["orderId"])
    followup = None
    if st == "CONFIRMED":
        followup = cancel(env, c["ta"], o["orderId"], "CONFIRMED")
        st = status_of(o["orderId"])
    stock = product_db(env, "B030-在售足库存-10")["stock"]
    legal = (st == "CANCELLED" and stock == "10" and
             (a[0] == 200 or (b[0] == 200 and followup is not None and followup[0] == 200))) or \
            (st == "CONFIRMED" and b[0] == 200)
    cons = [
        conjunct("confirm_vs_cancel_one_winner", legal,
                 "CANCELLED+restock or CONFIRMED (then cancel allowed)",
                 {"a": a, "b": b, "status": st}),
        conjunct("confirm_first_still_cancellable",
                 followup is None or (followup[0] == 200 and st == "CANCELLED"),
                 "after CONFIRMED, a new cancel succeeds", followup),
        conjunct("no_5xx", a[0] < 500 and b[0] < 500, "no 5xx", [a[0], b[0]]),
    ]
    reset(env)
    return finish_ac("PB-B05-AC4", "PB-B05", "取消 vs 确认/备货：先成功者生效，确认后备货仍可取消", cons,
                     {"race": {"cancel": a, "confirm": b}, "followup": followup, "status": st})


# ---------------------------------------------------------------- PB-B06


def b06_1(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "1")
    oid = o["orderId"]
    noauth = http_json("POST", f"{base_url(env)}/api/admin/orders/{oid}/cancel",
                       {"expectedStatus": "PLACED", "reason": "x"}, {})
    customer_token = http_json("POST", f"{base_url(env)}/api/admin/orders/{oid}/cancel",
                               {"expectedStatus": "PLACED", "reason": "x"},
                               {"Authorization": f"Bearer {c['ta']}"})
    seller = cancel(env, c["ts"], oid, "PLACED", seller=True)
    db = order_db(env, oid)
    cons = [
        conjunct("seller_anonymous_401", noauth[0] == 401 and noauth[1]["message"] == "请先登录后台",
                 "401 / 请先登录后台", noauth),
        conjunct("customer_token_403", customer_token[0] == 403,
                 "403", customer_token),
        conjunct("seller_cancel_ok", ok(seller) and db["status"] == "CANCELLED",
                 "200 & CANCELLED", seller),
    ]
    reset(env)
    return finish_ac("PB-B06-AC1", "PB-B06", "商家取消须登录卖家后台", cons,
                     {"noauth": noauth, "customer_token": customer_token, "seller": seller})


def b06_2(c):
    env = c["env"]
    reset(env)
    outcomes = {}
    for target in ("PLACED", "CONFIRMED", "PREPARED", "SHIPPED"):
        o = place(env, c["ta"], "P-ON-10", "1")
        if target != "PLACED":
            advance(env, o["orderId"], target, c["ts"])
        r = cancel(env, c["ts"], o["orderId"], target, seller=True)
        outcomes[target] = {"response": r, "status": status_of(o["orderId"]),
                            "cancelled_by": order_db(env, o["orderId"])["cancelled_by"]}
    cons = [
        conjunct(f"seller_cancel_{s.lower()}", ok(outcomes[s]["response"]) and
                 outcomes[s]["status"] == "CANCELLED" and outcomes[s]["cancelled_by"] == "SELLER",
                 "200 & CANCELLED/SELLER", outcomes[s]) for s in outcomes
    ]
    reset(env)
    return finish_ac("PB-B06-AC2", "PB-B06", "商家在发货后仍可取消，仅交易完成后不可", cons,
                     {"outcomes": outcomes})


def b06_3(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "2")
    oid = o["orderId"]
    r = cancel(env, c["ts"], oid, "PLACED", seller=True,
               body={"expectedStatus": "PLACED", "reason": "商家取消测试"})
    db = order_db(env, oid)
    listing = list_orders(env, c["ts"], seller=True, page=1, size=10)
    items = (listing[1] or {}).get("data", {}).get("items", []) if listing[0] == 200 else []
    listed = next((x for x in items if str(x.get("orderId")) == str(oid)), None)
    cons = [
        conjunct("cancelled_by_seller", db["cancelled_by"] == "SELLER", "SELLER", db["cancelled_by"]),
        conjunct("cancelled_at_set", db["cancelled_at"] is not None, "not null", str(db["cancelled_at"])),
        conjunct("admin_list_shows", listed is not None and listed.get("cancelledBy") == "SELLER",
                 "admin list shows cancelledBy=SELLER", listed),
        conjunct("reason_kept", db["cancel_reason"] == "商家取消测试", "reason kept", db["cancel_reason"]),
    ]
    reset(env)
    return finish_ac("PB-B06-AC3", "PB-B06", "商家取消记录发起方与时间，进入订单管理", cons,
                     {"db": db, "listed": listed})


def b06_4(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "2")
    first = cancel(env, c["ts"], o["orderId"], "PLACED", seller=True)
    stock1 = product_db(env, "B030-在售足库存-10")["stock"]
    again = cancel(env, c["ts"], o["orderId"], "CANCELLED", seller=True)
    stock2 = product_db(env, "B030-在售足库存-10")["stock"]
    o2 = place(env, c["ta"], "P-ON-10", "1")
    advance(env, o2["orderId"], "COMPLETED", c["ts"])
    stock_before_complete_cancel = product_db(env, "B030-在售足库存-10")["stock"]
    completed = cancel(env, c["ts"], o2["orderId"], "COMPLETED", seller=True)
    stock_after = product_db(env, "B030-在售足库存-10")["stock"]
    cons = [
        conjunct("repeat_seller_cancel_409", again[0] == 409 and msg(again) == "订单已取消",
                 "409 / 订单已取消", again),
        conjunct("no_second_restock", stock1 == stock2, stock1, {"first": stock1, "again": stock2}),
        conjunct("completed_cannot_cancel", completed[0] == 409 and
                 msg(completed) == "订单已完成，不可取消", "409 / 订单已完成，不可取消", completed),
        conjunct("completed_stock_unchanged", stock_before_complete_cancel == stock_after,
                 stock_before_complete_cancel, {"before": stock_before_complete_cancel, "after": stock_after}),
        conjunct("terminal_no_cancel_entry",
                 allowed_actions(order_detail(env, c["ts"], o["orderId"], seller=True)) == [] and
                 allowed_actions(order_detail(env, c["ts"], o2["orderId"], seller=True)) == [],
                 "allowedActions=[] for CANCELLED/COMPLETED", "deferred UI to B-036"),
    ]
    reset(env)
    return finish_ac("PB-B06-AC4", "PB-B06", "重复取消/完成取消拒绝，不二次回补", cons,
                     {"repeat": again, "completed": completed})


def b06_5(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "1")
    partial = cancel(env, c["ts"], o["orderId"], seller=True,
                     body={"expectedStatus": "PLACED", "reason": "x", "itemIds": ["1"]})
    whole = cancel(env, c["ts"], o["orderId"], "PLACED", seller=True)
    db = order_db(env, o["orderId"])
    cons = [
        conjunct("partial_rejected", partial[0] == 400 and msg(partial) == "不支持部分取消",
                 "400 / 不支持部分取消", partial),
        conjunct("whole_cancel_ok", ok(whole) and db["status"] == "CANCELLED", "200 & CANCELLED", whole),
        conjunct("entry_and_confirm_ui", False, "订单管理入口、二次确认、旧页面只读",
                 "deferred to B-036", "DEFER_TO_B036"),
    ]
    reset(env)
    return finish_ac("PB-B06-AC5", "PB-B06", "仅整单取消；入口与二次确认属 UI", cons,
                     {"partial": partial, "whole": whole})


def b06_6(c):
    env = c["env"]
    reset(env)
    intents = query(env, "SELECT COUNT(*) c FROM purchase_intent")[0]["c"]
    legacy = cancel(env, c["ts"], 99999997, "PLACED", seller=True)
    cons = [
        conjunct("closed_intent_has_no_seller_cancel_path",
                 legacy[0] == 404 and msg(legacy) == "订单不存在", "404 / 订单不存在", legacy),
        conjunct("legacy_intent_fixture", False, "已关闭旧意向不进入新取消流程（需 V8 数据）",
                 f"purchase_intent rows={intents}; deferred to B-035", "DEFER_TO_B035"),
    ]
    reset(env)
    return finish_ac("PB-B06-AC6", "PB-B06", "旧意向不进入商家取消流程", cons,
                     {"legacy": legacy})


# ---------------------------------------------------------------- PB-B07


def b07_1(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "2")
    advance(env, o["orderId"], "SHIPPED", c["ts"])
    stock_before = product_db(env, "B030-在售足库存-10")["stock"]
    r = cancel(env, c["ts"], o["orderId"], "SHIPPED", seller=True)
    stock_after = product_db(env, "B030-在售足库存-10")["stock"]
    db = order_db(env, o["orderId"])
    rebuy = place(env, c["ta"], "P-ON-10", "1")
    cons = [
        conjunct("seller_cancel_after_ship_ok", ok(r) and db["status"] == "CANCELLED",
                 "200 & CANCELLED", r),
        conjunct("restock_snapshot_qty", int(stock_after) == int(stock_before) + 2,
                 f"{stock_before}+2", stock_after),
        conjunct("no_logistics_required", db["cancelled_by"] == "SELLER" and db["cancelled_at"] is not None,
                 "SELLER + time, no logistics fields", db),
        conjunct("customer_can_rebuy_after_cancel", rebuy.get("http") in (200, 201),
                 "new order accepted", rebuy.get("http")),
    ]
    reset(env)
    return finish_ac("PB-B07-AC1", "PB-B07", "商家发货后取消：终态+回补，无物流凭证要求", cons,
                     {"response": r, "db": db, "stock": [stock_before, stock_after]})


def b07_2(c):
    env = c["env"]
    reset(env)
    o1 = place(env, c["ta"], "P-ON-10", "1")
    a, b = race(
        lambda: cancel(env, c["ta"], o1["orderId"], "PLACED"),
        lambda: cancel(env, c["ts"], o1["orderId"], "PLACED", seller=True),
    )
    st1 = status_of(o1["orderId"])
    stock1 = product_db(env, "B030-在售足库存-10")["stock"]
    reset(env)
    o2 = place(env, c["ta"], "P-ON-10", "2")
    advance(env, o2["orderId"], "SHIPPED", c["ts"])
    before2 = product_db(env, "B030-在售足库存-10")["stock"]
    c1, c2 = race(
        lambda: cancel(env, c["ts"], o2["orderId"], "SHIPPED", seller=True),
        lambda: http_json("POST", f"{base_url(env)}/api/admin/orders/{o2['orderId']}/actions",
                          {"action": "COMPLETE", "expectedStatus": "SHIPPED"},
                          {"Authorization": f"Bearer {c['ts']}"}),
    )
    st2 = status_of(o2["orderId"])
    stock2 = product_db(env, "B030-在售足库存-10")["stock"]
    legal1 = st1 == "CANCELLED" and stock1 == "10" and (a[0] == 200 or b[0] == 200)
    legal2 = (st2 == "CANCELLED" and int(stock2) == int(before2) + 2) or \
             (st2 == "COMPLETED" and stock2 == before2)
    reset(env)
    o3 = place(env, c["ta"], "P-ON-10", "1")
    advance(env, o3["orderId"], "CONFIRMED", c["ts"])
    later = cancel(env, c["ta"], o3["orderId"], "CONFIRMED")
    cons = [
        conjunct("customer_vs_seller_cancel_one_winner", legal1,
                 "CANCELLED, stock restored once", {"a": a, "b": b, "status": st1, "stock": stock1}),
        conjunct("seller_cancel_vs_complete", legal2,
                 "CANCELLED+restock or COMPLETED+no restock",
                 {"cancel": c1, "complete": c2, "status": st2, "stock": [before2, stock2]}),
        conjunct("confirm_does_not_block_cancel", later[0] == 200,
                 "cancel after CONFIRM succeeds", later),
        conjunct("no_5xx", all(x[0] < 500 for x in (a, b, c1, c2)), "no 5xx",
                 [a[0], b[0], c1[0], c2[0]]),
    ]
    reset(env)
    return finish_ac("PB-B07-AC2", "PB-B07", "双方取消/取消与完成并发：先成功者生效，回补一次", cons,
                     {"customer_vs_seller": {"a": a, "b": b, "status": st1},
                      "cancel_vs_complete": {"cancel": c1, "complete": c2, "status": st2}})


# ---------------------------------------------------------------- SEQ / HR


def seq12(c):
    env = c["env"]
    reset(env)
    o = place(env, c["ta"], "P-ON-10", "1")
    stock_before = product_db(env, "B030-在售足库存-10")["stock"]
    a, b = race(
        lambda: http_json("POST", f"{base_url(env)}/api/admin/orders/{o['orderId']}/actions",
                          {"action": "CONFIRM", "expectedStatus": "PLACED"},
                          {"Authorization": f"Bearer {c['ts']}"}),
        lambda: http_json("POST", f"{base_url(env)}/api/admin/orders/{o['orderId']}/actions",
                          {"action": "CONFIRM", "expectedStatus": "PLACED"},
                          {"Authorization": f"Bearer {c['ts']}"}),
    )
    st = status_of(o["orderId"])
    stock_after = product_db(env, "B030-在售足库存-10")["stock"]
    cons = [
        conjunct("exactly_one_confirm_success", sorted([a[0], b[0]]) == [200, 409],
                 "one 200 + one 409", [a, b]),
        conjunct("status_confirmed", st == "CONFIRMED", "CONFIRMED", st),
        conjunct("no_stock_change_on_confirm", stock_before == stock_after, stock_before,
                 {"before": stock_before, "after": stock_after}),
    ]
    reset(env)
    return finish_ac("SEQ-12", "PB-B01", "两连接同时确认：恰一成功、不重复", cons,
                     {"a": a, "b": b, "status": st})


CHECKS = {
    "PB-B04-AC1": b04_1_impl,
    "PB-B04-AC2": b04_2, "PB-B04-AC3": b04_3, "PB-B04-AC4": b04_4,
    "PB-B04-AC5": b04_5, "PB-B04-AC6": b04_6, "PB-B04-AC7": b04_7,
    "PB-B05-AC1": b05_1, "PB-B05-AC2": b05_2, "PB-B05-AC3": b05_3, "PB-B05-AC4": b05_4,
    "PB-B06-AC1": b06_1, "PB-B06-AC2": b06_2, "PB-B06-AC3": b06_3,
    "PB-B06-AC4": b06_4, "PB-B06-AC5": b06_5, "PB-B06-AC6": b06_6,
    "PB-B07-AC1": b07_1, "PB-B07-AC2": b07_2,
    "SEQ-12": seq12,
}


def markdown(results, window):
    lines = [
        "# B-033 验收执行结果（PB-B04 ×7、PB-B05 ×4、PB-B06 ×6、PB-B07 ×2 + SEQ-12）",
        "",
        f"- 执行窗口：{window['started_at']} → {window['ended_at']}（{window['started_at_cst']} → {window['ended_at_cst']}）",
        f"- SUT：`{window['sut_branch']}@{window['sut_sha']}`；DB：`{window['db']}`；BASE：{window['base']}",
        "",
        "| AC | 状态 | 合取 | 失败合取 |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['ac']} | **{r['status']}** | {r['conjunct_count']} | {', '.join(r['failed_conjuncts']) or '—'} |")
    acs = [r for r in results if r["ac"].startswith("PB-")]
    pass_n = sum(1 for r in acs if r["status"].startswith("PASS"))
    fail_n = sum(1 for r in acs if r["status"] == "FAIL")
    lines += ["", f"合计：{len(acs)} AC / **{pass_n} 通过** / {fail_n} 失败 / {len(acs)-pass_n-fail_n} 阻塞；"
                  f"合取 {sum(r['conjunct_count'] for r in results)} 个。", ""]
    for r in results:
        if r["failed_conjuncts"]:
            lines.append(f"## {r['ac']} 失败合取")
            for x in r["conjuncts"]:
                if not x["pass"] and not x["disposition_if_fail"].startswith("DEFER"):
                    lines.append(f"- `{x['name']}`：期望 {x['expected']}；实际 {x['actual']}")
            lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    env = load_b034_env()
    global CTX
    CTX = {
        "env": env,
        "ta": login_customer(env, "CUSTOMER_A"),
        "tb": login_customer(env, "CUSTOMER_B"),
        "ts": login_seller(env),
        "uuid": lambda: str(uuid.uuid4()),
    }
    started, started_cst = now_utc(), now_cst()
    window = {
        "started_at": started, "ended_at": "", "started_at_cst": started_cst, "ended_at_cst": "",
        "sut_sha": env.get("B030_SUT_SHA"), "sut_branch": env.get("B030_SUT_BRANCH"),
        "db": env.get("B030_DB_NAME"), "base": base_url(env),
        "delivery_baseline": f"topic/r2@{env.get('B030_DELIVERY_BASE_SHA', '')}",
        "plan": "docs/iterationB/B-030-本轮验收用例/cases/PB-B04..B07.md, concurrency/SEQ.md, execution/B033.md",
        "git_ops": "local-only; no commit/push during execution",
    }
    results = []
    for ac, fn in CHECKS.items():
        if args.only and ac != args.only:
            continue
        print(f"--- {ac}", flush=True)
        try:
            r = fn(CTX)
        except Exception:
            r = {"ac": ac, "pb": ac.split("-")[1], "title": "", "status": "BLOCKED",
                 "conjuncts": [], "conjunct_count": 0, "failed_conjuncts": [], "deferred_conjuncts": [],
                 "evidence": {"traceback": traceback.format_exc()}}
        results.append(r)
        write_json(CASES / f"{ac}.json", r)
        print(f"    {r['status']} conjuncts={r['conjunct_count']}", flush=True)
        try:
            reset(env)
        except Exception:
            pass
    window["ended_at"], window["ended_at_cst"] = now_utc(), now_cst()
    acs = [r for r in results if r["ac"].startswith("PB-")]
    summary = {
        "task": "B-033", "execution_window": window,
        "totals": {
            "acs": len(acs),
            "pass": sum(1 for r in acs if r["status"].startswith("PASS")),
            "fail": sum(1 for r in acs if r["status"] == "FAIL"),
            "blocked": sum(1 for r in acs if r["status"] == "BLOCKED"),
            "conjuncts": sum(r["conjunct_count"] for r in results),
            "failed_conjuncts": sum(len(r["failed_conjuncts"]) for r in results),
        },
        "acs": [{"ac": r["ac"], "status": r["status"], "conjuncts": r["conjunct_count"],
                 "failed": r["failed_conjuncts"], "deferred": r["deferred_conjuncts"]} for r in results],
    }
    write_json(EVID / "results.json", summary)
    (EVID / "results.md").write_text(markdown(results, window), encoding="utf-8")
    print(json.dumps(summary["totals"], ensure_ascii=False))
    return 0 if summary["totals"]["fail"] == 0 and summary["totals"]["blocked"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
