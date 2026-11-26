#!/usr/bin/env python3
"""B-034 acceptance runner: PB-B14 (7 AC) + PB-B15 (6 AC) = 13 AC.

Executes the B-030 plan (cases/PB-B14.md, PB-B15.md, concurrency/SEQ.md) against a
live SUT and records per-AC conjunct evidence. No AC is marked PASS without an
executed HTTP+DB observation.

Usage:
  set PYTHONPATH=<workspace>/_pydeps
  python scripts/run_acs.py [--only PB-B14-AC1]
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
import uuid
from pathlib import Path

from b034_common import (  # noqa: E402
    B034_ROOT,
    add_line,
    cleanup_missing_row,
    conjunct,
    counts,
    delete_line,
    favorite_rows,
    insert_missing_product_cart_row,
    load_b034_env,
    login_customer,
    login_seller,
    move,
    move_receipts,
    now_cst,
    now_utc,
    offline_product,
    product_id,
    product_snapshot,
    query,
    race,
    reset,
    set_stock,
    write_json,
)
from b030_common import http_json, base_url, auth_headers  # noqa: E402

EVID = B034_ROOT / "evidence"
CASES = EVID / "cases"


def msg(res) -> str:
    body = res.get("body") if isinstance(res, dict) else None
    return (body or {}).get("message", "") if isinstance(body, dict) else ""


def code_of(res) -> int | None:
    body = res.get("body") if isinstance(res, dict) else None
    return (body or {}).get("code") if isinstance(body, dict) else None


def no_order(ctx) -> bool:
    return counts(ctx["env"])["orders"] == 0


def same_stock(before: dict, after: dict) -> bool:
    return all(before[k]["stock"] == after[k]["stock"] for k in before) and set(before) == set(after)


def finish(ac: str, pb: str, title: str, conjuncts: list[dict], evidence: dict, ui_deferred: bool = False) -> dict:
    failed = [c for c in conjuncts if not c["pass"] and c["disposition_if_fail"] != "DEFER_TO_B036"]
    deferred = [c for c in conjuncts if c["disposition_if_fail"] == "DEFER_TO_B036"]
    if failed:
        status = "FAIL"
    elif deferred:
        status = "PASS_API_UI_DEFERRED"
    else:
        status = "PASS"
    return {
        "ac": ac, "pb": pb, "title": title, "status": status,
        "conjuncts": conjuncts, "conjunct_count": len(conjuncts),
        "failed_conjuncts": [c["name"] for c in failed],
        "deferred_conjuncts": [c["name"] for c in deferred],
        "evidence": evidence,
    }


# ---------------------------------------------------------------- PB-B14


def ac_b14_1(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    before = product_snapshot(env)
    c1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    c2 = add_line(env, ctx["ta"], "P-ON-5", "5")
    res = move(env, ctx["ta"], [c1, c2])
    after = counts(env)
    favs = favorite_rows(env)
    snap = product_snapshot(env)
    cons = [
        conjunct("http_and_message", res["http"] == 200 and msg(res) == "已收藏 2 件商品",
                 "200 / 已收藏 2 件商品", [res["http"], msg(res)]),
        conjunct("moved_line_count_is_line_count", res["body"]["data"]["movedLineCount"] == 2,
                 "movedLineCount=2 (qty5 line counts once)", res["body"]["data"]),
        conjunct("cart_rows_removed", after["cart"] == 0, "cart=0", after["cart"]),
        conjunct("favorites_two_distinct_rows", len(favs) == 2 and len({f["product_id"] for f in favs}) == 2,
                 "2 favorite rows for 2 products", favs),
        conjunct("qty5_yields_one_favorite", sum(1 for f in favs if f["product_name"] == "B030-在售足库存-5") == 1,
                 "exactly 1 favorite for qty=5 line", favs),
        conjunct("no_order_created", after["orders"] == 0, "orders=0", after["orders"]),
        conjunct("stock_unchanged", same_stock(before, snap), "product stock unchanged", 
                 {"before": before, "after": snap}),
    ]
    return finish("PB-B14-AC1", "PB-B14", "转为收藏是移动，不是复制；N 按行数", cons,
                  {"request": [c1, c2], "response": res["body"]})


def ac_b14_2(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    cb = add_line(env, ctx["tb"], "P-ON-10", "1")
    noauth = http_json("POST", f"{base_url(env)}/api/me/cart/move-to-favorites",
                       {"cartItemIds": [cb]}, {"Idempotency-Key": "b034-noauth"})
    invalid = move(env, "invalid.token.value", [cb])
    foreign = move(env, ctx["ta"], [cb])
    ca = add_line(env, ctx["ta"], "P-ON-10", "1")
    mixed = move(env, ctx["ta"], [ca, cb])
    seller = move(env, ctx["ts"], [cb])
    rows = counts(env)
    cons = [
        conjunct("anonymous_401_please_login", noauth[0] == 401 and noauth[1]["message"] == "请先登录",
                 "401 / 请先登录", list(noauth)),
        conjunct("expired_401_relogin", invalid["http"] == 401 and msg(invalid) == "请重新登录",
                 "401 / 请重新登录", [invalid["http"], msg(invalid)]),
        conjunct("foreign_row_403", foreign["http"] == 403 and msg(foreign) == "无权操作",
                 "403 / 无权操作", [foreign["http"], msg(foreign)]),
        conjunct("mixed_foreign_whole_batch_rejected", mixed["http"] == 403 and msg(mixed) == "无权操作",
                 "403 / 无权操作", [mixed["http"], msg(mixed)]),
        conjunct("seller_403_no_permission", seller["http"] == 403 and msg(seller) == "无此权限",
                 "403 / 无此权限", [seller["http"], msg(seller)]),
        conjunct("no_data_changed", rows["cart"] == 2 and rows["favorites"] == 0,
                 "cart=2, favorites=0 after all rejects", rows),
    ]
    return finish("PB-B14-AC2", "PB-B14", "登录与归属校验；商家无代操作权限", cons,
                  {"responses": {"anonymous": noauth, "invalid": invalid, "foreign": foreign,
                                 "mixed": mixed, "seller": seller}})


def ac_b14_3(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    c1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    c2 = add_line(env, ctx["ta"], "P-ON-5", "1")
    empty = move(env, ctx["ta"], [])
    partial = move(env, ctx["ta"], [c1])
    rows_partial = query(env, "SELECT ci.id, ci.quantity FROM cart_item ci JOIN customer c ON c.id=ci.customer_id "
                              "WHERE c.username LIKE 'b030\\_%' ORDER BY ci.id")
    reset(env)
    cbig = add_line(env, ctx["ta"], "P-ON-1", "5")
    over = move(env, ctx["ta"], [cbig])
    reset(env)
    o1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    o2 = add_line(env, ctx["ta"], "P-ON-5", "1")
    offline_product(env, ctx["ts"], "P-ON-5")
    offline_only = move(env, ctx["ta"], [o2])
    unselected_offline = move(env, ctx["ta"], [o1])
    rows = counts(env)
    cons = [
        conjunct("empty_selection_400", empty["http"] == 400 and msg(empty) == "请选择商品",
                 "400 / 请选择商品", [empty["http"], msg(empty)]),
        conjunct("partial_selection_leaves_other_row", partial["http"] == 200 and
                 len(rows_partial) == 1 and str(rows_partial[0]["id"]) == str(c2),
                 "moved 1, unselected row kept", {"http": partial["http"], "remaining": rows_partial}),
        conjunct("stock_below_qty_still_movable", over["http"] == 200,
                 "200 (on-sale only; stock<qty allowed)", [over["http"], msg(over)]),
        conjunct("offline_row_rejected", offline_only["http"] == 409 and
                 "商品已下架" in json.dumps(offline_only["body"], ensure_ascii=False),
                 "409 / 商品已下架", [offline_only["http"], offline_only["body"]]),
        conjunct("unselected_offline_row_not_processed", unselected_offline["http"] == 200 and
                 rows["cart"] == 1 and rows["favorites"] == 1,
                 "moved online row; offline row kept", {"http": unselected_offline["http"], "counts": rows}),
    ]
    return finish("PB-B14-AC3", "PB-B14", "可收藏=在售；空选拒绝；未选行不受影响", cons,
                  {"empty": empty["body"], "partial": partial["body"], "over": over["body"],
                   "offline": offline_only["body"], "unselected": unselected_offline["body"]})


def ac_b14_4(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    c1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    c2 = add_line(env, ctx["ta"], "P-ON-5", "5")
    two = move(env, ctx["ta"], [c1, c2])
    reset(env)
    one = add_line(env, ctx["ta"], "P-ON-10", "5")
    single = move(env, ctx["ta"], [one])
    cons = [
        conjunct("two_lines_message_n2", two["http"] == 200 and msg(two) == "已收藏 2 件商品",
                 "已收藏 2 件商品", [two["http"], msg(two)]),
        conjunct("single_line_message_n1", single["http"] == 200 and msg(single) == "已收藏 1 件商品",
                 "已收藏 1 件商品", [single["http"], msg(single)]),
        conjunct("ui_confirm_text", False,
                 "UI 二次确认：所选 N 件商品将从购物车移除并加入收藏（N=行数）",
                 "not executed here; deferred to B-036 real-page run", "DEFER_TO_B036"),
    ]
    return finish("PB-B14-AC4", "PB-B14", "N=所选商品行数；成功提示「已收藏 N 件商品」", cons,
                  {"two": two["body"], "single": single["body"]})


def ac_b14_5(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    pid = product_id("P-ON-10")
    fav = http_json("PUT", f"{base_url(env)}/api/me/favorites/{pid}", headers=auth_headers(ctx["ta"]))
    before = query(env, "SELECT f.id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id "
                        "WHERE c.username='b030_buyer_a' AND f.product_id=%s", (pid,))[0]
    c1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    res = move(env, ctx["ta"], [c1])
    after = query(env, "SELECT f.id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id "
                       "WHERE c.username='b030_buyer_a' AND f.product_id=%s", (pid,))
    cons = [
        conjunct("existing_favorite_move_succeeds", res["http"] == 200 and msg(res) == "已收藏 1 件商品",
                 "200 / 已收藏 1 件商品", [res["http"], msg(res)]),
        conjunct("favorite_not_duplicated", len(after) == 1, "1 row", len(after)),
        conjunct("favorite_time_unchanged", after[0]["created_at"] == before["created_at"],
                 "created_at unchanged", {"before": str(before["created_at"]), "after": str(after[0]["created_at"])}),
        conjunct("cart_row_still_removed", counts(env)["cart"] == 0, "cart=0", counts(env)["cart"]),
    ]
    return finish("PB-B14-AC5", "PB-B14", "已收藏商品再转收藏：保持原收藏、不刷新时间、仍移车", cons,
                  {"favorite": fav[1], "before": str(before["created_at"]), "after": str(after[0]["created_at"])})


def ac_b14_6(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    pid = product_id("P-ON-10")
    http_json("PUT", f"{base_url(env)}/api/me/favorites/{pid}", headers=auth_headers(ctx["ta"]))
    before = query(env, "SELECT f.id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id "
                        "WHERE c.username='b030_buyer_a' AND f.product_id=%s", (pid,))[0]
    c1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    offline_product(env, ctx["ts"], "P-ON-10")
    res = move(env, ctx["ta"], [c1])
    after = query(env, "SELECT f.id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id "
                       "WHERE c.username='b030_buyer_a' AND f.product_id=%s", (pid,))
    rows = counts(env)
    cons = [
        conjunct("offline_product_rejected", res["http"] == 409 and "商品已下架" in json.dumps(res["body"], ensure_ascii=False),
                 "409 / 商品已下架", [res["http"], res["body"]]),
        conjunct("invalid_favorite_not_revived", len(after) == 1 and after[0]["created_at"] == before["created_at"],
                 "existing invalid favorite unchanged", {"count": len(after), "created_at": str(after[0]["created_at"])}),
        conjunct("no_favorite_added", rows["favorites"] == 1, "favorites=1", rows["favorites"]),
        conjunct("cart_row_kept_on_batch_failure", rows["cart"] == 1, "cart=1", rows["cart"]),
    ]
    return finish("PB-B14-AC6", "PB-B14", "仅在售可新建收藏；已有失效收藏不因本次操作转成功", cons,
                  {"response": res["body"], "favorite_before": str(before["created_at"]),
                   "favorite_after": str(after[0]["created_at"])})


def ac_b14_7(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    c1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    c2 = add_line(env, ctx["ta"], "P-ON-5", "1")
    offline_product(env, ctx["ts"], "P-ON-5")
    res = move(env, ctx["ta"], [c1, c2])
    rows = counts(env)
    errs = (res["body"].get("data") or {}).get("errors") if isinstance(res["body"], dict) else None
    cons = [
        conjunct("mixed_batch_rejected", res["http"] == 409, "409", [res["http"], msg(res)]),
        conjunct("per_item_offline_reason", bool(errs) and any(e.get("message") == "商品已下架" for e in errs),
                 "errors[] contains 商品已下架", errs),
        conjunct("whole_batch_rollback", rows["cart"] == 2 and rows["favorites"] == 0,
                 "cart=2, favorites=0", rows),
        conjunct("no_partial_success_message", msg(res) != "已收藏 2 件商品",
                 "no all-success message", msg(res)),
    ]
    reset(env)
    c1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    cm = insert_missing_product_cart_row(env, ctx["ta"], "P-ON-5")
    res2 = move(env, ctx["ta"], [c1, cm])
    rows2 = counts(env)
    errs2 = (res2["body"].get("data") or {}).get("errors") if isinstance(res2["body"], dict) else None
    cons += [
        conjunct("missing_product_reason", res2["http"] == 409 and bool(errs2) and
                 any(e.get("message") == "商品不存在" for e in errs2),
                 "409 / errors[] 商品不存在", [res2["http"], errs2]),
        conjunct("missing_batch_rollback", rows2["cart"] == 2 and rows2["favorites"] == 0,
                 "cart=2, favorites=0", rows2),
    ]
    cleanup_missing_row(env, cm)
    reset(env)
    return finish("PB-B14-AC7", "PB-B14", "混合批次全成或全败；逐项原因", cons,
                  {"offline_mixed": res["body"], "missing_mixed": res2["body"]})


# ---------------------------------------------------------------- PB-B15


def ac_b15_1(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    before = product_snapshot(env)
    c1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    c2 = add_line(env, ctx["ta"], "P-ON-5", "1")
    ok = move(env, ctx["ta"], [c1, c2])
    after = counts(env)
    snap = product_snapshot(env)
    cons = [
        conjunct("success_writes_both_sides", ok["http"] == 200 and after["cart"] == 0 and after["favorites"] == 2,
                 "cart=0 & favorites=2", {"http": ok["http"], "counts": after}),
        conjunct("tombstones_created", after["tombstones"] == 2, "tombstones=2", after["tombstones"]),
        conjunct("no_order_no_stock_change", after["orders"] == 0 and same_stock(before, snap),
                 "orders=0 & stock unchanged", {"orders": after["orders"]}),
    ]
    reset(env)
    before2 = counts(env)
    o1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    o2 = add_line(env, ctx["ta"], "P-ON-5", "1")
    offline_product(env, ctx["ts"], "P-ON-5")
    fail = move(env, ctx["ta"], [o1, o2])
    after2 = counts(env)
    cons += [
        conjunct("failure_rolls_back_favorite_and_cart", fail["http"] == 409 and
                 after2["favorites"] == 0 and after2["cart"] == 2,
                 "409 & favorites=0 & cart=2 (no half state)", {"http": fail["http"], "counts": after2}),
    ]
    reset(env)
    return finish("PB-B15-AC1", "PB-B15", "收藏写入与移车同事务，无中间结果", cons,
                  {"success": ok["body"], "failure": fail["body"]})


def ac_b15_2(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    c1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    key = ctx["uuid"]()
    first = move(env, ctx["ta"], [c1], key)
    replay = move(env, ctx["ta"], [c1], key)
    rows = counts(env)
    cons = [
        conjunct("first_submit_success", first["http"] == 200 and msg(first) == "已收藏 1 件商品",
                 "200 / 已收藏 1 件商品", [first["http"], msg(first)]),
        conjunct("same_key_blocked", replay["http"] == 409 and msg(replay) == "请勿重复操作",
                 "409 / 请勿重复操作", [replay["http"], msg(replay)]),
        conjunct("no_double_processing", rows["favorites"] == 1 and rows["cart"] == 0,
                 "favorites=1, cart=0", rows),
        conjunct("single_receipt", move_receipts(env) == 1, "1 MOVE_TO_FAVORITES receipt",
                 move_receipts(env)),
    ]
    c2 = add_line(env, ctx["ta"], "P-ON-10", "1")
    newop = move(env, ctx["ta"], [c2], ctx["uuid"]())
    rows2 = counts(env)
    cons += [
        conjunct("new_key_new_request_allowed", newop["http"] == 200 and rows2["cart"] == 0 and rows2["favorites"] == 1,
                 "200; cart=0; favorites still 1", {"http": newop["http"], "counts": rows2}),
    ]
    reset(env)
    return finish("PB-B15-AC2", "PB-B15", "同键重放拦截，不重复收藏/清车", cons,
                  {"first": first, "replay": replay, "new_request": newop["body"]})


def ac_b15_3(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    c1 = add_line(env, ctx["ta"], "P-ON-10", "5")
    res = move(env, ctx["ta"], [c1])
    rows = counts(env)
    cons = [
        conjunct("qty5_whole_row_moved", res["http"] == 200 and rows["cart"] == 0 and rows["favorites"] == 1,
                 "cart=0, favorites=1", {"http": res["http"], "counts": rows}),
        conjunct("favorite_has_no_quantity", "quantity" not in json.dumps(
            query(env, "SELECT * FROM favorite LIMIT 1")[0], ensure_ascii=False, default=str),
                 "favorite row carries no quantity", query(env, "SELECT * FROM favorite LIMIT 1")[0]),
    ]
    c2 = add_line(env, ctx["ta"], "P-ON-10", "1")
    rows2 = counts(env)
    cons += [
        conjunct("late_add_creates_new_cart_row", rows2["cart"] == 1 and rows2["favorites"] == 1,
                 "re-added line is a fresh cart row, not auto-favorited", rows2),
    ]
    reset(env)
    c3 = add_line(env, ctx["ta"], "P-ON-10", "1")
    patch, mv = race(
        lambda: http_json("PATCH", f"{base_url(env)}/api/me/cart/items/{c3}", {"quantity": "5"},
                          auth_headers(ctx["ta"])),
        lambda: move(env, ctx["ta"], [c3]),
    )
    rows3 = counts(env)
    legal_patch = patch[0] in (200, 409)
    legal_move = mv["http"] in (200, 400)
    cons += [
        conjunct("qty_change_race_final_state", legal_patch and legal_move and rows3["cart"] == 0 and
                 rows3["favorites"] == 1,
                 "cart=0, favorites=1, no 5xx", {"patch": patch, "move": [mv["http"], msg(mv)], "counts": rows3}),
    ]
    reset(env)
    return finish("PB-B15-AC3", "PB-B15", "整行移动；数量与收藏无关；提交期改数量", cons,
                  {"move": res["body"], "race": {"patch": patch, "move": mv["body"]}})


def ac_b15_4(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    c1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    c2 = add_line(env, ctx["ta"], "P-ON-5", "1")
    delete_line(env, ctx["ta"], c2)
    res = move(env, ctx["ta"], [c1, c2])
    data = res["body"].get("data") or {}
    rows = counts(env)
    cons = [
        conjunct("deleted_row_skipped_not_failed", res["http"] == 200 and
                 data.get("movedLineCount") == 1 and str(c2) in [str(x) for x in data.get("skippedDeletedCartItemIds", [])],
                 "200; moved=1; skipped contains deleted id", [res["http"], data]),
        conjunct("other_row_moved", rows["cart"] == 0 and rows["favorites"] == 1, "cart=0, favorites=1", rows),
    ]
    reset(env)
    c3 = add_line(env, ctx["ta"], "P-ON-10", "1")
    delete_line(env, ctx["ta"], c3)
    allgone = move(env, ctx["ta"], [c3])
    cons += [
        conjunct("all_deleted_400_select_goods", allgone["http"] == 400 and msg(allgone) == "请选择商品",
                 "400 / 请选择商品", [allgone["http"], msg(allgone)]),
    ]
    reset(env)
    c4 = add_line(env, ctx["ta"], "P-ON-10", "1")
    mv, dl = race(lambda: move(env, ctx["ta"], [c4]),
                  lambda: delete_line(env, ctx["ta"], c4))
    rows2 = counts(env)
    legal = (mv["http"] == 200 and rows2["favorites"] == 1) or \
            (mv["http"] == 400 and msg(mv) == "请选择商品" and rows2["favorites"] == 0)
    cons += [
        conjunct("concurrent_delete_race_no_partial", legal and rows2["cart"] == 0 and dl[0] in (200, 409),
                 "no half state; cart=0; no 5xx", {"move": [mv["http"], msg(mv)],
                                                    "delete": dl, "counts": rows2}),
    ]
    reset(env)
    return finish("PB-B15-AC4", "PB-B15", "提交期删行：跳过已删；全删=请选择商品", cons,
                  {"skip": res["body"], "all_deleted": allgone["body"],
                   "race": {"move": mv["body"], "delete": dl}})


def ac_b15_5(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    pid = product_id("P-ON-10")
    c1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    key = ctx["uuid"]()
    first = move(env, ctx["ta"], [c1], key)
    cancel = http_json("DELETE", f"{base_url(env)}/api/me/favorites/{pid}", headers=auth_headers(ctx["ta"]))
    replay = move(env, ctx["ta"], [c1], key)
    rows = counts(env)
    cons = [
        conjunct("move_first_success", first["http"] == 200 and msg(first) == "已收藏 1 件商品",
                 "200 / 已收藏 1 件商品", [first["http"], msg(first)]),
        conjunct("late_cancel_success", cancel[0] == 200 and cancel[1]["message"] == "已取消收藏",
                 "200 / 已取消收藏", list(cancel)),
        conjunct("final_favorite_cancelled", rows["favorites"] == 0, "favorites=0", rows["favorites"]),
        conjunct("cart_row_still_removed", rows["cart"] == 0, "cart=0", rows["cart"]),
        conjunct("same_key_returns_original_result", replay["http"] == 200 and
                 msg(replay) == "已收藏 1 件商品" and
                 replay["body"]["data"]["movedLineCount"] == 1,
                 "200 + original payload, no re-favorite", [replay["http"], msg(replay), replay["body"]["data"]]),
        conjunct("no_revival_after_replay", counts(env)["favorites"] == 0 and move_receipts(env) == 1,
                 "favorites=0, 1 move receipt", {"favorites": counts(env)["favorites"],
                                                 "move_receipts": move_receipts(env)}),
    ]
    reset(env)
    return finish("PB-B15-AC5", "PB-B15", "转收藏成功后取消收藏；同键重试返回原结果不复活", cons,
                  {"first": first["body"], "cancel": cancel[1], "replay": replay["body"]})


def ac_b15_6(ctx) -> dict:
    env = ctx["env"]
    reset(env)
    c1 = add_line(env, ctx["ta"], "P-ON-10", "1")
    c2 = add_line(env, ctx["ta"], "P-ON-5", "1")
    offline_product(env, ctx["ts"], "P-ON-5")
    res = move(env, ctx["ta"], [c1, c2])
    rows = counts(env)
    cons = [
        conjunct("offline_row_rejects_batch", res["http"] == 409 and "商品已下架" in json.dumps(res["body"], ensure_ascii=False),
                 "409 / 商品已下架", [res["http"], msg(res)]),
        conjunct("whole_batch_rollback", rows["favorites"] == 0 and rows["cart"] == 2,
                 "favorites=0, cart=2", rows),
    ]
    reset(env)
    c3 = add_line(env, ctx["ta"], "P-ON-10", "1")
    cm = insert_missing_product_cart_row(env, ctx["ta"], "P-ON-5")
    res2 = move(env, ctx["ta"], [c3, cm])
    rows2 = counts(env)
    cons += [
        conjunct("missing_row_rejects_batch", res2["http"] == 409 and
                 "商品不存在" in json.dumps(res2["body"], ensure_ascii=False),
                 "409 / 商品不存在", [res2["http"], msg(res2)]),
        conjunct("missing_batch_rollback", rows2["favorites"] == 0 and rows2["cart"] == 2,
                 "favorites=0, cart=2", rows2),
    ]
    cleanup_missing_row(env, cm)
    reset(env)
    c4 = add_line(env, ctx["ta"], "P-ON-10", "1")
    mv, off = race(lambda: move(env, ctx["ta"], [c4]),
                   lambda: offline_product(env, ctx["ts"], "P-ON-10"))
    rows3 = counts(env)
    legal = (mv["http"] == 200 and rows3["favorites"] == 1 and rows3["cart"] == 0) or \
            (mv["http"] == 409 and rows3["favorites"] == 0 and rows3["cart"] == 1)
    cons += [
        conjunct("in_flight_offline_no_partial", legal,
                 "either success+offline or 409+kept, never favorite+carted", 
                 {"move": [mv["http"], msg(mv)], "offline": off[0], "counts": rows3}),
    ]
    reset(env)
    return finish("PB-B15-AC6", "PB-B15", "提交期下架/不存在：整批失败回滚", cons,
                  {"offline": res["body"], "missing": res2["body"],
                   "race": {"move": mv["body"], "offline": off[1]}})


CHECKS = {
    "PB-B14-AC1": ac_b14_1, "PB-B14-AC2": ac_b14_2, "PB-B14-AC3": ac_b14_3,
    "PB-B14-AC4": ac_b14_4, "PB-B14-AC5": ac_b14_5, "PB-B14-AC6": ac_b14_6,
    "PB-B14-AC7": ac_b14_7,
    "PB-B15-AC1": ac_b15_1, "PB-B15-AC2": ac_b15_2, "PB-B15-AC3": ac_b15_3,
    "PB-B15-AC4": ac_b15_4, "PB-B15-AC5": ac_b15_5, "PB-B15-AC6": ac_b15_6,
}


def markdown(results: list[dict], window: dict) -> str:
    lines = [
        "# B-034 验收执行结果（PB-B14 ×7，PB-B15 ×6）",
        "",
        f"- 执行窗口：{window['started_at']} → {window['ended_at']}（{window['started_at_cst']} → {window['ended_at_cst']}）",
        f"- SUT：`{window['sut_branch']}@{window['sut_sha']}`",
        f"- DB：`{window['db']}`；BASE：{window['base']}",
        "",
        "| AC | 状态 | 合取 | 失败合取 |",
        "|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['ac']} | **{r['status']}** | {r['conjunct_count']} | {', '.join(r['failed_conjuncts']) or '—'} |")
    pass_n = sum(1 for r in results if r["status"].startswith("PASS"))
    fail_n = sum(1 for r in results if r["status"] == "FAIL")
    lines += ["", f"合计：13 AC / **{pass_n} 通过** / {fail_n} 失败 / "
                  f"{13 - pass_n - fail_n} 阻塞；"
                  f"合取 {sum(r['conjunct_count'] for r in results)} 个。", ""]
    for r in results:
        if r["failed_conjuncts"]:
            lines.append(f"## {r['ac']} 失败合取")
            for c in r["conjuncts"]:
                if not c["pass"] and c["disposition_if_fail"] != "DEFER_TO_B036":
                    lines.append(f"- `{c['name']}`：期望 {c['expected']}；实际 {c['actual']}")
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="run a single AC id")
    args = ap.parse_args()
    env = load_b034_env()
    started, started_cst = now_utc(), now_cst()
    ctx = {
        "env": env,
        "ta": login_customer(env, "CUSTOMER_A"),
        "tb": login_customer(env, "CUSTOMER_B"),
        "ts": login_seller(env),
        "stamp": started.replace("-", "").replace(":", ""),
        "uuid": lambda: str(uuid.uuid4()),
    }
    window = {
        "started_at": started, "ended_at": "",
        "started_at_cst": started_cst, "ended_at_cst": "",
        "sut_sha": env.get("B030_SUT_SHA"), "sut_branch": env.get("B030_SUT_BRANCH"),
        "db": env.get("B030_DB_NAME"), "base": base_url(env),
        "delivery_baseline": f"topic/r2@{env.get('B030_DELIVERY_BASE_SHA', '')}",
        "plan": "docs/iterationB/B-030-本轮验收用例/cases/PB-B14.md, PB-B15.md, concurrency/SEQ.md",
        "git_ops": "local-only; no commit/push during execution",
    }
    results = []
    for ac, fn in CHECKS.items():
        if args.only and ac != args.only:
            continue
        print(f"--- {ac}", flush=True)
        try:
            r = fn(ctx)
        except Exception:
            r = {"ac": ac, "pb": ac.split("-")[1], "title": "", "status": "BLOCKED",
                 "conjuncts": [], "conjunct_count": 0, "failed_conjuncts": [],
                 "deferred_conjuncts": [], "evidence": {"traceback": traceback.format_exc()}}
        results.append(r)
        write_json(CASES / f"{ac}.json", r)
        print(f"    {r['status']} conjuncts={r['conjunct_count']}", flush=True)
        try:
            reset(env)
        except Exception:
            pass
    window["ended_at"], window["ended_at_cst"] = now_utc(), now_cst()
    summary = {
        "task": "B-034", "execution_window": window,
        "totals": {
            "acs": len(results),
            "pass": sum(1 for r in results if r["status"].startswith("PASS")),
            "fail": sum(1 for r in results if r["status"] == "FAIL"),
            "blocked": sum(1 for r in results if r["status"] == "BLOCKED"),
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
