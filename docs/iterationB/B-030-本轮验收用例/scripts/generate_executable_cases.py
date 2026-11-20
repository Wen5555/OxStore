#!/usr/bin/env python3
"""Generate executable B-030 case docs from AC semantics + B-000 contract.

Rejects mechanical 「quote」→required-message mapping for prohibition contexts.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACS = json.loads((ROOT / "acs-79.json").read_text(encoding="utf-8"))
CATALOG = json.loads((ROOT / "fixtures" / "catalog.json").read_text(encoding="utf-8"))
CONTRACT = json.loads(
    (ROOT.parent / "B-000-附件" / "B-000-接口契约.json").read_text(encoding="utf-8")
)
FIXED = {
    m["message"]: m
    for m in CONTRACT.get("fixedMessages", [])
    if isinstance(m, dict) and m.get("message") not in (None, "---")
}

# Phrases that appear in 「」 but are FORBIDDEN labels / intermediate states / old rules — not required tips.
FORBIDDEN_AS_REQUIRED_TIP = {
    "失败",
    "每笔数量固定为 1",
    "订单已生成但购物车未清理",
    "库存已扣但清车未完成",
    "订单成功、清车未完成、客户重试时只清车",
    "已扣减量",
    "无货",
    "缺货",
    "超限",
    "下单历史",
}

PROHIBITION_MARKERS = ("不使用", "不再", "不允许", "不存在", "不得", "禁止", "不要", "不可呈现", "不采用")


def classify_quotes(criteria: str) -> dict:
    """Split 「…」 occurrences into required tips vs forbidden labels vs UI labels."""
    required, forbidden, ui, other = [], [], [], []
    for m in re.finditer(r"「([^」]+)」", criteria):
        q = m.group(1)
        start = max(0, m.start() - 12)
        ctx = criteria[start : m.start()]
        if q in FORBIDDEN_AS_REQUIRED_TIP or any(p in ctx for p in PROHIBITION_MARKERS):
            # special: success/error tips that are required still
            if q in FIXED and not any(p in ctx for p in PROHIBITION_MARKERS) and q not in FORBIDDEN_AS_REQUIRED_TIP:
                required.append(q)
            else:
                forbidden.append(q)
        elif q in FIXED:
            required.append(q)
        elif q in ("备货完成", "开始发货", "交易完成", "已取消", "线下交易完成"):
            ui.append(q)
        else:
            # if appears after 提示
            if "提示" in ctx or "返回" in ctx:
                required.append(q)
            elif any(p in ctx for p in PROHIBITION_MARKERS):
                forbidden.append(q)
            else:
                other.append(q)
    # dedupe preserve order
    def uniq(xs):
        s, o = set(), []
        for x in xs:
            if x not in s:
                s.add(x)
                o.append(x)
        return o

    return {
        "required_messages": uniq(required),
        "forbidden_labels_or_states": uniq(forbidden),
        "ui_labels": uniq(ui),
        "other_quotes": uniq(other),
    }


def sql_snap(alias: str = "before") -> list[str]:
    return [
        f"-- snapshot {alias}",
        "SELECT id, stock, status, offline_reason FROM product WHERE name LIKE 'B030-%' ORDER BY name;",
        "SELECT id, username FROM customer WHERE username LIKE 'b030_%';",
        "SELECT so.id, so.order_no, so.status, so.total_amount, so.cancelled_by, c.username "
        "FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%' ORDER BY so.id;",
        "SELECT oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.line_amount "
        "FROM order_item oi JOIN shop_order so ON so.id=oi.order_id "
        "JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%';",
        "SELECT ci.id, c.username, ci.product_id, ci.quantity FROM cart_item ci "
        "JOIN customer c ON c.id=ci.customer_id WHERE c.username LIKE 'b030_%';",
        "SELECT f.id, c.username, f.product_id, f.created_at FROM favorite f "
        "JOIN customer c ON c.id=f.customer_id WHERE c.username LIKE 'b030_%';",
        "SELECT COUNT(*) AS intent_cnt FROM purchase_intent pi "
        "JOIN customer c ON c.id=pi.customer_id WHERE c.username LIKE 'b030_%' "
        "AND pi.legacy_closed_at IS NULL;",
    ]


def step(n, actor, action, detail, extract=None, assert_=None):
    d = {
        "n": n,
        "actor": actor,
        "action": action,
        "detail": detail,
    }
    if extract:
        d["extract"] = extract
    if assert_:
        d["assert"] = assert_
    return d


def http(method, path, headers=None, body=None, note=None):
    return {
        "http": {"method": method, "path": path, "headers": headers or {}, "body": body},
        "note": note,
    }


def build_cases_for_ac(ac: dict) -> list[dict]:
    """Semantic case expansion — not one generic template."""
    ac_id = ac["ac_id"]
    pb = ac["pb_id"]
    crit = ac["criteria"]
    quotes = classify_quotes(crit)
    cases = []

    def base(kind, title, roles, fixtures, steps, expects, seq=None, pages=None):
        cid = f"{ac_id}-{kind}"
        cases.append(
            {
                "case_id": cid,
                "ac_id": ac_id,
                "pb_id": pb,
                "kind": kind,
                "title": title,
                "status": "待执行",
                "roles": roles,
                "sessions": [f"S-{r}" for r in roles],
                "fixtures": fixtures,
                "quotes": quotes,
                "v3": ac["v3"],
                "scene": ac["scene"],
                "impl_tasks": ac["impl_tasks"],
                "test_tasks": ac["test_tasks"],
                "maps_to_seq": seq,
                "pages": pages or [],
                "pre": [
                    "被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。",
                    "独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。",
                    f"用例前：python3 scripts/reset_namespace.py --case-id {cid}",
                    "Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。",
                ],
                "steps": steps,
                "expects": expects,
                "db_assert_sql": sql_snap("after"),
                "cleanup": [
                    f"python3 scripts/reset_namespace.py --case-id {cid}",
                    "证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）",
                ],
                "criteria": crit,
            }
        )

    # ---------- PB-specific builders ----------
    if pb == "PB-B01":
        if ac_id.endswith("AC1"):
            base(
                "POS",
                "多商品多数量建一张新订单且不进旧意向",
                ["CUSTOMER_A"],
                ["P-ON-10", "P-ON-5"],
                [
                    step(1, "CUSTOMER_A", "登录", http("POST", "/api/auth/login", body={"username": "b030_buyer_a", "password": "B030-BuyerA-Pass9"}), extract={"tokenA": "data.token"}),
                    step(2, "CUSTOMER_A", "加购 P-ON-10", http("POST", "/api/me/cart/items", headers={"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${uuid1}"}, body={"productId": "${P-ON-10.id}"}), extract={"cart10": "data.cartItemId"}, assert_={"http": 200, "message": "已加入购物车"}),
                    step(3, "CUSTOMER_A", "改数量为 3", http("PATCH", "/api/me/cart/items/${cart10}", headers={"Authorization": "Bearer ${tokenA}"}, body={"quantity": "3"}), assert_={"http": 200, "message": "已更新", "data.quantity": "3"}),
                    step(4, "CUSTOMER_A", "加购 P-ON-5", http("POST", "/api/me/cart/items", headers={"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${uuid2}"}, body={"productId": "${P-ON-5.id}"}), extract={"cart5": "data.cartItemId"}, assert_={"http": 200, "message": "已加入购物车"}),
                    step(5, "CUSTOMER_A", "改数量为 2", http("PATCH", "/api/me/cart/items/${cart5}", headers={"Authorization": "Bearer ${tokenA}"}, body={"quantity": "2"}), assert_={"http": 200, "data.quantity": "2"}),
                    step(6, "CUSTOMER_A", "创建确认单", http("POST", "/api/me/checkout/confirmations", headers={"Authorization": "Bearer ${tokenA}"}, body={"cartItemIds": ["${cart10}", "${cart5}"]}), extract={"confirmationToken": "data.confirmationToken"}, assert_={"http": 200}),
                    step(7, "CUSTOMER_A", "提交订单", http("POST", "/api/me/orders", headers={"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${uuidSubmit}"}, body={"confirmationToken": "${confirmationToken}"}), extract={"orderId": "data.id", "orderNo": "data.orderNo"}, assert_={"http": [200, 201], "message": "下单成功", "data.status": "PLACED", "data.items.length": 2}),
                    step(8, "DB", "核对", {"sql": [
                        "SELECT COUNT(*) c FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username='b030_buyer_a' AND so.status='PLACED'; -- expect 1",
                        "SELECT quantity FROM order_item WHERE order_id=${orderId} ORDER BY product_id; -- expect 2 and 3 (one row per product)",
                        "SELECT COUNT(*) c FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id WHERE c.username='b030_buyer_a' AND pi.legacy_closed_at IS NULL; -- expect 0 new intent",
                        "SELECT status FROM shop_order WHERE id=${orderId}; -- must NOT be FAILED / 失败",
                    ]}),
                ],
                {
                    "response": "单订单；明细两条；数量分别为 3 与 2；message=下单成功",
                    "page": "订单历史出现该单；无旧意向队列入口冻结；状态文案不是「失败」；不展示「每笔数量固定为 1」",
                    "db": "仅 shop_order/order_item；无新 purchase_intent；status=PLACED",
                    "forbidden": quotes["forbidden_labels_or_states"],
                },
                pages=["/buyer/orders", "/buyer/cart"],
            )
        elif ac_id.endswith("AC2"):
            base(
                "POS",
                "商家依次推进五态不可跳步",
                ["CUSTOMER_A", "SELLER"],
                ["P-ON-10"],
                [
                    step(1, "CUSTOMER_A", "登录并建 PLACED 单（P-ON-10×1）", {"ref": "helper:place_order", "product": "P-ON-10", "qty": "1"}, extract={"orderId": "order.id"}),
                    step(2, "SELLER", "登录后台", http("POST", "/api/admin/auth/login", body={"username": "admin", "password": "${B030_SELLER_PASSWORD}"}), extract={"tokenS": "data.token"}),
                    step(3, "SELLER", "CONFIRM", http("POST", "/api/admin/orders/${orderId}/actions", headers={"Authorization": "Bearer ${tokenS}"}, body={"action": "CONFIRM", "expectedStatus": "PLACED"}), assert_={"http": 200, "data.status": "CONFIRMED"}),
                    step(4, "SELLER", "跳步 SHIP 应拒绝", http("POST", "/api/admin/orders/${orderId}/actions", headers={"Authorization": "Bearer ${tokenS}"}, body={"action": "SHIP", "expectedStatus": "CONFIRMED"}), assert_={"http_not": 200, "data.status_unchanged": "CONFIRMED"}),
                    step(5, "SELLER", "PREPARE", http("POST", "/api/admin/orders/${orderId}/actions", headers={"Authorization": "Bearer ${tokenS}"}, body={"action": "PREPARE", "expectedStatus": "CONFIRMED"}), assert_={"data.status": "PREPARED"}),
                    step(6, "SELLER", "SHIP", http("POST", "/api/admin/orders/${orderId}/actions", headers={"Authorization": "Bearer ${tokenS}"}, body={"action": "SHIP", "expectedStatus": "PREPARED"}), assert_={"data.status": "SHIPPED"}),
                    step(7, "SELLER", "COMPLETE", http("POST", "/api/admin/orders/${orderId}/actions", headers={"Authorization": "Bearer ${tokenS}"}, body={"action": "COMPLETE", "expectedStatus": "SHIPPED"}), assert_={"data.status": "COMPLETED"}),
                    step(8, "CUSTOMER_A", "客户不可推进", http("POST", "/api/admin/orders/${orderId}/actions", headers={"Authorization": "Bearer ${tokenA}"}, body={"action": "CONFIRM", "expectedStatus": "PLACED"}), assert_={"forbidden": True}),
                ],
                {
                    "response": "仅顺序 CONFIRM→PREPARE→SHIP→COMPLETE 成功；跳步失败且状态不变",
                    "page": "商家订单管理五态按钮按序；客户侧无推进控件",
                    "db": "最终 COMPLETED；无回退记录",
                    "forbidden": ["部分确认", "部分发货", "自动流转"],
                },
                pages=["/admin/orders"],
            )
            base(
                "NEG",
                "客户尝试推进状态被拒",
                ["CUSTOMER_A"],
                ["P-ON-10"],
                [
                    step(1, "CUSTOMER_A", "持有 PLACED 单", {"ref": "helper:place_order", "product": "P-ON-10", "qty": "1"}, extract={"orderId": "order.id", "tokenA": "token"}),
                    step(2, "CUSTOMER_A", "调用商家 actions", http("POST", "/api/admin/orders/${orderId}/actions", headers={"Authorization": "Bearer ${tokenA}"}, body={"action": "CONFIRM", "expectedStatus": "PLACED"}), assert_={"not_success": True}),
                    step(3, "DB", "状态仍为 PLACED", {"sql": ["SELECT status FROM shop_order WHERE id=${orderId}; -- PLACED"]}),
                ],
                {"response": "拒绝；订单不变", "db": "status=PLACED", "forbidden": []},
            )
        elif ac_id.endswith("AC3"):
            base(
                "POS",
                "终态完成与取消不可再流转",
                ["CUSTOMER_A", "SELLER"],
                ["P-ON-10"],
                [
                    step(1, "BOTH", "准备 COMPLETED 单与 CANCELLED 单各一", {"ref": "helper:seed_terminal_orders"}),
                    step(2, "SELLER", "对 COMPLETED 再 COMPLETE/取消", http("POST", "/api/admin/orders/${completedId}/actions", headers={"Authorization": "Bearer ${tokenS}"}, body={"action": "COMPLETE", "expectedStatus": "COMPLETED"}), assert_={"rejected": True}),
                    step(3, "CUSTOMER_A", "对 COMPLETED 取消", http("POST", "/api/me/orders/${completedId}/cancel", headers={"Authorization": "Bearer ${tokenA}"}, body={"expectedStatus": "COMPLETED"}), assert_={"message": "订单已完成，不可取消"}),
                    step(4, "SELLER", "对 CANCELLED 再推进", http("POST", "/api/admin/orders/${cancelledId}/actions", headers={"Authorization": "Bearer ${tokenS}"}, body={"action": "CONFIRM", "expectedStatus": "CANCELLED"}), assert_={"rejected": True}),
                ],
                {
                    "response": "终态操作拒绝；完成后取消提示「订单已完成，不可取消」；重复取消「订单已取消」",
                    "ui_labels": quotes["ui_labels"],
                    "db": "终态不变；无超时自动取消任务副作用",
                    "forbidden": quotes["forbidden_labels_or_states"],
                },
            )
        elif ac_id.endswith("AC4"):
            base(
                "POS",
                "备货/发货/完成仅状态标记无需物流凭证",
                ["CUSTOMER_A", "SELLER"],
                ["P-ON-10"],
                [
                    step(1, "SELLER", "将订单推到 PREPARED", {"ref": "helper:advance_to", "status": "PREPARED"}),
                    step(2, "SELLER", "SHIP 无地址/运单字段", http("POST", "/api/admin/orders/${orderId}/actions", headers={"Authorization": "Bearer ${tokenS}"}, body={"action": "SHIP", "expectedStatus": "PREPARED"}), assert_={"http": 200, "data.status": "SHIPPED"}),
                    step(3, "SELLER", "COMPLETE 仅确认", http("POST", "/api/admin/orders/${orderId}/actions", headers={"Authorization": "Bearer ${tokenS}"}, body={"action": "COMPLETE", "expectedStatus": "SHIPPED"}), assert_={"http": 200, "data.status": "COMPLETED"}),
                    step(4, "UI", "页面", {"page": "/admin/orders/${orderId}", "assert": "无强制收货地址/承运商/运单号/凭证上传校验即可完成"}),
                ],
                {
                    "response": "SHIP/COMPLETE 成功无需额外字段",
                    "page": "人工标记即可；线下交易由商家确认",
                    "db": "status 到 COMPLETED；无物流附属表必填失败",
                    "ui_labels": ["备货完成", "开始发货", "交易完成"],
                },
                pages=["/admin/orders"],
            )
        elif ac_id.endswith("AC5"):
            base(
                "BND",
                "重复推进拒绝且不重复扣库",
                ["SELLER"],
                ["P-ON-10"],
                [
                    step(1, "SELLER", "订单已 CONFIRMED；记录 stock_before", {"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-10';"]}, extract={"stock_before": "stock"}),
                    step(2, "SELLER", "再次 CONFIRM", http("POST", "/api/admin/orders/${orderId}/actions", headers={"Authorization": "Bearer ${tokenS}"}, body={"action": "CONFIRM", "expectedStatus": "CONFIRMED"}), assert_={"rejected": True}),
                    step(3, "DB", "库存不变", {"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-10'; -- == stock_before"]}),
                ],
                {"response": "拒绝；状态不变", "db": "库存无二次扣减", "forbidden": []},
                seq="SEQ-12",
            )
            base(
                "CON",
                "双商家会话并发推进同一单",
                ["SELLER", "SELLER"],
                ["P-ON-10"],
                [
                    step(1, "SETUP", "PLACED 单；两个商家 JWT（或同商家双连接）", {"ref": "helper:place_order"}),
                    step(2, "BARRIER", "同时 CONFIRM", {"barrier": "SEQ-12", "mode": "simultaneous", "a": "POST /api/admin/orders/${orderId}/actions CONFIRM expectedStatus=PLACED", "b": "同"}),
                    step(3, "ASSERT", "恰一成功一拒绝；最终 CONFIRMED；无重复订单", {"sql": ["SELECT status, COUNT(*) FROM shop_order WHERE id=${orderId};"]}),
                ],
                {"response": "先成功者生效；后到冲突拒绝", "db": "单行订单；库存只按建单时已扣一次", "forbidden": []},
                seq="SEQ-12",
            )

    elif pb == "PB-B02":
        if "AC1" in ac_id:
            base("POS", "下单直接扣剩余可售库存且完成不再扣", ["CUSTOMER_A", "SELLER"], ["P-ON-10"], [
                step(1, "DB", "stock_before=10", {"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-10';"]}),
                step(2, "CUSTOMER_A", "下单 qty=3", {"ref": "helper:place_order", "product": "P-ON-10", "qty": "3"}),
                step(3, "DB", "stock=7", {"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-10'; -- 7"]}),
                step(4, "SELLER", "推进至 COMPLETED", {"ref": "helper:advance_to", "status": "COMPLETED"}),
                step(5, "DB", "完成后再读 stock 仍为 7", {"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-10'; -- 7"]}),
            ], {"response": "下单成功", "db": "仅下单扣减；无独立已扣减量字段对齐；确认/备货/完成不改库存", "forbidden": ["已扣减量"]})
        elif "AC2" in ac_id:
            base("POS", "他客看到扣后余量；下架不影响已单", ["CUSTOMER_A", "CUSTOMER_B", "SELLER"], ["P-ON-10"], [
                step(1, "CUSTOMER_A", "下单 qty=4", {"ref": "helper:place_order", "qty": "4"}),
                step(2, "CUSTOMER_B", "读商品可售", {"http": {"method": "GET", "path": "/api/products/${P-ON-10.id}"}, "assert": {"stock": "6"}}),
                step(3, "SELLER", "下架商品", http("POST", "/api/admin/products/${P-ON-10.id}/offline", headers={"Authorization": "Bearer ${tokenS}"})),
                step(4, "SELLER", "原单仍可 CONFIRM", http("POST", "/api/admin/orders/${orderId}/actions", headers={"Authorization": "Bearer ${tokenS}"}, body={"action": "CONFIRM", "expectedStatus": "PLACED"}), assert_={"data.status": "CONFIRMED"}),
            ], {"db": "已单快照不变；新订单不可再下", "forbidden": []}, seq="SEQ-01")
        elif "AC3" in ac_id:
            base("POS", "商家改库存任意非负整数；0 自动下架", ["SELLER"], ["P-ON-10"], [
                step(1, "SELLER", "PATCH stock=42", http("PATCH", "/api/admin/products/${P-ON-10.id}", headers={"Authorization": "Bearer ${tokenS}"}, body={"stock": "42"}), assert_={"http": 200}),
                step(2, "SELLER", "PATCH stock=0", http("PATCH", "/api/admin/products/${P-ON-10.id}", headers={"Authorization": "Bearer ${tokenS}"}, body={"stock": "0"}), assert_={"http": 200}),
                step(3, "DB", "OFFLINE AUTO_ZERO", {"sql": ["SELECT stock,status,offline_reason FROM product WHERE id=${P-ON-10.id}; -- 0,OFFLINE,AUTO_ZERO"]}),
            ], {"db": "已单快照不受影响", "forbidden": []})
            base("NEG", "负数/小数库存拒绝", ["SELLER"], ["P-ON-5"], [
                step(1, "DB", "stock_before", {"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-5';"]}, extract={"stock_before": "stock"}),
                step(2, "SELLER", "stock=-1", http("PATCH", "/api/admin/products/${P-ON-5.id}", headers={"Authorization": "Bearer ${tokenS}"}, body={"stock": "-1"}), assert_={"message": "库存不能为负数，请输入非负整数。"}),
                step(3, "SELLER", "stock=1.5", http("PATCH", "/api/admin/products/${P-ON-5.id}", headers={"Authorization": "Bearer ${tokenS}"}, body={"stock": "1.5"}), assert_={"message": "库存不能为负数，请输入非负整数。"}),
                step(4, "DB", "不变", {"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-5'; -- == stock_before"]}),
            ], {"required_messages": ["库存不能为负数，请输入非负整数。"], "db": "原库存保持"})
        else:  # AC4+
            _generic_executable(base, ac, quotes, crit)

    elif pb in ("PB-B08", "PB-B09"):
        if "收藏" in crit or pb == "PB-B08":
            if ac_id.endswith("AC1") or "首次" in crit or "重复收藏" in crit:
                base("POS", "首次与重复收藏", ["CUSTOMER_A"], ["P-ON-10"], [
                    step(1, "CUSTOMER_A", "登录", http("POST", "/api/auth/login", body={"username": "b030_buyer_a", "password": "B030-BuyerA-Pass9"}), extract={"tokenA": "data.token"}),
                    step(2, "CUSTOMER_A", "首次收藏", http("PUT", "/api/me/favorites/${P-ON-10.id}", headers={"Authorization": "Bearer ${tokenA}"}), extract={"createdAt": "data.createdAt", "favoriteId": "data.favoriteId"}, assert_={"http": 200, "message": "已收藏"}),
                    step(3, "CUSTOMER_A", "重复收藏", http("PUT", "/api/me/favorites/${P-ON-10.id}", headers={"Authorization": "Bearer ${tokenA}"}), assert_={"http": 200, "message": "已收藏", "data.createdAt": "${createdAt}"}),
                    step(4, "DB", "唯一行且 created_at 不变", {"sql": ["SELECT COUNT(*), MIN(created_at)=MAX(created_at) FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username='b030_buyer_a' AND f.product_id=${P-ON-10.id};"]}),
                ], {"required_messages": ["已收藏"], "db": "UNIQUE(customer,product)；重复不刷新时间"})
            if "未登录" in crit or "登录" in crit:
                base("NEG", "未登录收藏", ["ANON"], ["P-ON-10"], [
                    step(1, "ANON", "无 Authorization 收藏", http("PUT", "/api/me/favorites/${P-ON-10.id}"), assert_={"message": "请先登录"}),
                    step(2, "DB", "无新收藏", {"sql": ["SELECT COUNT(*) FROM favorite f JOIN product p ON p.id=f.product_id WHERE p.name LIKE 'B030-%'; -- 0 new"]}),
                ], {"required_messages": ["请先登录"], "db": "不写入"})
            if "下架" in crit:
                base("NEG", "下架商品不可新收藏", ["CUSTOMER_A"], ["P-OFF-M"], [
                    step(1, "CUSTOMER_A", "收藏人工下架商品", http("PUT", "/api/me/favorites/${P-OFF-M.id}", headers={"Authorization": "Bearer ${tokenA}"}), assert_={"message": "商品已下架"}),
                ], {"required_messages": ["商品已下架"], "db": "不新建"})
            if "取消" in crit or pb == "PB-B09":
                base("POS", "取消收藏", ["CUSTOMER_A"], ["P-ON-10"], [
                    step(1, "CUSTOMER_A", "确保已收藏", http("PUT", "/api/me/favorites/${P-ON-10.id}", headers={"Authorization": "Bearer ${tokenA}"}), assert_={"message": "已收藏"}),
                    step(2, "CUSTOMER_A", "取消", http("DELETE", "/api/me/favorites/${P-ON-10.id}", headers={"Authorization": "Bearer ${tokenA}"}), assert_={"message": "已取消收藏"}),
                    step(3, "CUSTOMER_A", "再取消", http("DELETE", "/api/me/favorites/${P-ON-10.id}", headers={"Authorization": "Bearer ${tokenA}"}), assert_={"message": "未收藏"}),
                ], {"required_messages": ["已取消收藏", "未收藏"]})
            if "列表" in crit or "已下架" in crit or ac_id.endswith("AC2") or ac_id.endswith("AC3"):
                base("POS", "列表失效项展示", ["CUSTOMER_A", "SELLER"], ["P-ON-10"], [
                    step(1, "CUSTOMER_A", "收藏后商家下架", {"ref": "helper:favorite_then_offline"}),
                    step(2, "CUSTOMER_A", "GET 列表", http("GET", "/api/me/favorites?page=1", headers={"Authorization": "Bearer ${tokenA}"}), assert_={"contains_badge": "已下架"}),
                ], {"required_messages": [], "ui_labels": ["已下架"], "page": "失效项保留且不可进可购买详情"})
            if not cases:
                _generic_executable(base, ac, quotes, crit)
        else:
            _generic_executable(base, ac, quotes, crit)

    elif pb in ("PB-B10", "PB-B11"):
        base("POS", "加购与改数量", ["CUSTOMER_A"], ["P-ON-10"], [
            step(1, "CUSTOMER_A", "加购", http("POST", "/api/me/cart/items", headers={"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k1}"}, body={"productId": "${P-ON-10.id}"}), extract={"cartId": "data.cartItemId"}, assert_={"message": "已加入购物车", "data.quantity": "1"}),
            step(2, "CUSTOMER_A", "同键重放", http("POST", "/api/me/cart/items", headers={"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k1}"}, body={"productId": "${P-ON-10.id}"}), assert_={"message": "已加入购物车", "data.cartItemId": "${cartId}", "data.quantity": "1"}),
            step(3, "CUSTOMER_A", "改量 5", http("PATCH", "/api/me/cart/items/${cartId}", headers={"Authorization": "Bearer ${tokenA}"}, body={"quantity": "5"}), assert_={"message": "已更新", "data.quantity": "5"}),
            step(4, "CUSTOMER_A", "改量 0 删行", http("PATCH", "/api/me/cart/items/${cartId}", headers={"Authorization": "Bearer ${tokenA}"}, body={"quantity": "0"}), assert_={"message": "已移除"}),
            step(5, "CUSTOMER_A", "旧 id 再改量", http("PATCH", "/api/me/cart/items/${cartId}", headers={"Authorization": "Bearer ${tokenA}"}, body={"quantity": "2"}), assert_={"message": "该商品已不在购物车，请刷新页面后查看。"}),
        ], {"required_messages": ["已加入购物车", "已更新", "已移除", "该商品已不在购物车，请刷新页面后查看。"], "db": "删行后 tombstone；旧 id 不 upsert"}, seq="SEQ-09" if "删" in crit or "旧" in crit else ("SEQ-08" if "多端" in crit or "同时" in crit else None))
        if "未登录" in crit or "无权" in crit:
            base("NEG", "未登录/越权购物车", ["ANON", "CUSTOMER_B"], ["P-ON-10"], [
                step(1, "ANON", "加购", http("POST", "/api/me/cart/items", headers={"Idempotency-Key": "${k}"}, body={"productId": "${P-ON-10.id}"}), assert_={"message": "请先登录"}),
                step(2, "CUSTOMER_B", "改 A 的 cartItemId", http("PATCH", "/api/me/cart/items/${cartIdA}", headers={"Authorization": "Bearer ${tokenB}"}, body={"quantity": "9"}), assert_={"message": "无权操作"}),
            ], {"required_messages": ["请先登录", "无权操作"]})
        if "空" in crit or "清空" in crit:
            base("POS", "空车与清空", ["CUSTOMER_A"], ["P-ON-10"], [
                step(1, "CUSTOMER_A", "空车 GET", http("GET", "/api/me/cart", headers={"Authorization": "Bearer ${tokenA}"}), assert_={"empty_message_or_items": "购物车是空的"}),
                step(2, "CUSTOMER_A", "加购后 DELETE /api/me/cart", http("DELETE", "/api/me/cart", headers={"Authorization": "Bearer ${tokenA}"}), assert_={"http": 200}),
            ], {"ui_empty": "购物车是空的"})
        if "并发" in crit or "同时" in crit or "多端" in crit:
            base("CON", "多端最后写入", ["CUSTOMER_A"], ["P-ON-10"], [
                step(1, "BARRIER", "两端同时改量", {"barrier": "SEQ-08", "mode": "simultaneous"}),
            ], {"db": "同商品一行；以服务端最后成功为准"}, seq="SEQ-08")

    elif pb in ("PB-B12", "PB-B13"):
        if "AC1" in ac_id and pb == "PB-B13":
            base("POS", "建单扣库清车同事务成功", ["CUSTOMER_A"], ["P-ON-10"], [
                step(1, "CUSTOMER_A", "车行 qty=2；记录 stock/cart", {"ref": "helper:cart_qty", "qty": "2"}),
                step(2, "CUSTOMER_A", "确认+下单", {"ref": "helper:checkout_submit"}, extract={"orderId": "data.id"}, assert_={"message": "下单成功"}),
                step(3, "ASSERT", "同时可见：有订单、库存-2、所选行按余数清理；无中间态文案", {"checks": [
                    "response.message == 下单成功 且含 orderNo",
                    "DB shop_order 存在",
                    "product.stock 已减",
                    "cart 所选行已按余数处理",
                    "禁止出现「订单已生成但购物车未清理」「库存已扣但清车未完成」类可见态",
                ]}),
            ], {"required_messages": ["下单成功"], "forbidden": quotes["forbidden_labels_or_states"], "db": "同事务全有或全无"}, seq="SEQ-02")
            base("NEG", "失败全回滚", ["CUSTOMER_A"], ["P-ON-1"], [
                step(1, "CUSTOMER_A", "车行 qty=5 > stock 1", {"ref": "helper:cart_qty", "product": "P-ON-1", "qty": "5"}),
                step(2, "CUSTOMER_A", "下单应失败", {"ref": "helper:checkout_submit"}, assert_={"message_contains": "库存不足", "no_order": True}),
                step(3, "DB", "无订单；库存仍 1；车行仍 5", {"sql": sql_snap("fail")}),
            ], {"db": "失败无订单无扣库车不变", "forbidden": quotes["forbidden_labels_or_states"]})
        elif "幂等" in crit or "重复" in crit or (pb == "PB-B13" and "AC4" in ac_id):
            base("BND", "同结算同键不重复建单", ["CUSTOMER_A"], ["P-ON-10"], [
                step(1, "CUSTOMER_A", "确认并提交成功", {"ref": "helper:checkout_submit"}, extract={"orderId": "data.id", "key": "idemKey", "token": "confirmationToken"}),
                step(2, "CUSTOMER_A", "同 confirmationToken + 同 Idempotency-Key 重放", http("POST", "/api/me/orders", headers={"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${key}"}, body={"confirmationToken": "${token}"}), assert_={"message": "订单已提交，请勿重复下单"}),
                step(3, "DB", "仍仅一单；库存/车不二次处理", {"sql": ["SELECT COUNT(*) FROM shop_order WHERE id=${orderId}; -- 1"]}),
            ], {"required_messages": ["订单已提交，请勿重复下单"]}, seq="SEQ-02")
        elif "并发" in crit or "抢" in crit or (pb == "PB-B13" and "AC5" in ac_id):
            base("CON", "库存1双客户抢购", ["CUSTOMER_A", "CUSTOMER_B"], ["P-ON-1"], [
                step(1, "SETUP", "P-ON-1 stock=1；A/B 各确认 qty=1", {"ref": "helper:dual_confirm", "product": "P-ON-1"}),
                step(2, "BARRIER", "同时提交", {"barrier": "SEQ-01", "mode": "simultaneous", "a": "POST /api/me/orders A", "b": "POST /api/me/orders B"}),
                step(3, "ASSERT", "恰一成功；库存0；失败者整单拒绝无半单", {"sql": ["SELECT stock FROM product WHERE name='B030-低库存-1'; -- 0", "SELECT COUNT(*) FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%' AND so.status='PLACED'; -- 1"]}),
            ], {"db": "防超卖；无半张订单"}, seq="SEQ-01")
        else:
            _checkout_family(base, ac, quotes, crit)

    elif pb in ("PB-B14", "PB-B15"):
        base("POS", "转收藏同事务", ["CUSTOMER_A"], ["P-ON-10", "P-ON-5"], [
            step(1, "CUSTOMER_A", "车内两行在售", {"ref": "helper:cart_two_lines"}),
            step(2, "UI", "二次确认文案", {"page": "/buyer/cart", "assert_text": "所选 2 件商品将从购物车移除并加入收藏"}),
            step(3, "CUSTOMER_A", "move-to-favorites", http("POST", "/api/me/cart/move-to-favorites", headers={"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}, body={"cartItemIds": ["${c1}", "${c2}"]}), assert_={"message_match": "已收藏 2 件商品"}),
            step(4, "DB", "车行移除且收藏存在；库存不变；无订单", {"sql": [
                "SELECT COUNT(*) FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username='b030_buyer_a'; -- 0 for moved",
                "SELECT COUNT(*) FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username='b030_buyer_a'; -- >=2",
                "SELECT COUNT(*) FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username='b030_buyer_a' AND so.created_at > ${t0}; -- 0",
            ]}),
        ], {"required_messages": ["已收藏 N 件商品"], "forbidden": ["中间结果"], "db": "收藏写入与移车同事务"}, seq="SEQ-10")
        if "并发" in crit or "取消" in crit or pb == "PB-B15":
            base("CON", "转收藏 vs 取消收藏", ["CUSTOMER_A"], ["P-ON-10"], [
                step(1, "BARRIER", "SEQ-10", {"barrier": "SEQ-10", "mode": "simultaneous"}),
            ], {"db": "车行已移除；最终收藏可为空；同键重试不复活"}, seq="SEQ-10")
            base("CON", "转收藏期间删光所选行", ["CUSTOMER_A"], ["P-ON-10"], [
                step(1, "BARRIER", "SEQ-11", {"barrier": "SEQ-11", "mode": "b_first"}),
            ], {"required_messages": ["请选择商品"], "db": "无半成功"}, seq="SEQ-11")
        if "空选" in crit:
            base("NEG", "空选转收藏", ["CUSTOMER_A"], [], [
                step(1, "CUSTOMER_A", "cartItemIds=[]", http("POST", "/api/me/cart/move-to-favorites", headers={"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}, body={"cartItemIds": []}), assert_={"message": "请选择商品"}),
            ], {"required_messages": ["请选择商品"]})

    elif pb in ("PB-B04", "PB-B05", "PB-B06", "PB-B07"):
        _cancel_family(base, ac, quotes, crit)
    elif pb == "PB-B03":
        _order_snapshot_family(base, ac, quotes, crit)
    else:
        _generic_executable(base, ac, quotes, crit)

    # Ensure at least one case
    if not cases:
        _generic_executable(base, ac, quotes, crit)
    return cases


def _checkout_family(base, ac, quotes, crit):
    base("POS", "结算选择与确认", ["CUSTOMER_A"], ["P-ON-10", "P-OFF-M"], [
        step(1, "CUSTOMER_A", "确认所选在售行", http("POST", "/api/me/checkout/confirmations", headers={"Authorization": "Bearer ${tokenA}"}, body={"cartItemIds": ["${cartOn}"]}), extract={"confirmationToken": "data.confirmationToken"}, assert_={"http": 200}),
        step(2, "CUSTOMER_A", "空选确认", http("POST", "/api/me/checkout/confirmations", headers={"Authorization": "Bearer ${tokenA}"}, body={"cartItemIds": []}), assert_={"message": "请选择商品"}),
        step(3, "CUSTOMER_A", "提交下单", http("POST", "/api/me/orders", headers={"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}, body={"confirmationToken": "${confirmationToken}"}), assert_={"message": "下单成功"}),
    ], {"required_messages": [m for m in ("请选择商品", "下单成功") if m in crit or True], "forbidden": quotes["forbidden_labels_or_states"]})
    if "下架" in crit:
        base("NEG", "确认后下架再提交", ["CUSTOMER_A", "SELLER"], ["P-ON-10"], [
            step(1, "CUSTOMER_A", "确认", {"ref": "helper:confirm"}),
            step(2, "SELLER", "下架", http("POST", "/api/admin/products/${P-ON-10.id}/offline", headers={"Authorization": "Bearer ${tokenS}"})),
            step(3, "CUSTOMER_A", "提交", {"ref": "helper:submit"}, assert_={"message_contains": "已下架"}),
        ], {"db": "无订单"})


def _cancel_family(base, ac, quotes, crit):
    who = "CUSTOMER_A" if "客户" in crit or ac["pb_id"] in ("PB-B04", "PB-B05") else "SELLER"
    base("POS", "取消主路径", [who, "CUSTOMER_A", "SELLER"], ["P-ON-10"], [
        step(1, "SETUP", "准备可取消状态订单并记录 stock_before 与 snapshot_qty", {"ref": "helper:order_in_status", "status": "PREPARED" if "备货" in crit or "发货" in crit else "PLACED"}),
        step(2, who, "取消", http("POST", "/api/me/orders/${orderId}/cancel" if who == "CUSTOMER_A" else "/api/admin/orders/${orderId}/cancel", headers={"Authorization": "Bearer ${token}"}, body={"expectedStatus": "${status}", "reason": "B030-test"}), assert_={"data.status": "CANCELLED"}),
        step(3, "DB", "回补一次；cancelled_by 正确", {"sql": [
            "SELECT status, cancelled_by, cancelled_at FROM shop_order WHERE id=${orderId};",
            "SELECT stock FROM product WHERE id=${productId}; -- stock_before + snapshot_qty （人工改库存交叉时按 B-000 串行规则）",
        ]}),
    ], {"db": "回补至多一次；终态 CANCELLED"}, seq="SEQ-04" if "并发" in crit or "发货" in crit else ("SEQ-06" if "双方" in crit else None))
    if "发货" in crit or "不可取消" in crit:
        base("NEG", "SHIPPED 客户不可取消", ["CUSTOMER_A"], ["P-ON-10"], [
            step(1, "SETUP", "SHIPPED 单", {"ref": "helper:advance_to", "status": "SHIPPED"}),
            step(2, "CUSTOMER_A", "取消", http("POST", "/api/me/orders/${orderId}/cancel", headers={"Authorization": "Bearer ${tokenA}"}, body={"expectedStatus": "SHIPPED"}), assert_={"message": "订单已开始发货，不可取消"}),
        ], {"required_messages": ["订单已开始发货，不可取消"]})
    if "完成" in crit:
        base("NEG", "完成后不可取消", ["CUSTOMER_A"], ["P-ON-10"], [
            step(1, "SETUP", "COMPLETED", {"ref": "helper:advance_to", "status": "COMPLETED"}),
            step(2, "CUSTOMER_A", "取消", http("POST", "/api/me/orders/${orderId}/cancel", headers={"Authorization": "Bearer ${tokenA}"}, body={"expectedStatus": "COMPLETED"}), assert_={"message": "订单已完成，不可取消"}),
        ], {"required_messages": ["订单已完成，不可取消"]})
    if "并发" in crit or "同时" in crit:
        base("CON", "取消竞争", ["CUSTOMER_A", "SELLER"], ["P-ON-10"], [
            step(1, "BARRIER", "按 SEQ", {"barrier": "SEQ-04" if "发货" in crit else "SEQ-06", "mode": "simultaneous"}),
        ], {"db": "先成功；回补一次"}, seq="SEQ-04" if "发货" in crit else "SEQ-06")
    if "部分取消" in crit:
        base("NEG", "部分取消拒绝", ["CUSTOMER_A"], ["P-ON-10"], [
            step(1, "CUSTOMER_A", "body 含 items", http("POST", "/api/me/orders/${orderId}/cancel", headers={"Authorization": "Bearer ${tokenA}"}, body={"expectedStatus": "PLACED", "items": ["1"]}), assert_={"message": "不支持部分取消"}),
        ], {"required_messages": ["不支持部分取消"]})
    if "自动恢复" in crit or "人工下架" in crit or "AUTO_ZERO" in crit or "回补" in crit:
        base("BND", "取消回补与自动恢复边界", ["CUSTOMER_A", "SELLER"], ["P-ON-0", "P-OFF-M"], [
            step(1, "SETUP", "造单使某商品扣至 0→AUTO_ZERO；另一单商品为 MANUAL 下架", {"ref": "helper:cancel_restock_matrix"}),
            step(2, "CUSTOMER_A", "取消 AUTO_ZERO 来源单", {"ref": "helper:cancel"}),
            step(3, "DB", "回补后 stock>0 且自动恢复在售；MANUAL 下架不因回补自动上架", {"sql": [
                "SELECT stock,status,offline_reason FROM product WHERE name='B030-零库存自动下架';",
                "SELECT stock,status,offline_reason FROM product WHERE name='B030-人工下架-库存5';",
            ]}),
        ], {"db": "AUTO_ZERO 可恢复；MANUAL 不自动恢复"})


def _order_snapshot_family(base, ac, quotes, crit):
    base("POS", "订单快照与历史", ["CUSTOMER_A", "SELLER"], ["P-ON-10"], [
        step(1, "CUSTOMER_A", "下单", {"ref": "helper:place_order", "qty": "2"}, extract={"orderId": "id", "unit": "items[0].unitPrice", "qty": "items[0].quantity"}),
        step(2, "SELLER", "改价改库存改名", {"ref": "helper:mutate_product"}),
        step(3, "CUSTOMER_A", "GET 订单详情", http("GET", "/api/me/orders/${orderId}", headers={"Authorization": "Bearer ${tokenA}"}), assert_={"snapshot_unchanged": True}),
        step(4, "CUSTOMER_A", "订单历史分页", http("GET", "/api/me/orders?page=1&size=10", headers={"Authorization": "Bearer ${tokenA}"}), assert_={"http": 200}),
    ], {"db": "order_item 快照不随商品变更；同 order+product 仅一行", "page": "历史展示快照字段"})
    if "归档" in crit or "legacy" in crit.lower() or "旧" in crit:
        base("POS", "旧意向只读归档", ["CUSTOMER_A", "SELLER"], ["LEGACY_INTENT"], [
            step(1, "CUSTOMER_A", "GET legacy", http("GET", "/api/me/legacy-intents?page=1&size=10", headers={"Authorization": "Bearer ${tokenA}"}), assert_={"http": 200}),
            step(2, "SELLER", "GET admin legacy", http("GET", "/api/admin/legacy-intents?page=1&size=10", headers={"Authorization": "Bearer ${tokenS}"}), assert_={"http": 200}),
            step(3, "ASSERT", "不可当新单推进；拍卖未改", {"note": "B035 回归单列"}),
        ], {"db": "legacy_closed_at 非空；原 status 保留"})


def _generic_executable(base, ac, quotes, crit):
    """Fallback still concrete: bind fixtures + primary APIs inferred from PB/criteria."""
    pb = ac["pb_id"]
    fixtures = ["P-ON-10"]
    if "库存" in crit:
        fixtures += ["P-ON-1", "P-ON-0"]
    if "下架" in crit:
        fixtures.append("P-OFF-M")
    if "拍卖" in crit:
        fixtures.append("P-AUC")
    roles = ["CUSTOMER_A"]
    if "商家" in crit:
        roles.append("SELLER")
    if "其他客户" in crit or "另一" in crit or "双方" in crit or "并发" in crit:
        roles.append("CUSTOMER_B")

    primary = []
    if any(k in crit for k in ("收藏",)):
        primary.append(("PUT", "/api/me/favorites/${P-ON-10.id}", None, "已收藏"))
    if any(k in crit for k in ("加购", "购物车", "清车", "改量")):
        primary.append(("POST", "/api/me/cart/items", {"productId": "${P-ON-10.id}"}, "已加入购物车"))
    if any(k in crit for k in ("下单", "结算", "确认", "建单")):
        primary.append(("POST", "/api/me/checkout/confirmations", {"cartItemIds": ["${cartId}"]}, None))
        primary.append(("POST", "/api/me/orders", {"confirmationToken": "${confirmationToken}"}, "下单成功"))
    if "取消" in crit and "商家" in crit:
        primary.append(("POST", "/api/admin/orders/${orderId}/cancel", {"expectedStatus": "${status}"}, None))
    elif "取消" in crit:
        primary.append(("POST", "/api/me/orders/${orderId}/cancel", {"expectedStatus": "${status}"}, None))
    if "转收藏" in crit:
        primary.append(("POST", "/api/me/cart/move-to-favorites", {"cartItemIds": ["${cartId}"]}, None))
    if "五态" in crit or "确认" in crit and "商家" in crit or "发货" in crit or "备货" in crit:
        primary.append(("POST", "/api/admin/orders/${orderId}/actions", {"action": "CONFIRM", "expectedStatus": "PLACED"}, None))

    steps = [
        step(1, "CUSTOMER_A", "登录", http("POST", "/api/auth/login", body={"username": "b030_buyer_a", "password": "B030-BuyerA-Pass9"}), extract={"tokenA": "data.token"}),
    ]
    n = 2
    if "SELLER" in roles:
        steps.append(step(n, "SELLER", "登录", http("POST", "/api/admin/auth/login", body={"username": "admin", "password": "${B030_SELLER_PASSWORD}"}), extract={"tokenS": "data.token"}))
        n += 1
    steps.append(step(n, "SETUP", "按 fixture 准备初始态", {"fixtures": fixtures, "reset": f"python3 scripts/reset_namespace.py --case-id {ac['ac_id']}-GEN"}))
    n += 1
    for method, path, body, msg in primary:
        hdr = {"Authorization": "Bearer ${tokenA}"}
        if method == "POST" and ("cart/items" in path or "/orders" == path.split("?")[0].rstrip("/").endswith("orders") or "move-to-favorites" in path):
            if path.endswith("/orders") or "cart/items" in path or "move-to-favorites" in path:
                hdr["Idempotency-Key"] = "${uuid}"
        if "admin" in path:
            hdr["Authorization"] = "Bearer ${tokenS}"
        steps.append(step(n, "ACTOR", f"{method} {path}", http(method, path, headers=hdr, body=body), assert_={"message": msg} if msg and msg in quotes["required_messages"] or (msg and msg in FIXED) else {"http_ok_or_expected_error": True}))
        n += 1
    steps.append(step(n, "DB", "按 AC 语义断言", {"sql": sql_snap("after"), "rules": crit}))
    n += 1
    steps.append(step(n, "NEG_CHECK", "若 AC 含拒绝条件则另会话触发并核消息", {"required_messages": quotes["required_messages"], "forbidden": quotes["forbidden_labels_or_states"]}))

    kind = "CON" if any(k in crit for k in ("并发", "同时", "多端")) else ("NEG" if any(k in crit for k in ("拒绝", "不可", "未登录", "无权")) else ("BND" if any(k in crit for k in ("边界", "重复", "幂等", "0")) else "POS"))
    base(kind, f"{ac['ac_id']} 可执行主用例", roles, fixtures, steps, {
        "response": "符合验收标准原文；固定文案仅使用 required_messages",
        "required_messages": quotes["required_messages"],
        "forbidden": quotes["forbidden_labels_or_states"],
        "ui_labels": quotes["ui_labels"],
        "db": "无禁止中间态；失败则相关表无变化",
        "page": "前端透传 message 原文，不替换为无货/缺货/超限/下单历史",
    })


def render_case_md(case: dict) -> str:
    lines = []
    lines.append(f"## {case['case_id']} · {case['title']}")
    lines.append("")
    lines.append(f"- AC：`{case['ac_id']}` · PB：`{case['pb_id']}` · 类型：`{case['kind']}` · 状态：**{case['status']}**")
    lines.append(f"- V3：`{case['v3']}` · 场景：`{case['scene']}`")
    lines.append(f"- 实现任务：{case['impl_tasks']} · 测试任务：{case['test_tasks']}")
    lines.append(f"- 角色/会话：{', '.join(case['roles'])} / {', '.join(case['sessions'])}")
    lines.append(f"- Fixtures：{', '.join(case['fixtures']) if case['fixtures'] else '（无商品 fixture）'}")
    if case.get("maps_to_seq"):
        lines.append(f"- 并发 SEQ：`{case['maps_to_seq']}` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`")
    if case.get("pages"):
        lines.append(f"- 页面：{', '.join(case['pages'])}")
    lines.append("")
    lines.append("### 验收标准原文")
    lines.append("")
    lines.append(case["criteria"])
    lines.append("")
    q = case["quotes"]
    lines.append("### 文案/标签语义分类（禁止机械摘引号）")
    lines.append("")
    lines.append(f"- **必须匹配的接口提示（fixedMessages）**：{', '.join('「'+m+'」' for m in q['required_messages']) or '（本 AC 无强制成功/失败提示，或见步骤内 assert）'}")
    lines.append(f"- **禁止作为状态/中间态/旧规则出现**：{', '.join('「'+m+'」' for m in q['forbidden_labels_or_states']) or '（无）'}")
    lines.append(f"- **UI 状态标签（非错误提示）**：{', '.join('「'+m+'」' for m in q['ui_labels']) or '（无）'}")
    lines.append("")
    lines.append("### 前置")
    lines.append("")
    for p in case["pre"]:
        lines.append(f"1. {p}" if not p.startswith("1.") else f"- {p}")
    # fix numbering
    lines = lines[:-len(case["pre"])]
    for i, p in enumerate(case["pre"], 1):
        lines.append(f"{i}. {p}")
    lines.append("")
    lines.append("### 步骤（可直接执行）")
    lines.append("")
    for s in case["steps"]:
        lines.append(f"#### 步骤 {s['n']} · {s['actor']} · {s['action']}")
        lines.append("")
        detail = s["detail"]
        if isinstance(detail, dict) and "http" in detail:
            h = detail["http"]
            lines.append(f"- HTTP `{h['method']}` `{h['path']}`")
            if h.get("headers"):
                lines.append(f"- Headers：`{json.dumps(h['headers'], ensure_ascii=False)}`")
            if h.get("body") is not None:
                lines.append(f"- Body：`{json.dumps(h['body'], ensure_ascii=False)}`")
        else:
            lines.append(f"- 操作：`{json.dumps(detail, ensure_ascii=False)}`")
        if s.get("extract"):
            lines.append(f"- 提取：`{json.dumps(s['extract'], ensure_ascii=False)}`")
        if s.get("assert"):
            lines.append(f"- 断言：`{json.dumps(s['assert'], ensure_ascii=False)}`")
        lines.append("")
    lines.append("### 期望（响应 / 页面 / DB）")
    lines.append("")
    for k, v in case["expects"].items():
        lines.append(f"- **{k}**：{v if not isinstance(v, list) else '、'.join(map(str, v))}")
    lines.append("")
    lines.append("### DB 断言 SQL")
    lines.append("")
    lines.append("```sql")
    lines.append("\n".join(case["db_assert_sql"]))
    lines.append("```")
    lines.append("")
    lines.append("### 清理")
    lines.append("")
    for c in case["cleanup"]:
        lines.append(f"- `{c}`" if c.startswith("python") or c.startswith("证据") else f"- {c}")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def main():
    all_cases = []
    by_pb = defaultdict(list)
    for ac in ACS:
        cs = build_cases_for_ac(ac)
        all_cases.extend(cs)
        by_pb[ac["pb_id"]].extend(cs)

    cases_dir = ROOT / "cases"
    cases_dir.mkdir(exist_ok=True)
    # remove old root PB-*.md later in shell

    index_rows = []
    for pb in sorted(by_pb.keys()):
        cs = by_pb[pb]
        body = [f"# {pb} · B-030 可执行用例（重写）", "", f"> 全部状态：**待执行**。未跑业务验收不得标通过。", f"> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。", ""]
        for c in cs:
            body.append(render_case_md(c))
            index_rows.append((c["ac_id"], c["case_id"], c["kind"], c.get("maps_to_seq") or "", pb))
        (cases_dir / f"{pb}.md").write_text("\n".join(body), encoding="utf-8")

    manifest = {
        "ac_count": len(ACS),
        "case_count": len(all_cases),
        "cases": [
            {
                "case_id": c["case_id"],
                "ac_id": c["ac_id"],
                "kind": c["kind"],
                "seq": c.get("maps_to_seq"),
                "fixtures": c["fixtures"],
                "required_messages": c["quotes"]["required_messages"],
                "forbidden": c["quotes"]["forbidden_labels_or_states"],
                "status": c["status"],
            }
            for c in all_cases
        ],
    }
    (ROOT / "cases" / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    idx = ["# B-030 AC/用例索引（重写）", "", f"- AC：**{len(ACS)}**", f"- 可执行用例：**{len(all_cases)}**（按语义拆分，不追求固定编号数）", "- 状态：全部待执行", "",
           "| AC | case_id | kind | SEQ | 文件 |", "|---|---|---|---|---|"]
    for ac_id, case_id, kind, seq, pb in index_rows:
        idx.append(f"| {ac_id} | {case_id} | {kind} | {seq or '—'} | [cases/{pb}.md](./cases/{pb}.md) |")
    (ROOT / "00-索引.md").write_text("\n".join(idx), encoding="utf-8")
    print(f"generated AC={len(ACS)} cases={len(all_cases)} pbs={len(by_pb)}")


if __name__ == "__main__":
    main()
