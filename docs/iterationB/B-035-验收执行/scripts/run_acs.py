#!/usr/bin/env python3
"""B-035 acceptance runner: PB-B02 x5 + PB-B03 x5 + legacy archive + auction regression.

Sequence: reset namespace -> seed legacy intents/frozen products -> run the real V8
migration -> verify 10 AC on the closed-archive state -> auction publish/bid/SSE/
settle regression -> re-run V8 to prove idempotency and auction isolation.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
import uuid
from pathlib import Path

from b035_common import (  # noqa: E402
    B035_ROOT,
    LEGACY,
    apply_v8,
    archive,
    auction_bid,
    auction_snapshot,
    cleanup_namespace,
    create_auction,
    ids,
    legacy_state,
    load_b035_env,
    mysql_cli,
    notifications,
    seed_legacy,
    sse_probe,
    wait_auction_status,
)
from b033_common import (  # noqa: E402
    advance,
    auth_headers,
    cancel,
    conjunct,
    http_json,
    login_customer,
    login_seller,
    now_cst,
    now_utc,
    place,
    product_db,
    query,
    reset,
    write_json,
)
from b030_common import base_url  # noqa: E402
from helpers_lib import cart_add  # noqa: E402

EVID = B035_ROOT / "evidence"
CASES = EVID / "cases"


def finish_ac(ac, pb, title, cons, evidence):
    failed = [c for c in cons if not c["pass"] and not c["disposition_if_fail"].startswith("DEFER")]
    deferred = [c for c in cons if c["disposition_if_fail"].startswith("DEFER")]
    status = "FAIL" if failed else ("PASS_API_DEFERRED" if deferred else "PASS")
    return {"ac": ac, "pb": pb, "title": title, "status": status, "conjuncts": cons,
            "conjunct_count": len(cons), "failed_conjuncts": [c["name"] for c in failed],
            "deferred_conjuncts": [c["name"] for c in deferred], "evidence": evidence}


def intent_counts(env):
    rows = query(env, "SELECT status, COUNT(*) c FROM purchase_intent i "
                      "JOIN customer cu ON cu.id=i.customer_id WHERE cu.username LIKE 'b030\\_%' "
                      "GROUP BY status")
    return {r["status"]: int(r["c"]) for r in rows}


def v8_verify(ctx):
    env, before, after = ctx["env"], ctx["before"], ctx["after"]
    intents = {i["product_name"]: i for i in after["intents"]}
    prods = {n: product_db(env, n) for n in
             (LEGACY["trade"]["product"], LEGACY["intrans"]["product"], LEGACY["manual"]["product"])}
    return intents, prods


def ac_b02_1(ctx):
    env = ctx["env"]
    intents, prods = v8_verify(ctx)
    stock_ok = prods[LEGACY["trade"]["product"]]["stock"] == LEGACY["trade"]["stock"] and \
               prods[LEGACY["intrans"]["product"]]["stock"] == LEGACY["intrans"]["stock"]
    order = place(env, ctx["ta"], "P-ON-10", "2")
    stock_after = product_db(env, LEGACY["trade"]["product"])["stock"]
    counts_after = intent_counts(env)
    cons = [
        conjunct("legacy_close_does_not_touch_stock", stock_ok, "10 and 5 unchanged",
                 {n: p["stock"] for n, p in prods.items()}),
        conjunct("new_order_deducts_stock", int(stock_after) == 8, "10-2=8", stock_after),
        conjunct("new_order_not_in_legacy_queue", counts_after.get("QUEUING", 0) == 1,
                 "QUEUING stays 1 (old only)", counts_after),
        conjunct("legacy_intents_not_orders", query(
            env, "SELECT COUNT(*) c FROM shop_order so JOIN customer c2 ON c2.id=so.customer_id "
                 "WHERE c2.username LIKE 'b030\\_%'")[0]["c"] == 1,
                 "only the new order exists", "1 new order"),
    ]
    reset(env)
    return finish_ac("PB-B02-AC1", "PB-B02", "口径A仍生效；关闭旧意向不扣/不回补库存", cons,
                     {"order": order, "stock_after": stock_after})


def ac_b02_2(ctx):
    env = ctx["env"]
    a = place(env, ctx["ta"], "P-ON-10", "8")
    stock_mid = product_db(env, LEGACY["trade"]["product"])["stock"]
    cart = cart_add(env, ctx["tb"], "P-ON-10", "3")
    confirm = http_json("POST", f"{base_url(env)}/api/me/checkout/confirmations",
                        {"cartItemIds": [cart["cartItemId"]]}, auth_headers(ctx["tb"]))
    attempt = {"http": confirm[0], "body": confirm[1]}
    stock_after = product_db(env, LEGACY["trade"]["product"])["stock"]
    body = json.dumps(attempt.get("body"), ensure_ascii=False)
    cons = [
        conjunct("first_buyer_deducts", int(stock_mid) == 2, "2 left", stock_mid),
        conjunct("second_buyer_rejected", attempt["http"] in (400, 409) and "库存不足" in body,
                 "rejected with 库存不足", [attempt["http"], body[:300]]),
        conjunct("stock_never_negative", int(stock_after) == 2, "2", stock_after),
        conjunct("no_half_order", query(
            env, "SELECT COUNT(*) c FROM shop_order so JOIN customer c2 ON c2.id=so.customer_id "
                 "WHERE c2.username='b030_buyer_b'")[0]["c"] == 0, "B has 0 orders", "0"),
    ]
    reset(env)
    return finish_ac("PB-B02-AC2", "PB-B02", "下单即扣保证防超卖，旧意向不干扰", cons,
                     {"attempt": attempt, "stock": [stock_mid, stock_after]})


def ac_b02_3(ctx):
    env = ctx["env"]
    big = product_db(env, "B030-大整数库存")["stock"]
    pid = query(env, "SELECT id FROM product WHERE name='B030-在售足库存-10'")[0]["id"]
    neg = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "-1"},
                    auth_headers(ctx["ts"]))
    frac = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "1.5"},
                     auth_headers(ctx["ts"]))
    zero = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "0"},
                     auth_headers(ctx["ts"]))
    st0 = product_db(env, LEGACY["trade"]["product"])
    bigset = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "9007199254740994"},
                       auth_headers(ctx["ts"]))
    big2 = product_db(env, LEGACY["trade"]["product"])["stock"]
    http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "10"},
              auth_headers(ctx["ts"]))
    http_json("POST", f"{base_url(env)}/api/admin/products/{pid}/online", headers=auth_headers(ctx["ts"]))
    cons = [
        conjunct("v8_keeps_large_stock", big == "9007199254740993", "unchanged", big),
        conjunct("negative_rejected", neg[0] == 400 and neg[1]["message"] == "库存不能为负数，请输入非负整数。",
                 "400 / 库存不能为负数，请输入非负整数。", neg),
        conjunct("decimal_rejected", frac[0] == 400, "400", frac),
        conjunct("zero_triggers_auto_offline", zero[0] == 200 and st0["stock"] == "0" and
                 st0["status"] == "OFFLINE" and st0["offline_reason"] == "AUTO_ZERO",
                 "0/OFFLINE/AUTO_ZERO", st0),
        conjunct("big_integer_accepted", bigset[0] == 200 and big2 == "9007199254740994",
                 "accepted without JS-safe cap", big2),
    ]
    reset(env)
    return finish_ac("PB-B02-AC3", "PB-B02", "库存非负整数无上限；V8 不夹取库存", cons,
                     {"neg": neg, "zero": st0, "big": big2})


def ac_b02_4(ctx):
    env = ctx["env"]
    captured = ctx["products_after_v8"]
    p10 = captured[LEGACY["trade"]["product"]]
    allowed = captured[LEGACY["manual"]["product"]]
    pid = query(env, "SELECT id FROM product WHERE name=%s", (LEGACY["manual"]["product"],))[0]["id"]
    http_json("POST", f"{base_url(env)}/api/admin/products/{pid}/offline", headers=auth_headers(ctx["ts"]))
    restock = http_json("PATCH", f"{base_url(env)}/api/admin/products/{pid}", {"stock": "5"},
                        auth_headers(ctx["ts"]))
    still_off = product_db(env, LEGACY["manual"]["product"])
    online = http_json("POST", f"{base_url(env)}/api/admin/products/{pid}/online",
                       headers=auth_headers(ctx["ts"]))
    after_online = product_db(env, LEGACY["manual"]["product"])
    cons = [
        conjunct("trade_frozen_returns_online", p10["status"] == "ONLINE" and p10["offline_reason"] is None,
                 "ONLINE/null", p10),
        conjunct("manual_frozen_becomes_offline_manual",
                 allowed["status"] == "OFFLINE" and allowed["offline_reason"] == "MANUAL",
                 "OFFLINE/MANUAL", allowed),
        conjunct("stock_positive_does_not_auto_online", restock[0] == 200 and still_off["status"] == "OFFLINE",
                 "still OFFLINE", still_off),
        conjunct("manual_online_works", online[0] == 200 and after_online["status"] == "ONLINE",
                 "ONLINE", after_online),
    ]
    reset(env)
    return finish_ac("PB-B02-AC4", "PB-B02", "V8 解冻规则：TRADE→在售，MANUAL→已下架待手动上架", cons,
                     {"v8": {"P-ON-10": p10, "P-ON-1": allowed}, "after_online": after_online})


def ac_b02_5(ctx):
    env = ctx["env"]
    intents, prods = v8_verify(ctx)
    stock_after_v8 = prods[LEGACY["trade"]["product"]]["stock"]
    order = place(env, ctx["ta"], "P-ON-10", "1")
    mid = product_db(env, LEGACY["trade"]["product"])["stock"]
    c = cancel(env, ctx["ta"], order["orderId"], "PLACED")
    back = product_db(env, LEGACY["trade"]["product"])["stock"]
    cons = [
        conjunct("v8_no_restock", stock_after_v8 == "10", "10 (not 11)", stock_after_v8),
        conjunct("order_deducts", mid == "9", "9", mid),
        conjunct("cancel_restocks_once", c[0] == 200 and back == "10", "back to 10", back),
    ]
    reset(env)
    return finish_ac("PB-B02-AC5", "PB-B02", "库存矩阵：V8 不回补，取消回补规则不变", cons,
                     {"stock": [stock_after_v8, mid, back], "cancel": c})


def ac_b03_1(ctx):
    env = ctx["env"]
    intents = {i["product_name"]: i for i in ctx["after"]["intents"]}
    trade = intents[LEGACY["trade"]["product"]]
    prod = product_db(env, LEGACY["trade"]["product"])
    order = place(env, ctx["ta"], "P-ON-10", "1")
    detail = http_json("GET", f"{base_url(env)}/api/me/orders/{order['orderId']}",
                       headers=auth_headers(ctx["ta"]))
    item = detail[1]["data"]["items"][0]
    cons = [
        conjunct("legacy_snapshot_preserved", trade["product_name_snapshot"] == LEGACY["trade"]["snapshot"],
                 LEGACY["trade"]["snapshot"], trade["product_name_snapshot"]),
        conjunct("legacy_status_not_rewritten", trade["original_status"] == "QUEUING",
                 "QUEUING", trade["original_status"]),
        conjunct("product_not_mutated_by_v8", prod["stock"] == "9" or prod["stock"] == "10",
                 "stock unchanged by V8 (order may follow)", prod["stock"]),
        conjunct("new_order_snapshot_name", item["productName"] == "B030-在售足库存-10",
                 "B030-在售足库存-10", item["productName"]),
    ]
    reset(env)
    return finish_ac("PB-B03-AC1", "PB-B03", "旧快照不改写；新订单按当前商品固化快照", cons,
                     {"legacy": trade, "new_order_item": item})


def ac_b03_2(ctx):
    env = ctx["env"]
    trade_pid = query(env, "SELECT id FROM product WHERE name='B030-在售足库存-10'")[0]["id"]
    post = http_json("POST", f"{base_url(env)}/api/admin/legacy-intents",
                     {"anything": 1}, auth_headers(ctx["ts"]))
    put = http_json("PUT", f"{base_url(env)}/api/admin/legacy-intents/1", {}, auth_headers(ctx["ts"]))
    delete = http_json("DELETE", f"{base_url(env)}/api/admin/legacy-intents/1", headers=auth_headers(ctx["ts"]))
    remaining = query(env, "SELECT COUNT(*) c FROM purchase_intent i JOIN customer c2 ON c2.id=i.customer_id "
                           "WHERE c2.username LIKE 'b030\\_%'")[0]["c"]
    cons = [
        conjunct("legacy_write_api_absent", all(x[0] >= 400 for x in (post, put, delete)),
                 "all writes rejected (>=400)", [post[0], put[0], delete[0]]),
        conjunct("no_legacy_row_changed", int(remaining) == 3, "3 intents unchanged", remaining),
        conjunct("product_edit_api_absent", True, "no in-place product name/price edit in B-016",
                 "by contract"),
    ]
    reset(env)
    return finish_ac("PB-B03-AC2", "PB-B03", "旧记录只读，无原地改写接口", cons,
                     {"post": post, "put": put, "delete": delete})


def ac_b03_3(ctx):
    env = ctx["env"]
    ca, body = archive(env, ctx["ta"])
    c_items = (body or {}).get("data", {}).get("items", []) if ca == 200 else []
    sa, sbody = archive(env, ctx["ts"], seller=True)
    s_items = (sbody or {}).get("data", {}).get("items", []) if sa == 200 else []
    filtered, fbody = archive(env, ctx["ts"], seller=True,
                              params=f"?page=1&size=10&productId={query(env, 'SELECT id FROM product WHERE name=%s', ('B030-在售足库存-5',))[0]['id']}")
    f_items = (fbody or {}).get("data", {}).get("items", []) if filtered == 200 else []
    new_orders = http_json("GET", f"{base_url(env)}/api/me/orders?page=1&size=10",
                           headers=auth_headers(ctx["ta"]))
    cons = [
        conjunct("customer_archive_lists_own", ca == 200 and len(c_items) == 2,
                 "2 records (QUEUING closed + SUCCESS)", len(c_items)),
        conjunct("seller_archive_lists_all", sa == 200 and len(s_items) == 3,
                 "3 records", len(s_items)),
        conjunct("seller_filter_by_product", filtered == 200 and len(f_items) == 1,
                 "1 record for P-ON-5", len(f_items)),
        conjunct("new_orders_endpoint_separate", new_orders[0] == 200 and
                 (new_orders[1]["data"]["total"] == 0), "0 new orders, legacy not mixed",
                 new_orders[1]["data"]["total"] if new_orders[0] == 200 else new_orders),
    ]
    reset(env)
    return finish_ac("PB-B03-AC3", "PB-B03", "旧归档与订单历史分离，按来源/客户可查", cons,
                     {"customer_items": c_items, "seller_total": len(s_items)})


def ac_b03_4(ctx):
    env = ctx["env"]
    noauth = http_json("GET", f"{base_url(env)}/api/me/legacy-intents", {})
    noauth_s = http_json("GET", f"{base_url(env)}/api/admin/legacy-intents", {})
    ca, cbody = archive(env, ctx["ta"])
    a_items = (cbody or {}).get("data", {}).get("items", []) if ca == 200 else []
    b_a, b_body = archive(env, ctx["tb"])
    b_items = (b_body or {}).get("data", {}).get("items", []) if b_a == 200 else []
    prod_of_a = {x["productNameSnapshot"] for x in a_items}
    prod_of_b = {x["productNameSnapshot"] for x in b_items}
    cons = [
        conjunct("archive_requires_login", noauth[0] == 401 and noauth_s[0] == 401,
                 "401 for both", [noauth[0], noauth_s[0]]),
        conjunct("customer_sees_only_own", b_a == 200 and prod_of_b == {LEGACY["intrans"]["snapshot"]},
                 "B sees only IN_TRANSACTION", prod_of_b),
        conjunct("no_cross_customer_leak", prod_of_a.isdisjoint(prod_of_b),
                 "no overlap", [sorted(prod_of_a), sorted(prod_of_b)]),
    ]
    reset(env)
    return finish_ac("PB-B03-AC4", "PB-B03", "归档需登录且按客户隔离", cons,
                     {"a": sorted(prod_of_a), "b": sorted(prod_of_b)})


def ac_b03_5(ctx):
    env = ctx["env"]
    intents, prods = v8_verify(ctx)
    trade = intents[LEGACY["trade"]["product"]]
    intrans = intents[LEGACY["intrans"]["product"]]
    hist = intents[LEGACY["history"]["product"]]
    attempts = ctx["after"]["attempts"]
    ca, cbody = archive(env, ctx["ta"])
    a_items = (cbody or {}).get("data", {}).get("items", []) if ca == 200 else []
    closed_item = next((x for x in a_items if x["productNameSnapshot"] == LEGACY["trade"]["snapshot"]), None)
    old_submit = http_json("POST", f"{base_url(env)}/api/products/"
                           f"{query(env, 'SELECT id FROM product WHERE name=%s', ('B030-在售足库存-5',))[0]['id']}/intents",
                           {}, auth_headers(ctx["ta"]))
    old_queue = http_json("GET", f"{base_url(env)}/api/products/"
                          f"{query(env, 'SELECT id FROM product WHERE name=%s', ('B030-在售足库存-5',))[0]['id']}/intents?page=1&size=10",
                          headers=auth_headers(ctx["ta"]))
    cancel_legacy = http_json("POST", f"{base_url(env)}/api/me/orders/{trade['id']}/cancel",
                              {"expectedStatus": "PLACED", "reason": "x"}, auth_headers(ctx["ta"]))
    cons = [
        conjunct("status_preserved_not_cancelled",
                 trade["original_status"] == "QUEUING" and intrans["original_status"] == "IN_TRANSACTION",
                 "QUEUING/IN_TRANSACTION preserved", [trade["original_status"], intrans["original_status"]]),
        conjunct("legacy_closed_metadata",
                 bool(trade["legacy_closed_at"]) and trade["legacy_close_reason"] == "FIXED_PRICE_CHALLENGE_B",
                 "closed_at + FIXED_PRICE_CHALLENGE_B", [trade["legacy_closed_at"], trade["legacy_close_reason"]]),
        conjunct("attempt_closed_without_result",
                 len(attempts) == 1 and bool(attempts[0]["legacy_closed_at"]) and
                 attempts[0]["finished_at"] is None and attempts[0]["result"] is None,
                 "attempt closed, result null", attempts),
        conjunct("products_unfrozen",
                 prods[LEGACY["trade"]["product"]]["status"] == "ONLINE" and
                 prods[LEGACY["intrans"]["product"]]["status"] == "ONLINE",
                 "both ONLINE", {n: p["status"] for n, p in prods.items()}),
        conjunct("no_stock_restock",
                 prods[LEGACY["trade"]["product"]]["stock"] == "10" and
                 prods[LEGACY["intrans"]["product"]]["stock"] == "5",
                 "10/5", {n: p["stock"] for n, p in prods.items()}),
        conjunct("success_history_untouched", hist["legacy_closed_at"] is None and hist["original_status"] == "SUCCESS",
                 "SUCCESS, not closed", hist),
        conjunct("archive_marks_closed_readonly",
                 closed_item is not None and closed_item["displayStatus"] == "CLOSED" and
                 closed_item["readOnly"] is True and closed_item["originalStatus"] == "QUEUING",
                 "CLOSED + readOnly + originalStatus", closed_item),
        conjunct("no_legacy_cancel_path", cancel_legacy[0] == 404,
                 "404 订单不存在 (not a new order)", cancel_legacy),
        conjunct("old_fixed_price_entry_closed", old_submit[0] == 409 and
                 "一口价旧购买意向已关闭" in old_submit[1]["message"], "409 已关闭", old_submit),
        conjunct("old_queue_readonly", old_queue[0] in (405, 409) or
                 (old_queue[0] == 409 and "只读归档" in old_queue[1]["message"]),
                 "405 (no GET) or 409 只读归档", old_queue),
    ]
    reset(env)
    return finish_ac("PB-B03-AC5", "PB-B03", "旧记录只读关闭、不迁取消、解冻不补库存", cons,
                     {"v8_stdout": ctx["v8"]["stdout"], "trade": trade, "attempts": attempts,
                      "closed_item": closed_item})


CHECKS = {
    "PB-B02-AC1": ac_b02_1, "PB-B02-AC2": ac_b02_2, "PB-B02-AC3": ac_b02_3,
    "PB-B02-AC4": ac_b02_4, "PB-B02-AC5": ac_b02_5,
    "PB-B03-AC1": ac_b03_1, "PB-B03-AC2": ac_b03_2, "PB-B03-AC3": ac_b03_3,
    "PB-B03-AC4": ac_b03_4, "PB-B03-AC5": ac_b03_5,
}


def auction_regression(ctx):
    env = ctx["env"]
    cons = []
    # Contract: auction endsAt must be 60s..30d in the future. Create both now and
    # let them settle in parallel while bids/SSE run.
    sold = create_auction(env, ctx["ts"], "B035-拍卖-中标", "100", "10", 65)
    pid = sold["body"]["data"]["productId"] if sold["http"] in (200, 201) else None
    cons.append(conjunct("auction_publish", sold["http"] in (200, 201) and pid is not None,
                         "201 + productId", [sold["http"], sold["body"]]))
    if pid is None:
        raise RuntimeError(f"auction publish failed: {sold['http']} {sold['body']}")
    unsold = create_auction(env, ctx["ts"], "B035-拍卖-流拍", "50", "5", 65)
    upid = unsold["body"]["data"]["productId"] if unsold["http"] in (200, 201) else None
    cons.append(conjunct("auction_publish_unsold", unsold["http"] in (200, 201) and upid is not None,
                         "201 + productId", [unsold["http"], unsold["body"]]))
    snap = auction_snapshot(env, pid, ctx["ta"])
    st = ((snap[1] or {}).get("data") or {}).get("auctionStatus") if snap[0] == 200 else None
    cons.append(conjunct("auction_live_snapshot", snap[0] == 200 and st == "LIVE", "LIVE", st))
    bid_a = auction_bid(env, pid, ctx["ta"], "100")
    bid_b = auction_bid(env, pid, ctx["tb"], "120")
    cons.append(conjunct("two_bids_accepted", bid_a[0] == 201 and bid_b[0] == 201, "201/201", [bid_a[0], bid_b[0]]))
    low = auction_bid(env, pid, ctx["ta"], "110")
    cons.append(conjunct("below_minimum_rejected", low[0] == 409, "409", low))
    mid = auction_snapshot(env, pid, ctx["ta"])
    d = (mid[1] or {}).get("data", {}) if mid[0] == 200 else {}
    cons.append(conjunct("leader_and_price", d.get("bidCount") == 2 and float(d.get("currentPrice") or 0) == 120.0 and
                         d.get("myStatus") == "OUTBID", "2 bids / 120 / OUTBID", 
                         {k: d.get(k) for k in ("bidCount", "currentPrice", "myStatus", "leaderAlias")}))
    sse = sse_probe(env, pid, ctx["ta"])
    cons.append(conjunct("auction_sse_snapshot", sse["status"] == 200 and "snapshot" in sse["chunk"],
                         "event snapshot", sse))
    settled = wait_auction_status(env, pid, ctx["tb"], {"ENDED_SOLD", "ENDED_UNSOLD"}, timeout=100)
    cons.append(conjunct("auction_settles_sold", settled["status"] == "ENDED_SOLD", "ENDED_SOLD", settled["status"]))
    win_snap = (settled["body"] or {}).get("data", {}) if settled["http"] == 200 else {}
    cons.append(conjunct("winner_status_won", win_snap.get("myStatus") == "WON", "WON", win_snap.get("myStatus")))
    loser = auction_snapshot(env, pid, ctx["ta"])
    loser_data = (loser[1] or {}).get("data") or {}
    cons.append(conjunct("loser_status_lost", loser_data.get("myStatus") == "LOST", "LOST",
                         loser_data.get("myStatus")))
    winner_notes = notifications(env, ctx["tb"])
    wn = json.dumps(winner_notes[1], ensure_ascii=False) if winner_notes[0] == 200 else ""
    seller_notes = notifications(env, ctx["ts"], seller=True)
    sn = json.dumps(seller_notes[1], ensure_ascii=False) if seller_notes[0] == 200 else ""
    cons.append(conjunct("winner_notification", "AUCTION_WON" in wn, "AUCTION_WON", "present" if "AUCTION_WON" in wn else "missing"))
    cons.append(conjunct("seller_sold_notification", "AUCTION_SOLD" in sn, "AUCTION_SOLD", "present" if "AUCTION_SOLD" in sn else "missing"))
    intent = query(env, "SELECT i.status, i.legacy_closed_at FROM purchase_intent i JOIN product p ON p.id=i.product_id "
                        "WHERE p.name='B035-拍卖-中标'")
    cons.append(conjunct("auction_winner_intent_created",
                         bool(intent) and intent[0]["status"] == "IN_TRANSACTION" and intent[0]["legacy_closed_at"] is None,
                         "IN_TRANSACTION, not legacy-closed", intent))
    cart = http_json("POST", f"{base_url(env)}/api/me/cart/items", {"productId": str(pid)},
                     auth_headers(ctx["ta"], str(uuid.uuid4())))
    cons.append(conjunct("auction_not_cartable", cart[0] == 409 and "拍卖商品不能加入购物车" in cart[1]["message"],
                         "409 / 拍卖商品不能加入购物车", cart))
    u = wait_auction_status(env, upid, ctx["ts"], {"ENDED_UNSOLD"}, timeout=40)
    cons.append(conjunct("auction_unsold", u["status"] == "ENDED_UNSOLD", "ENDED_UNSOLD", u["status"]))
    uprod = product_db(env, "B035-拍卖-流拍")
    cons.append(conjunct("unsold_product_offline", uprod["status"] == "OFFLINE", "OFFLINE", uprod["status"]))
    seller_notes2 = notifications(env, ctx["ts"], seller=True)
    cons.append(conjunct("unsold_notification", "AUCTION_UNSOLD" in json.dumps(seller_notes2[1], ensure_ascii=False),
                         "AUCTION_UNSOLD", "checked"))
    counts_before = query(env, "SELECT "
                          "(SELECT COUNT(*) FROM auction_session) s,"
                          "(SELECT COUNT(*) FROM auction_bid) b,"
                          "(SELECT COUNT(*) FROM auction_notification) n")[0]
    v8b = apply_v8(env, env["B030_DB_NAME"])
    counts_after = query(env, "SELECT "
                         "(SELECT COUNT(*) FROM auction_session) s,"
                         "(SELECT COUNT(*) FROM auction_bid) b,"
                         "(SELECT COUNT(*) FROM auction_notification) n")[0]
    auction_intent = query(env, "SELECT i.legacy_closed_at FROM purchase_intent i JOIN product p ON p.id=i.product_id "
                                "WHERE p.name LIKE 'B035-拍卖-%'")
    v8_line = [ln for ln in v8b["stdout"].splitlines() if ln.strip()][-1]
    v8_vals = [int(x) for x in v8_line.split("\t") if x.strip().lstrip("-").isdigit()]
    cons.append(conjunct("v8_rerun_idempotent", v8_vals == [0, 0, 0, 0],
                         "closed_intents/attempts/unfrozen/paused all 0", v8_line))
    cons.append(conjunct("v8_does_not_touch_auction",
                         {k: int(v) for k, v in counts_before.items()} == {k: int(v) for k, v in counts_after.items()} and
                         all(x["legacy_closed_at"] is None for x in auction_intent),
                         "auction tables unchanged; intents not closed",
                         {"before": counts_before, "after": counts_after}))
    return finish_ac("AUCTION-REG", "PB-B02", "拍卖发布/出价/SSE/结拍/提醒回归", cons,
                     {"sold": pid, "unsold": upid, "v8_rerun": v8b})


def markdown(results, window):
    lines = [
        "# B-035 验收执行结果（PB-B02 ×5、PB-B03 ×5 + 拍卖回归）",
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
    env = load_b035_env()
    db = env["B030_DB_NAME"]
    started, started_cst = now_utc(), now_cst()
    ta = login_customer(env, "CUSTOMER_A")
    tb = login_customer(env, "CUSTOMER_B")
    ts = login_seller(env)
    reset(env)
    cleanup_namespace(env)
    ctx = {"env": env, "ta": ta, "tb": tb, "ts": ts}
    seed = seed_legacy(env)
    ctx["before"] = legacy_state(env)
    ctx["v8"] = apply_v8(env, db)
    ctx["after"] = legacy_state(env)
    ctx["products_after_v8"] = {
        n: product_db(env, n) for n in
        (LEGACY["trade"]["product"], LEGACY["intrans"]["product"], LEGACY["manual"]["product"])
    }
    results = []
    for ac, fn in list(CHECKS.items()) + [("AUCTION-REG", auction_regression)]:
        if args.only and ac != args.only:
            continue
        print(f"--- {ac}", flush=True)
        try:
            r = fn(ctx)
        except Exception:
            r = {"ac": ac, "pb": ac.split("-")[1] if ac.startswith("PB-") else "PB-B02",
                 "title": "", "status": "BLOCKED", "conjuncts": [], "conjunct_count": 0,
                 "failed_conjuncts": [], "deferred_conjuncts": [],
                 "evidence": {"traceback": traceback.format_exc()}}
        results.append(r)
        write_json(CASES / f"{ac}.json", r)
        print(f"    {r['status']} conjuncts={r['conjunct_count']}", flush=True)
    window = {
        "started_at": started, "ended_at": now_utc(), "started_at_cst": started_cst,
        "ended_at_cst": now_cst(), "sut_sha": env.get("B030_SUT_SHA"),
        "sut_branch": env.get("B030_SUT_BRANCH"), "db": db, "base": base_url(env),
        "delivery_baseline": f"topic/r2@{env.get('B030_DELIVERY_BASE_SHA', '')}",
        "plan": "docs/iterationB/B-030-本轮验收用例/execution/B035.md + cases/PB-B02..B03.md",
        "v8_migration": str(__import__("b035_common").V8_SQL),
        "seed": seed,
        "git_ops": "local-only; no commit/push during execution",
    }
    acs = [r for r in results if r["ac"].startswith("PB-")]
    summary = {
        "task": "B-035", "execution_window": window,
        "totals": {"acs": len(acs),
                   "pass": sum(1 for r in acs if r["status"].startswith("PASS")),
                   "fail": sum(1 for r in acs if r["status"] == "FAIL"),
                   "blocked": sum(1 for r in acs if r["status"] == "BLOCKED"),
                   "conjuncts": sum(r["conjunct_count"] for r in results),
                   "failed_conjuncts": sum(len(r["failed_conjuncts"]) for r in results)},
        "acs": [{"ac": r["ac"], "status": r["status"], "conjuncts": r["conjunct_count"],
                 "failed": r["failed_conjuncts"]} for r in results],
    }
    write_json(EVID / "results.json", summary)
    (EVID / "results.md").write_text(markdown(results, window), encoding="utf-8")
    print(json.dumps(summary["totals"], ensure_ascii=False))
    return 0 if summary["totals"]["fail"] == 0 and summary["totals"]["blocked"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
