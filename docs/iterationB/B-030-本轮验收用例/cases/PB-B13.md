# PB-B13 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B13-AC1-POS · 建单扣库清车同事务成功

- AC：`PB-B13-AC1` · PB：`PB-B13` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.5` · 场景：`V04 / W04、W05`
- 实现任务：B-001、B-003、B-010、B-011、B-012、B-021 · 测试任务：B-028、B-032、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-02` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

下单成功时：建单、按快照数量直接扣减库存、清理购物车所选行，必须在同一事务内完成，要么全部成功，要么全部回滚。客户成功时只看到「下单成功」（并展示订单号、可进入订单详情）；不存在「订单已生成但购物车未清理」或「库存已扣但清车未完成」的可见中间态，也不存在「订单成功、清车未完成、客户重试时只清车」的路径。失败则无订单、库存未扣、购物车不变，客户看到失败原因。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「下单成功」
- **禁止作为状态/中间态/旧规则出现**：「订单已生成但购物车未清理」, 「库存已扣但清车未完成」, 「订单成功、清车未完成、客户重试时只清车」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B13-AC1-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车行 qty=2；记录 stock/cart

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py cart_qty --product P-ON-10 --qty 2
# HTTP：login → POST /api/me/cart/items {productId} → PATCH quantity="2" → cartItemId
```

#### 步骤 2 · CUSTOMER_A · 确认+下单

- 操作（已展开）：
**实现**
```bash
# 需已有 cartItemId；或先 cart_qty
python3 scripts/run_helper.py checkout_submit --cart-item-id "$CART_ITEM_ID"
# HTTP：POST /api/me/checkout/confirmations → POST /api/me/orders + Idempotency-Key
```
- 提取：`{"orderId": "data.id"}`
- 断言：`{"message": "下单成功"}`

#### 步骤 3 · ASSERT · 同时可见：有订单、库存-2、所选行按余数清理；无中间态文案

- 操作：`{"checks": ["response.message == 下单成功 且含 orderNo", "DB shop_order 存在", "product.stock 已减", "cart 所选行已按余数处理", "禁止出现「订单已生成但购物车未清理」「库存已扣但清车未完成」类可见态"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：下单成功
- **forbidden**：订单已生成但购物车未清理、库存已扣但清车未完成、订单成功、清车未完成、客户重试时只清车
- **db**：同事务全有或全无

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

- `python3 scripts/reset_namespace.py --case-id PB-B13-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B13-AC1-NEG · 失败全回滚

- AC：`PB-B13-AC1` · PB：`PB-B13` · 类型：`NEG` · 状态：**待执行**
- V3：`5.3.5` · 场景：`V04 / W04、W05`
- 实现任务：B-001、B-003、B-010、B-011、B-012、B-021 · 测试任务：B-028、B-032、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-1

### 验收标准原文

下单成功时：建单、按快照数量直接扣减库存、清理购物车所选行，必须在同一事务内完成，要么全部成功，要么全部回滚。客户成功时只看到「下单成功」（并展示订单号、可进入订单详情）；不存在「订单已生成但购物车未清理」或「库存已扣但清车未完成」的可见中间态，也不存在「订单成功、清车未完成、客户重试时只清车」的路径。失败则无订单、库存未扣、购物车不变，客户看到失败原因。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「下单成功」
- **禁止作为状态/中间态/旧规则出现**：「订单已生成但购物车未清理」, 「库存已扣但清车未完成」, 「订单成功、清车未完成、客户重试时只清车」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B13-AC1-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车行 qty=5 > stock 1

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py cart_qty --product P-ON-1 --qty 5
# HTTP：login → POST /api/me/cart/items {productId} → PATCH quantity="5" → cartItemId
```

#### 步骤 2 · CUSTOMER_A · 下单应失败

- 操作（已展开）：
**实现**
```bash
# 需已有 cartItemId；或先 cart_qty
python3 scripts/run_helper.py checkout_submit --cart-item-id "$CART_ITEM_ID"
# HTTP：POST /api/me/checkout/confirmations → POST /api/me/orders + Idempotency-Key
```
- 断言：`{"message_contains": "库存不足", "no_order": true}`

#### 步骤 3 · DB · 无订单；库存仍 1；车行仍 5

- 操作：`{"sql": ["-- snapshot fail", "SELECT id, stock, status, offline_reason FROM product WHERE name LIKE 'B030-%' ORDER BY name;", "SELECT id, username FROM customer WHERE username LIKE 'b030_%';", "SELECT so.id, so.order_no, so.status, so.total_amount, so.cancelled_by, c.username FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%' ORDER BY so.id;", "SELECT oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.line_amount FROM order_item oi JOIN shop_order so ON so.id=oi.order_id JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%';", "SELECT ci.id, c.username, ci.product_id, ci.quantity FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username LIKE 'b030_%';", "SELECT f.id, c.username, f.product_id, f.created_at FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username LIKE 'b030_%';", "SELECT COUNT(*) AS intent_cnt FROM purchase_intent pi JOIN customer c ON c.id=pi.customer_id WHERE c.username LIKE 'b030_%' AND pi.legacy_closed_at IS NULL;"]}`

### 期望（响应 / 页面 / DB）

- **db**：失败无订单无扣库车不变
- **forbidden**：订单已生成但购物车未清理、库存已扣但清车未完成、订单成功、清车未完成、客户重试时只清车

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

- `python3 scripts/reset_namespace.py --case-id PB-B13-AC1-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B13-AC2-POS · 结算选择与确认

- AC：`PB-B13-AC2` · PB：`PB-B13` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.5` · 场景：`V04 / W04、W05`
- 实现任务：B-001、B-003、B-010、B-011、B-012、B-021 · 测试任务：B-028、B-032、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-OFF-M

### 验收标准原文

成功清车按余数处理：该行扣除已下单数量，余数大于 0 则保留余数，等于 0 则移除该行；提交后、锁定前另端新增的数量按提交成功时锁定的数量计算，锁定后新增的数量不会被误删，保留为余数。未选行始终保留。建单失败时，所选行、数量与勾选状态全部不变。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B13-AC2-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 确认所选在售行

- HTTP `POST` `/api/me/checkout/confirmations`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"cartItemIds": ["${cartOn}"]}`
- 提取：`{"confirmationToken": "data.confirmationToken"}`
- 断言：`{"http": 200}`

#### 步骤 2 · CUSTOMER_A · 空选确认

- HTTP `POST` `/api/me/checkout/confirmations`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"cartItemIds": []}`
- 断言：`{"message": "请选择商品"}`

#### 步骤 3 · CUSTOMER_A · 提交下单

- HTTP `POST` `/api/me/orders`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}`
- Body：`{"confirmationToken": "${confirmationToken}"}`
- 断言：`{"message": "下单成功"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：请选择商品、下单成功
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

- `python3 scripts/reset_namespace.py --case-id PB-B13-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B13-AC3-POS · 结算选择与确认

- AC：`PB-B13-AC3` · PB：`PB-B13` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.5` · 场景：`V04 / W04、W05`
- 实现任务：B-001、B-003、B-010、B-011、B-012、B-021 · 测试任务：B-028、B-032、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-OFF-M

### 验收标准原文

下单成功时固化的快照、金额计算与精度以 `US-B03` / `PB-B03` 为准，库存扣减时点以 `US-B02` / `PB-B02` 为准。下单后商品下架或库存变为 0，只影响其他新订单，不使本单失效；商家仍照常确认、备货、发货、完成。客户取消或商家取消后，已下单商品不自动回到购物车。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B13-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 确认所选在售行

- HTTP `POST` `/api/me/checkout/confirmations`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"cartItemIds": ["${cartOn}"]}`
- 提取：`{"confirmationToken": "data.confirmationToken"}`
- 断言：`{"http": 200}`

#### 步骤 2 · CUSTOMER_A · 空选确认

- HTTP `POST` `/api/me/checkout/confirmations`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"cartItemIds": []}`
- 断言：`{"message": "请选择商品"}`

#### 步骤 3 · CUSTOMER_A · 提交下单

- HTTP `POST` `/api/me/orders`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}`
- Body：`{"confirmationToken": "${confirmationToken}"}`
- 断言：`{"message": "下单成功"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：请选择商品、下单成功
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

- `python3 scripts/reset_namespace.py --case-id PB-B13-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B13-AC3-NEG · 确认后下架再提交

- AC：`PB-B13-AC3` · PB：`PB-B13` · 类型：`NEG` · 状态：**待执行**
- V3：`5.3.5` · 场景：`V04 / W04、W05`
- 实现任务：B-001、B-003、B-010、B-011、B-012、B-021 · 测试任务：B-028、B-032、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

下单成功时固化的快照、金额计算与精度以 `US-B03` / `PB-B03` 为准，库存扣减时点以 `US-B02` / `PB-B02` 为准。下单后商品下架或库存变为 0，只影响其他新订单，不使本单失效；商家仍照常确认、备货、发货、完成。客户取消或商家取消后，已下单商品不自动回到购物车。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B13-AC3-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 确认

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py confirm --cart-item-id "$CART_ITEM_ID"
# HTTP：POST /api/me/checkout/confirmations {cartItemIds:[$CART_ITEM_ID]}
```

#### 步骤 2 · SELLER · 下架

- HTTP `POST` `/api/admin/products/${P-ON-10.id}/offline`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`

#### 步骤 3 · CUSTOMER_A · 提交

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py submit --confirmation-token "$CONFIRMATION_TOKEN"
# HTTP：POST /api/me/orders + Idempotency-Key {confirmationToken}
```
- 断言：`{"message_contains": "已下架"}`

### 期望（响应 / 页面 / DB）

- **db**：无订单

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

- `python3 scripts/reset_namespace.py --case-id PB-B13-AC3-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B13-AC4-BND · 同结算同键不重复建单

- AC：`PB-B13-AC4` · PB：`PB-B13` · 类型：`BND` · 状态：**待执行**
- V3：`5.3.5` · 场景：`V04 / W04、W05`
- 实现任务：B-001、B-003、B-010、B-011、B-012、B-021 · 测试任务：B-028、B-032、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-02` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

同一次结算被双击、网络重试或重复确认：最多生成一张订单，库存与购物车最多处理一次；再次提交提示「订单已提交，请勿重复下单」。幂等键只用于拦截同一结算请求的重复提交，不用于补清车。服务端已建单但响应丢失时，客户通过「订单历史」查到原订单；再试时靠同一结算请求的幂等键拦截，不重复建单。客户有意再次购买同一商品，属于新的结算请求，允许生成新订单。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「订单已提交，请勿重复下单」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B13-AC4-BND
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 确认并提交成功

- 操作（已展开）：
**实现**
```bash
# 需已有 cartItemId；或先 cart_qty
python3 scripts/run_helper.py checkout_submit --cart-item-id "$CART_ITEM_ID"
# HTTP：POST /api/me/checkout/confirmations → POST /api/me/orders + Idempotency-Key
```
- 提取：`{"orderId": "data.id", "key": "idemKey", "token": "confirmationToken"}`

#### 步骤 2 · CUSTOMER_A · 同 confirmationToken + 同 Idempotency-Key 重放

- HTTP `POST` `/api/me/orders`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${key}"}`
- Body：`{"confirmationToken": "${token}"}`
- 断言：`{"message": "订单已提交，请勿重复下单"}`

#### 步骤 3 · DB · 仍仅一单；库存/车不二次处理

- 操作：`{"sql": ["SELECT COUNT(*) FROM shop_order WHERE id=${orderId}; -- 1"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：订单已提交，请勿重复下单

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

- `python3 scripts/reset_namespace.py --case-id PB-B13-AC4-BND`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B13-AC5-CON · 库存1双客户抢购

- AC：`PB-B13-AC5` · PB：`PB-B13` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.5` · 场景：`V04 / W04、W05`
- 实现任务：B-001、B-003、B-010、B-011、B-012、B-021 · 测试任务：B-028、B-032、B-037
- 角色/会话：CUSTOMER_A, CUSTOMER_B / S-CUSTOMER_A, S-CUSTOMER_B
- Fixtures：P-ON-1
- 并发 SEQ：`SEQ-01` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间另一端改数量、删行或加购：发生在锁定前，则反映到本次最新校验；发生在锁定后，则不影响本单。最终订单数量以提交成功时锁定的快照为准。其他客户抢先下单导致库存不足时，后到请求整单拒绝，不留下扣减，不产生半张订单，不超卖。商家下架后的新提交按已下架规则拒绝。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B13-AC5-CON
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · P-ON-1 stock=1；A/B 各确认 qty=1

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py dual_confirm --product P-ON-1 --qty 1
# 产出 JSON：A/B 的 token、confirmationToken、idem — 供 barrier_runner / SEQ-01 使用
```

#### 步骤 2 · BARRIER · 同时提交

- 操作：`{"barrier": "SEQ-01", "mode": "simultaneous", "a": "POST /api/me/orders A", "b": "POST /api/me/orders B"}`

#### 步骤 3 · ASSERT · 恰一成功；库存0；失败者整单拒绝无半单

- 操作：`{"sql": ["SELECT stock FROM product WHERE name='B030-低库存-1'; -- 0", "SELECT COUNT(*) FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username LIKE 'b030_%' AND so.status='PLACED'; -- 1"]}`

### 期望（响应 / 页面 / DB）

- **db**：防超卖；无半张订单

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

- `python3 scripts/reset_namespace.py --case-id PB-B13-AC5-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
