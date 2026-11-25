# PB-B01 · B-030 可执行用例

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B01-AC1-POS · 多商品多数量建一张新订单且不进旧意向

- AC：`PB-B01-AC1` · PB：`PB-B01` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.1` · 场景：`V06 / W08`
- 实现任务：B-001、B-011、B-013、B-023 · 测试任务：B-032、B-033、B-036
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 页面：/buyer/orders, /buyer/cart

### 验收标准原文

新订单不再进入旧意向队列，不冻结队首，不使用「失败」状态，也不再「每笔数量固定为 1」。一次提交所选商品只生成一张订单，不拆单；一单可含多个不同商品，同一商品也可购买多件，对应一条订单明细。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：「失败」, 「每笔数量固定为 1」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B01-AC1-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 登录

- HTTP `POST` `/api/auth/login`
- Body：`{"username": "b030_buyer_a", "password": "B030-BuyerA-Pass9"}`
- 提取：`{"tokenA": "data.token"}`

#### 步骤 2 · CUSTOMER_A · 加购 P-ON-10

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${uuid1}"}`
- Body：`{"productId": "${P-ON-10.id}"}`
- 提取：`{"cart10": "data.cartItemId"}`
- 断言：`{"http": 200, "message": "已加入购物车"}`

#### 步骤 3 · CUSTOMER_A · 改数量为 3

- HTTP `PATCH` `/api/me/cart/items/${cart10}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "3"}`
- 断言：`{"http": 200, "message": "已更新", "data.quantity": "3"}`

#### 步骤 4 · CUSTOMER_A · 加购 P-ON-5

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${uuid2}"}`
- Body：`{"productId": "${P-ON-5.id}"}`
- 提取：`{"cart5": "data.cartItemId"}`
- 断言：`{"http": 200, "message": "已加入购物车"}`

#### 步骤 5 · CUSTOMER_A · 改数量为 2

- HTTP `PATCH` `/api/me/cart/items/${cart5}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "2"}`
- 断言：`{"http": 200, "data.quantity": "2"}`

#### 步骤 6 · CUSTOMER_A · 创建确认单

- HTTP `POST` `/api/me/checkout/confirmations`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"cartItemIds": ["${cart10}", "${cart5}"]}`
- 提取：`{"confirmationToken": "data.confirmationToken"}`
- 断言：`{"http": 200}`

#### 步骤 7 · CUSTOMER_A · 提交订单

- HTTP `POST` `/api/me/orders`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${uuidSubmit}"}`
- Body：`{"confirmationToken": "${confirmationToken}"}`
- 提取：`{"orderId": "data.id", "orderNo": "data.orderNo"}`
- 断言：`{"http": [200, 201], "message": "下单成功", "data.status": "PLACED", "data.items.length": 2}`

#### 步骤 8 · DB · 核对

- 操作：`{"sql": ["SELECT COUNT(*) c FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username='b030_buyer_a' AND so.status='PLACED'; -- expect 1", "SELECT quantity FROM order_item WHERE order_id=${orderId} ORDER BY product_id; -- expect 2 and 3 (one row per product)", "SELECT COUNT(*) c FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id WHERE c.username='b030_buyer_a' AND pi.legacy_closed_at IS NULL; -- expect 0 new intent", "SELECT status FROM shop_order WHERE id=${orderId}; -- must NOT be FAILED / 失败"]}`

### 期望（响应 / 页面 / DB）

- **response**：单订单；明细两条；数量分别为 3 与 2；message=下单成功
- **page**：订单历史出现该单；无旧意向队列入口冻结；状态文案不是「失败」；不展示「每笔数量固定为 1」
- **db**：仅 shop_order/order_item；无新 purchase_intent；status=PLACED
- **forbidden**：失败、每笔数量固定为 1

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

- `python3 scripts/reset_namespace.py --case-id PB-B01-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B01-AC2-POS · 商家依次推进五态不可跳步

- AC：`PB-B01-AC2` · PB：`PB-B01` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.1` · 场景：`V06 / W08`
- 实现任务：B-001、B-011、B-013、B-023 · 测试任务：B-032、B-033、B-036
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10
- 页面：/admin/orders

### 验收标准原文

五态作用于整单，必须依次单向流转：客户下单 → 商家确认 → 备货完成 → 开始发货 → 交易完成。不允许跳步、回退、自动流转，也不支持部分确认、部分发货或部分完成。客户不可推进状态；商家登录后台后依次执行确认、备货完成、开始发货、交易完成。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B01-AC2-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 登录并建 PLACED 单（P-ON-10×1）

- 操作（已展开）：
**实现（勿留悬空 helper）**
```bash
python3 scripts/reset_namespace.py --case-id $CASE_ID
python3 scripts/run_helper.py place_order --product P-ON-10 --qty 1
# 等价 HTTP：
# 1) POST /api/auth/login {username:b030_buyer_a,password:B030-BuyerA-Pass9} → tokenA
# 2) POST /api/me/cart/items + Idempotency-Key 新 UUID  body={productId:$(P-ON-10.id)} → cartItemId
# 3) PATCH /api/me/cart/items/{cartItemId} {quantity:"1"} （若 qty≠1）
# 4) POST /api/me/checkout/confirmations {cartItemIds:[cartItemId]} → confirmationToken
# 5) POST /api/me/orders + Idempotency-Key  body={confirmationToken} → orderId/orderNo；message=下单成功
```
提取：`orderId`、`orderNo`、`tokenA`
- 提取：`{"orderId": "order.id"}`

#### 步骤 2 · SELLER · 登录后台

- HTTP `POST` `/api/admin/auth/login`
- Body：`{"username": "admin", "password": "${B030_SELLER_PASSWORD}"}`
- 提取：`{"tokenS": "data.token"}`

#### 步骤 3 · SELLER · CONFIRM

- HTTP `POST` `/api/admin/orders/${orderId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"action": "CONFIRM", "expectedStatus": "PLACED"}`
- 断言：`{"http": 200, "data.status": "CONFIRMED"}`

#### 步骤 4 · SELLER · 跳步 SHIP 应拒绝

- HTTP `POST` `/api/admin/orders/${orderId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"action": "SHIP", "expectedStatus": "CONFIRMED"}`
- 断言：`{"http_not": 200, "data.status_unchanged": "CONFIRMED"}`

#### 步骤 5 · SELLER · PREPARE

- HTTP `POST` `/api/admin/orders/${orderId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"action": "PREPARE", "expectedStatus": "CONFIRMED"}`
- 断言：`{"data.status": "PREPARED"}`

#### 步骤 6 · SELLER · SHIP

- HTTP `POST` `/api/admin/orders/${orderId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"action": "SHIP", "expectedStatus": "PREPARED"}`
- 断言：`{"data.status": "SHIPPED"}`

#### 步骤 7 · SELLER · COMPLETE

- HTTP `POST` `/api/admin/orders/${orderId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"action": "COMPLETE", "expectedStatus": "SHIPPED"}`
- 断言：`{"data.status": "COMPLETED"}`

#### 步骤 8 · CUSTOMER_A · 客户不可推进

- HTTP `POST` `/api/admin/orders/${orderId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"action": "CONFIRM", "expectedStatus": "PLACED"}`
- 断言：`{"forbidden": true}`

### 期望（响应 / 页面 / DB）

- **response**：仅顺序 CONFIRM→PREPARE→SHIP→COMPLETE 成功；跳步失败且状态不变
- **page**：商家订单管理五态按钮按序；客户侧无推进控件
- **db**：最终 COMPLETED；无回退记录
- **forbidden**：部分确认、部分发货、自动流转

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

- `python3 scripts/reset_namespace.py --case-id PB-B01-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B01-AC2-NEG · 客户尝试推进状态被拒

- AC：`PB-B01-AC2` · PB：`PB-B01` · 类型：`NEG` · 状态：**待执行**
- V3：`5.3.1` · 场景：`V06 / W08`
- 实现任务：B-001、B-011、B-013、B-023 · 测试任务：B-032、B-033、B-036
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

五态作用于整单，必须依次单向流转：客户下单 → 商家确认 → 备货完成 → 开始发货 → 交易完成。不允许跳步、回退、自动流转，也不支持部分确认、部分发货或部分完成。客户不可推进状态；商家登录后台后依次执行确认、备货完成、开始发货、交易完成。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B01-AC2-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 持有 PLACED 单

- 操作（已展开）：
**实现（勿留悬空 helper）**
```bash
python3 scripts/reset_namespace.py --case-id $CASE_ID
python3 scripts/run_helper.py place_order --product P-ON-10 --qty 1
# 等价 HTTP：
# 1) POST /api/auth/login {username:b030_buyer_a,password:B030-BuyerA-Pass9} → tokenA
# 2) POST /api/me/cart/items + Idempotency-Key 新 UUID  body={productId:$(P-ON-10.id)} → cartItemId
# 3) PATCH /api/me/cart/items/{cartItemId} {quantity:"1"} （若 qty≠1）
# 4) POST /api/me/checkout/confirmations {cartItemIds:[cartItemId]} → confirmationToken
# 5) POST /api/me/orders + Idempotency-Key  body={confirmationToken} → orderId/orderNo；message=下单成功
```
提取：`orderId`、`orderNo`、`tokenA`
- 提取：`{"orderId": "order.id", "tokenA": "token"}`

#### 步骤 2 · CUSTOMER_A · 调用商家 actions

- HTTP `POST` `/api/admin/orders/${orderId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"action": "CONFIRM", "expectedStatus": "PLACED"}`
- 断言：`{"not_success": true}`

#### 步骤 3 · DB · 状态仍为 PLACED

- 操作：`{"sql": ["SELECT status FROM shop_order WHERE id=${orderId}; -- PLACED"]}`

### 期望（响应 / 页面 / DB）

- **response**：拒绝；订单不变
- **db**：status=PLACED
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

- `python3 scripts/reset_namespace.py --case-id PB-B01-AC2-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B01-AC3-POS · 终态完成与取消不可再流转

- AC：`PB-B01-AC3` · PB：`PB-B01` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.1` · 场景：`V06 / W08`
- 实现任务：B-001、B-011、B-013、B-023 · 测试任务：B-032、B-033、B-036
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

终态只有「交易完成」与「已取消」。已取消不可再流转、不可恢复。交易完成后双方均不可取消。无超时自动取消。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「交易完成」, 「已取消」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B01-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · BOTH · 准备 COMPLETED 单与 CANCELLED 单各一

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py seed_terminal_orders
# 产出 completedId / cancelledId / tokenA / tokenS
```

#### 步骤 2 · SELLER · 对 COMPLETED 再 COMPLETE/取消

- HTTP `POST` `/api/admin/orders/${completedId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"action": "COMPLETE", "expectedStatus": "COMPLETED"}`
- 断言：`{"rejected": true}`

#### 步骤 3 · CUSTOMER_A · 对 COMPLETED 取消

- HTTP `POST` `/api/me/orders/${completedId}/cancel`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"expectedStatus": "COMPLETED"}`
- 断言：`{"message": "订单已完成，不可取消"}`

#### 步骤 4 · SELLER · 对 CANCELLED 再推进

- HTTP `POST` `/api/admin/orders/${cancelledId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"action": "CONFIRM", "expectedStatus": "CANCELLED"}`
- 断言：`{"rejected": true}`

### 期望（响应 / 页面 / DB）

- **response**：终态操作拒绝；完成后取消提示「订单已完成，不可取消」；重复取消「订单已取消」
- **ui_labels**：交易完成、已取消
- **db**：终态不变；无超时自动取消任务副作用
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

- `python3 scripts/reset_namespace.py --case-id PB-B01-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B01-AC4-POS · 备货/发货/完成仅状态标记无需物流凭证

- AC：`PB-B01-AC4` · PB：`PB-B01` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.1` · 场景：`V06 / W08`
- 实现任务：B-001、B-011、B-013、B-023 · 测试任务：B-032、B-033、B-036
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10
- 页面：/admin/orders

### 验收标准原文

「备货完成」「开始发货」只是人工状态标记，不要求录入收货地址、承运商或运单号。商家标记「交易完成」只须点击确认，无需上传凭证、无需填写物流信息；点击后订单进入「交易完成」即通过验收。「线下交易完成」由商家自行确认，系统不做额外凭证校验。前置为订单已处于「开始发货」。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「备货完成」, 「开始发货」, 「交易完成」, 「线下交易完成」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B01-AC4-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SELLER · 将订单推到 PREPARED

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py advance_to --order-id "$ORDER_ID" --status PREPARED
# HTTP：按 PLACED→CONFIRMED→PREPARED→SHIPPED→COMPLETED 依次
# POST /api/admin/orders/{id}/actions {action, expectedStatus}
```

#### 步骤 2 · SELLER · SHIP 无地址/运单字段

- HTTP `POST` `/api/admin/orders/${orderId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"action": "SHIP", "expectedStatus": "PREPARED"}`
- 断言：`{"http": 200, "data.status": "SHIPPED"}`

#### 步骤 3 · SELLER · COMPLETE 仅确认

- HTTP `POST` `/api/admin/orders/${orderId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"action": "COMPLETE", "expectedStatus": "SHIPPED"}`
- 断言：`{"http": 200, "data.status": "COMPLETED"}`

#### 步骤 4 · UI · 页面

- 操作：`{"page": "/admin/orders/${orderId}", "assert": "无强制收货地址/承运商/运单号/凭证上传校验即可完成"}`

### 期望（响应 / 页面 / DB）

- **response**：SHIP/COMPLETE 成功无需额外字段
- **page**：人工标记即可；线下交易由商家确认
- **db**：status 到 COMPLETED；无物流附属表必填失败
- **ui_labels**：备货完成、开始发货、交易完成

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

- `python3 scripts/reset_namespace.py --case-id PB-B01-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B01-AC5-BND · 重复推进拒绝且不重复扣库

- AC：`PB-B01-AC5` · PB：`PB-B01` · 类型：`BND` · 状态：**待执行**
- V3：`5.3.1` · 场景：`V06 / W08`
- 实现任务：B-001、B-011、B-013、B-023 · 测试任务：B-032、B-033、B-036
- 角色/会话：SELLER / S-SELLER
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-12` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

重复推进同一状态、重复发货或重复完成：拒绝，状态不变，不重复扣库存。并发以系统先成功变更状态者为准，后到的冲突操作被拒绝，不覆盖已成功操作，不生成重复订单。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B01-AC5-BND
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SELLER · 订单已 CONFIRMED；记录 stock_before

- 操作：`{"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-10';"]}`
- 提取：`{"stock_before": "stock"}`

#### 步骤 2 · SELLER · 再次 CONFIRM

- HTTP `POST` `/api/admin/orders/${orderId}/actions`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- Body：`{"action": "CONFIRM", "expectedStatus": "CONFIRMED"}`
- 断言：`{"rejected": true}`

#### 步骤 3 · DB · 库存不变

- 操作：`{"sql": ["SELECT stock FROM product WHERE name='B030-在售足库存-10'; -- == stock_before"]}`

### 期望（响应 / 页面 / DB）

- **response**：拒绝；状态不变
- **db**：库存无二次扣减
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

- `python3 scripts/reset_namespace.py --case-id PB-B01-AC5-BND`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B01-AC5-CON · 双商家会话并发推进同一单

- AC：`PB-B01-AC5` · PB：`PB-B01` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.1` · 场景：`V06 / W08`
- 实现任务：B-001、B-011、B-013、B-023 · 测试任务：B-032、B-033、B-036
- 角色/会话：SELLER, SELLER / S-SELLER, S-SELLER
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-12` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

重复推进同一状态、重复发货或重复完成：拒绝，状态不变，不重复扣库存。并发以系统先成功变更状态者为准，后到的冲突操作被拒绝，不覆盖已成功操作，不生成重复订单。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B01-AC5-CON
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · PLACED 单；两个商家 JWT（或同商家双连接）

- 操作（已展开）：
**实现（勿留悬空 helper）**
```bash
python3 scripts/reset_namespace.py --case-id $CASE_ID
python3 scripts/run_helper.py place_order --product P-ON-10 --qty 1
# 等价 HTTP：
# 1) POST /api/auth/login {username:b030_buyer_a,password:B030-BuyerA-Pass9} → tokenA
# 2) POST /api/me/cart/items + Idempotency-Key 新 UUID  body={productId:$(P-ON-10.id)} → cartItemId
# 3) PATCH /api/me/cart/items/{cartItemId} {quantity:"1"} （若 qty≠1）
# 4) POST /api/me/checkout/confirmations {cartItemIds:[cartItemId]} → confirmationToken
# 5) POST /api/me/orders + Idempotency-Key  body={confirmationToken} → orderId/orderNo；message=下单成功
```
提取：`orderId`、`orderNo`、`tokenA`

#### 步骤 2 · BARRIER · 同时 CONFIRM

- 操作：`{"barrier": "SEQ-12", "mode": "simultaneous", "a": "POST /api/admin/orders/${orderId}/actions CONFIRM expectedStatus=PLACED", "b": "同"}`

#### 步骤 3 · ASSERT · 恰一成功一拒绝；最终 CONFIRMED；无重复订单

- 操作：`{"sql": ["SELECT status, COUNT(*) FROM shop_order WHERE id=${orderId};"]}`

### 期望（响应 / 页面 / DB）

- **response**：先成功者生效；后到冲突拒绝
- **db**：单行订单；库存只按建单时已扣一次
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

- `python3 scripts/reset_namespace.py --case-id PB-B01-AC5-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
