# PB-B02 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B02-AC1-POS · 下单直接扣剩余可售库存且完成不再扣

- AC：`PB-B02-AC1` · PB：`PB-B02` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.2` · 场景：`V07 / W09`
- 实现任务：B-003、B-006、B-011、B-013、B-024 · 测试任务：B-028、B-032、B-033、B-035
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

库存采用口径 A，且为直接扣减、不是预占。系统只维护一个库存数值，含义为剩余可售量；下单成功时按订单快照数量当场从该值扣减，没有独立的「已扣减量」事后对齐。交易完成不再重复扣减，确认、备货、完成均不再校验库存。取消回补规则见 `US-B05` / `PB-B05`（`US-B07` / `PB-B07` 交叉引用，不另定口径）。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：「已扣减量」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B02-AC1-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · DB · stock_before=10

- 操作：`{"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-10';"]}`

#### 步骤 2 · CUSTOMER_A · 下单 qty=3

- 操作：`{"ref": "helper:place_order", "product": "P-ON-10", "qty": "3"}`

#### 步骤 3 · DB · stock=7

- 操作：`{"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-10'; -- 7"]}`

#### 步骤 4 · SELLER · 推进至 COMPLETED

- 操作：`{"ref": "helper:advance_to", "status": "COMPLETED"}`

#### 步骤 5 · DB · 完成后再读 stock 仍为 7

- 操作：`{"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-10'; -- 7"]}`

### 期望（响应 / 页面 / DB）

- **response**：下单成功
- **db**：仅下单扣减；无独立已扣减量字段对齐；确认/备货/完成不改库存
- **forbidden**：已扣减量

### DB 断言 SQL

```sql
-- snapshot after
SELECT id, stock, status, offline_reason FROM product WHERE name LIKE 'B030-%' ORDER BY name;
SELECT id, username FROM customer WHERE username LIKE 'b030_%';
SELECT so.id, so.order_no, so.status, so.total_amount, so.cancelled_by, c.username FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%' ORDER BY so.id;
SELECT oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.line_amount FROM order_item oi JOIN shop_order so ON so.id=oi.order_id JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%';
SELECT ci.id, c.username, ci.product_id, ci.quantity FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username LIKE 'b030_%';
SELECT f.id, c.username, f.product_id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username LIKE 'b030_%';
SELECT COUNT(*) AS intent_cnt FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id WHERE c.username LIKE 'b030_%' AND pi.legacy_closed_at IS NULL;
```

### 清理

- `python3 scripts/reset_namespace.py --case-id PB-B02-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B02-AC2-POS · 他客看到扣后余量；下架不影响已单

- AC：`PB-B02-AC2` · PB：`PB-B02` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.2` · 场景：`V07 / W09`
- 实现任务：B-003、B-006、B-011、B-013、B-024 · 测试任务：B-028、B-032、B-033、B-035
- 角色/会话：CUSTOMER_A, CUSTOMER_B, SELLER / S-CUSTOMER_A, S-CUSTOMER_B, S-SELLER
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-01` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

防超卖由「下单即扣」保证。其他客户下单时看到的是已扣减后的剩余可售量。商品下架不影响已下单订单（快照与流转不变），只是不再接受新订单。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B02-AC2-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 下单 qty=4

- 操作：`{"ref": "helper:place_order", "qty": "4"}`

#### 步骤 2 · CUSTOMER_B · 读商品可售

- HTTP `GET` `/api/products/${P-ON-10.id}`

#### 步骤 3 · SELLER · 下架商品

- HTTP `POST` `/api/admin/products/${P-ON-10.id}/offline`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`

#### 步骤 4 · SELLER · 原单仍可 CONFIRM

- HTTP `POST` `/api/admin/orders/${orderId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"action": "CONFIRM", "expectedStatus": "PLACED"}`
- 断言：`{"data.status": "CONFIRMED"}`

### 期望（响应 / 页面 / DB）

- **db**：已单快照不变；新订单不可再下
- **forbidden**：

### DB 断言 SQL

```sql
-- snapshot after
SELECT id, stock, status, offline_reason FROM product WHERE name LIKE 'B030-%' ORDER BY name;
SELECT id, username FROM customer WHERE username LIKE 'b030_%';
SELECT so.id, so.order_no, so.status, so.total_amount, so.cancelled_by, c.username FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%' ORDER BY so.id;
SELECT oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.line_amount FROM order_item oi JOIN shop_order so ON so.id=oi.order_id JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%';
SELECT ci.id, c.username, ci.product_id, ci.quantity FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username LIKE 'b030_%';
SELECT f.id, c.username, f.product_id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username LIKE 'b030_%';
SELECT COUNT(*) AS intent_cnt FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id WHERE c.username LIKE 'b030_%' AND pi.legacy_closed_at IS NULL;
```

### 清理

- `python3 scripts/reset_namespace.py --case-id PB-B02-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B02-AC3-POS · 商家改库存任意非负整数；0 自动下架

- AC：`PB-B02-AC3` · PB：`PB-B02` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.2` · 场景：`V07 / W09`
- 实现任务：B-003、B-006、B-011、B-013、B-024 · 测试任务：B-028、B-032、B-033、B-035
- 角色/会话：SELLER / S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

库存须为非负整数，无硬上限，仅受非负整数约束。商家可将该商品的可售库存改为任意非负整数，不影响已下单订单的快照与已发生扣减，只影响未来新订单。改为 0 允许，并触发自动下架。改为负数、小数或非整数时，整次拒绝并保持原库存，提示「库存不能为负数，请输入非负整数。」不采用「不得低于未完成订单扣减总量」的预占下限。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「库存不能为负数，请输入非负整数。」
- **禁止作为状态/中间态/旧规则出现**：「不得低于未完成订单扣减总量」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B02-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SELLER · PATCH stock=42

- HTTP `PATCH` `/api/admin/products/${P-ON-10.id}`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"stock": "42"}`
- 断言：`{"http": 200}`

#### 步骤 2 · SELLER · PATCH stock=0

- HTTP `PATCH` `/api/admin/products/${P-ON-10.id}`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"stock": "0"}`
- 断言：`{"http": 200}`

#### 步骤 3 · DB · OFFLINE AUTO_ZERO

- 操作：`{"sql": ["SELECT stock,status,offline_reason FROM product WHERE id=${P-ON-10.id}; -- 0,OFFLINE,AUTO_ZERO"]}`

### 期望（响应 / 页面 / DB）

- **db**：已单快照不受影响
- **forbidden**：

### DB 断言 SQL

```sql
-- snapshot after
SELECT id, stock, status, offline_reason FROM product WHERE name LIKE 'B030-%' ORDER BY name;
SELECT id, username FROM customer WHERE username LIKE 'b030_%';
SELECT so.id, so.order_no, so.status, so.total_amount, so.cancelled_by, c.username FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%' ORDER BY so.id;
SELECT oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.line_amount FROM order_item oi JOIN shop_order so ON so.id=oi.order_id JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%';
SELECT ci.id, c.username, ci.product_id, ci.quantity FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username LIKE 'b030_%';
SELECT f.id, c.username, f.product_id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username LIKE 'b030_%';
SELECT COUNT(*) AS intent_cnt FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id WHERE c.username LIKE 'b030_%' AND pi.legacy_closed_at IS NULL;
```

### 清理

- `python3 scripts/reset_namespace.py --case-id PB-B02-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B02-AC3-NEG · 负数/小数库存拒绝

- AC：`PB-B02-AC3` · PB：`PB-B02` · 类型：`NEG` · 状态：**待执行**
- V3：`5.3.2` · 场景：`V07 / W09`
- 实现任务：B-003、B-006、B-011、B-013、B-024 · 测试任务：B-028、B-032、B-033、B-035
- 角色/会话：SELLER / S-SELLER
- Fixtures：P-ON-5

### 验收标准原文

库存须为非负整数，无硬上限，仅受非负整数约束。商家可将该商品的可售库存改为任意非负整数，不影响已下单订单的快照与已发生扣减，只影响未来新订单。改为 0 允许，并触发自动下架。改为负数、小数或非整数时，整次拒绝并保持原库存，提示「库存不能为负数，请输入非负整数。」不采用「不得低于未完成订单扣减总量」的预占下限。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「库存不能为负数，请输入非负整数。」
- **禁止作为状态/中间态/旧规则出现**：「不得低于未完成订单扣减总量」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B02-AC3-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · DB · stock_before

- 操作：`{"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-5';"]}`
- 提取：`{"stock_before": "stock"}`

#### 步骤 2 · SELLER · stock=-1

- HTTP `PATCH` `/api/admin/products/${P-ON-5.id}`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"stock": "-1"}`
- 断言：`{"message": "库存不能为负数，请输入非负整数。"}`

#### 步骤 3 · SELLER · stock=1.5

- HTTP `PATCH` `/api/admin/products/${P-ON-5.id}`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"stock": "1.5"}`
- 断言：`{"message": "库存不能为负数，请输入非负整数。"}`

#### 步骤 4 · DB · 不变

- 操作：`{"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-5'; -- == stock_before"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：库存不能为负数，请输入非负整数。
- **db**：原库存保持

### DB 断言 SQL

```sql
-- snapshot after
SELECT id, stock, status, offline_reason FROM product WHERE name LIKE 'B030-%' ORDER BY name;
SELECT id, username FROM customer WHERE username LIKE 'b030_%';
SELECT so.id, so.order_no, so.status, so.total_amount, so.cancelled_by, c.username FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%' ORDER BY so.id;
SELECT oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.line_amount FROM order_item oi JOIN shop_order so ON so.id=oi.order_id JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%';
SELECT ci.id, c.username, ci.product_id, ci.quantity FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username LIKE 'b030_%';
SELECT f.id, c.username, f.product_id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username LIKE 'b030_%';
SELECT COUNT(*) AS intent_cnt FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id WHERE c.username LIKE 'b030_%' AND pi.legacy_closed_at IS NULL;
```

### 清理

- `python3 scripts/reset_namespace.py --case-id PB-B02-AC3-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B02-AC4-NEG · PB-B02-AC4 可执行主用例

- AC：`PB-B02-AC4` · PB：`PB-B02` · 类型：`NEG` · 状态：**待执行**
- V3：`5.3.2` · 场景：`V07 / W09`
- 实现任务：B-003、B-006、B-011、B-013、B-024 · 测试任务：B-028、B-032、B-033、B-035
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10, P-ON-1, P-ON-0, P-OFF-M

### 验收标准原文

因下单扣减或商家将库存改为 0，使库存变为 0 时，商品自动下架：买家端不可见、不可打开详情、不可再被加入新订单。将库存从 0 改为正数，本身不会自动上架，须商家手动上架后才可再次在售；仅取消回补触发的自动恢复在售见 `US-B05` / `PB-B05`。商家手动下架（库存仍大于 0）后，库存大于 0 时允许手动上架，不必重新发布。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B02-AC4-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 登录

- HTTP `POST` `/api/auth/login`
- Body：`{"username": "b030_buyer_a", "password": "B030-BuyerA-Pass9"}`
- 提取：`{"tokenA": "data.token"}`

#### 步骤 2 · SELLER · 登录

- HTTP `POST` `/api/admin/auth/login`
- Body：`{"username": "admin", "password": "${B030_SELLER_PASSWORD}"}`
- 提取：`{"tokenS": "data.token"}`

#### 步骤 3 · SETUP · 按 fixture 准备初始态

- 操作：`{"fixtures": ["P-ON-10", "P-ON-1", "P-ON-0", "P-OFF-M"], "reset": "python3 scripts/reset_namespace.py --case-id PB-B02-AC4-GEN"}`

#### 步骤 4 · ACTOR · POST /api/me/checkout/confirmations

- HTTP `POST` `/api/me/checkout/confirmations`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"cartItemIds": ["${cartId}"]}`
- 断言：`{"http_ok_or_expected_error": true}`

#### 步骤 5 · ACTOR · POST /api/me/orders

- HTTP `POST` `/api/me/orders`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"confirmationToken": "${confirmationToken}"}`
- 断言：`{"message": "下单成功"}`

#### 步骤 6 · ACTOR · POST /api/admin/orders/${orderId}/cancel

- HTTP `POST` `/api/admin/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"expectedStatus": "${status}"}`
- 断言：`{"http_ok_or_expected_error": true}`

#### 步骤 7 · DB · 按 AC 语义断言

- 操作：`{"sql": ["-- snapshot after", "SELECT id, stock, status, offline_reason FROM product WHERE name LIKE 'B030-%' ORDER BY name;", "SELECT id, username FROM customer WHERE username LIKE 'b030_%';", "SELECT so.id, so.order_no, so.status, so.total_amount, so.cancelled_by, c.username FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%' ORDER BY so.id;", "SELECT oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.line_amount FROM order_item oi JOIN shop_order so ON so.id=oi.order_id JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%';", "SELECT ci.id, c.username, ci.product_id, ci.quantity FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username LIKE 'b030_%';", "SELECT f.id, c.username, f.product_id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username LIKE 'b030_%';", "SELECT COUNT(*) AS intent_cnt FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id WHERE c.username LIKE 'b030_%' AND pi.legacy_closed_at IS NULL;"], "rules": "因下单扣减或商家将库存改为 0，使库存变为 0 时，商品自动下架：买家端不可见、不可打开详情、不可再被加入新订单。将库存从 0 改为正数，本身不会自动上架，须商家手动上架后才可再次在售；仅取消回补触发的自动恢复在售见 `US-B05` / `PB-B05`。商家手动下架（库存仍大于 0）后，库存大于 0 时允许手动上架，不必重新发布。"}`

#### 步骤 8 · NEG_CHECK · 若 AC 含拒绝条件则另会话触发并核消息

- 操作：`{"required_messages": [], "forbidden": []}`

### 期望（响应 / 页面 / DB）

- **response**：符合验收标准原文；固定文案仅使用 required_messages
- **required_messages**：
- **forbidden**：
- **ui_labels**：
- **db**：无禁止中间态；失败则相关表无变化
- **page**：前端透传 message 原文，不替换为无货/缺货/超限/下单历史

### DB 断言 SQL

```sql
-- snapshot after
SELECT id, stock, status, offline_reason FROM product WHERE name LIKE 'B030-%' ORDER BY name;
SELECT id, username FROM customer WHERE username LIKE 'b030_%';
SELECT so.id, so.order_no, so.status, so.total_amount, so.cancelled_by, c.username FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%' ORDER BY so.id;
SELECT oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.line_amount FROM order_item oi JOIN shop_order so ON so.id=oi.order_id JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%';
SELECT ci.id, c.username, ci.product_id, ci.quantity FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username LIKE 'b030_%';
SELECT f.id, c.username, f.product_id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username LIKE 'b030_%';
SELECT COUNT(*) AS intent_cnt FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id WHERE c.username LIKE 'b030_%' AND pi.legacy_closed_at IS NULL;
```

### 清理

- `python3 scripts/reset_namespace.py --case-id PB-B02-AC4-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B02-AC5-BND · PB-B02-AC5 可执行主用例

- AC：`PB-B02-AC5` · PB：`PB-B02` · 类型：`BND` · 状态：**待执行**
- V3：`5.3.2` · 场景：`V07 / W09`
- 实现任务：B-003、B-006、B-011、B-013、B-024 · 测试任务：B-028、B-032、B-033、B-035
- 角色/会话：CUSTOMER_A, SELLER, CUSTOMER_B / S-CUSTOMER_A, S-SELLER, S-CUSTOMER_B
- Fixtures：P-ON-10, P-ON-1, P-ON-0, P-OFF-M

### 验收标准原文

库存口径在各场景下的变化如下，后续条目不得写成与本表冲突的另一套规则：

| 场景 | 库存变化 |
| --- | --- |
| 下单成功 | 按订单快照数量直接扣减 |
| 完成前取消（客户或商家） | 按订单快照数量回补（详见 PB-B05、PB-B07） |
| 交易完成成功 | 不变（下单时已扣，完成不再扣） |
| 交易完成时库存不足 | 不适用（口径 A 下无此场景） |
| 因库存为 0 被自动下架，且本次取消把库存补回大于 0 | 自动恢复在售（详见 PB-B05） |
| 商家手动下架（库存仍大于 0）后取消 | 保持已下架，须商家手动上架（详见 PB-B05） |

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B02-AC5-BND
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 登录

- HTTP `POST` `/api/auth/login`
- Body：`{"username": "b030_buyer_a", "password": "B030-BuyerA-Pass9"}`
- 提取：`{"tokenA": "data.token"}`

#### 步骤 2 · SELLER · 登录

- HTTP `POST` `/api/admin/auth/login`
- Body：`{"username": "admin", "password": "${B030_SELLER_PASSWORD}"}`
- 提取：`{"tokenS": "data.token"}`

#### 步骤 3 · SETUP · 按 fixture 准备初始态

- 操作：`{"fixtures": ["P-ON-10", "P-ON-1", "P-ON-0", "P-OFF-M"], "reset": "python3 scripts/reset_namespace.py --case-id PB-B02-AC5-GEN"}`

#### 步骤 4 · ACTOR · POST /api/me/checkout/confirmations

- HTTP `POST` `/api/me/checkout/confirmations`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"cartItemIds": ["${cartId}"]}`
- 断言：`{"http_ok_or_expected_error": true}`

#### 步骤 5 · ACTOR · POST /api/me/orders

- HTTP `POST` `/api/me/orders`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"confirmationToken": "${confirmationToken}"}`
- 断言：`{"message": "下单成功"}`

#### 步骤 6 · ACTOR · POST /api/admin/orders/${orderId}/cancel

- HTTP `POST` `/api/admin/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"expectedStatus": "${status}"}`
- 断言：`{"http_ok_or_expected_error": true}`

#### 步骤 7 · DB · 按 AC 语义断言

- 操作：`{"sql": ["-- snapshot after", "SELECT id, stock, status, offline_reason FROM product WHERE name LIKE 'B030-%' ORDER BY name;", "SELECT id, username FROM customer WHERE username LIKE 'b030_%';", "SELECT so.id, so.order_no, so.status, so.total_amount, so.cancelled_by, c.username FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%' ORDER BY so.id;", "SELECT oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.line_amount FROM order_item oi JOIN shop_order so ON so.id=oi.order_id JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%';", "SELECT ci.id, c.username, ci.product_id, ci.quantity FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username LIKE 'b030_%';", "SELECT f.id, c.username, f.product_id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username LIKE 'b030_%';", "SELECT COUNT(*) AS intent_cnt FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id WHERE c.username LIKE 'b030_%' AND pi.legacy_closed_at IS NULL;"], "rules": "库存口径在各场景下的变化如下，后续条目不得写成与本表冲突的另一套规则：\n\n| 场景 | 库存变化 |\n| --- | --- |\n| 下单成功 | 按订单快照数量直接扣减 |\n| 完成前取消（客户或商家） | 按订单快照数量回补（详见 PB-B05、PB-B07） |\n| 交易完成成功 | 不变（下单时已扣，完成不再扣） |\n| 交易完成时库存不足 | 不适用（口径 A 下无此场景） |\n| 因库存为 0 被自动下架，且本次取消把库存补回大于 0 | 自动恢复在售（详见 PB-B05） |\n| 商家手动下架（库存仍大于 0）后取消 | 保持已下架，须商家手动上架（详见 PB-B05） |"}`

#### 步骤 8 · NEG_CHECK · 若 AC 含拒绝条件则另会话触发并核消息

- 操作：`{"required_messages": [], "forbidden": []}`

### 期望（响应 / 页面 / DB）

- **response**：符合验收标准原文；固定文案仅使用 required_messages
- **required_messages**：
- **forbidden**：
- **ui_labels**：
- **db**：无禁止中间态；失败则相关表无变化
- **page**：前端透传 message 原文，不替换为无货/缺货/超限/下单历史

### DB 断言 SQL

```sql
-- snapshot after
SELECT id, stock, status, offline_reason FROM product WHERE name LIKE 'B030-%' ORDER BY name;
SELECT id, username FROM customer WHERE username LIKE 'b030_%';
SELECT so.id, so.order_no, so.status, so.total_amount, so.cancelled_by, c.username FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%' ORDER BY so.id;
SELECT oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.line_amount FROM order_item oi JOIN shop_order so ON so.id=oi.order_id JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%';
SELECT ci.id, c.username, ci.product_id, ci.quantity FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username LIKE 'b030_%';
SELECT f.id, c.username, f.product_id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username LIKE 'b030_%';
SELECT COUNT(*) AS intent_cnt FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id WHERE c.username LIKE 'b030_%' AND pi.legacy_closed_at IS NULL;
```

### 清理

- `python3 scripts/reset_namespace.py --case-id PB-B02-AC5-BND`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
