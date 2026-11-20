# PB-B03 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B03-AC1-POS · 订单快照与历史

- AC：`PB-B03-AC1` · PB：`PB-B03` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.3` · 场景：`V05、V08 / W06～W08、W10`
- 实现任务：B-001、B-004、B-010、B-011、B-015、B-016、B-022、B-023、B-024 · 测试任务：B-029、B-032、B-033、B-035、B-036
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

下单成功时固化快照，且之后不可改写：所选商品的名称、单价、数量，以及总金额、下单时间、唯一且不可变更的订单号。未选商品不进入快照。下单后商品下架、库存变化或重新发布，均不改写该订单快照。总金额 = Σ（单价 × 整数数量），单位为人民币元，保留两位小数；单价为两位小数，逐行相乘后求和，页面、订单明细与总额一致，不含运费及其他费用。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B03-AC1-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 下单

- 操作：`{"ref": "helper:place_order", "qty": "2"}`
- 提取：`{"orderId": "id", "unit": "items[0].unitPrice", "qty": "items[0].quantity"}`

#### 步骤 2 · SELLER · 改价改库存改名

- 操作：`{"ref": "helper:mutate_product"}`

#### 步骤 3 · CUSTOMER_A · GET 订单详情

- HTTP `GET` `/api/me/orders/${orderId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"snapshot_unchanged": true}`

#### 步骤 4 · CUSTOMER_A · 订单历史分页

- HTTP `GET` `/api/me/orders?page=1&size=10`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"http": 200}`

### 期望（响应 / 页面 / DB）

- **db**：order_item 快照不随商品变更；同 order+product 仅一行
- **page**：历史展示快照字段

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

- `python3 scripts/reset_namespace.py --case-id PB-B03-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B03-AC2-POS · 订单快照与历史

- AC：`PB-B03-AC2` · PB：`PB-B03` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.3` · 场景：`V05、V08 / W06～W08、W10`
- 实现任务：B-001、B-004、B-010、B-011、B-015、B-016、B-022、B-023、B-024 · 测试任务：B-029、B-032、B-033、B-035、B-036
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

原商品名称、价格、图文仍不可原地修改。不存在「原商品原地改价」场景，本轮不新开这些字段的编辑能力。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：「原商品原地改价」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B03-AC2-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 下单

- 操作：`{"ref": "helper:place_order", "qty": "2"}`
- 提取：`{"orderId": "id", "unit": "items[0].unitPrice", "qty": "items[0].quantity"}`

#### 步骤 2 · SELLER · 改价改库存改名

- 操作：`{"ref": "helper:mutate_product"}`

#### 步骤 3 · CUSTOMER_A · GET 订单详情

- HTTP `GET` `/api/me/orders/${orderId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"snapshot_unchanged": true}`

#### 步骤 4 · CUSTOMER_A · 订单历史分页

- HTTP `GET` `/api/me/orders?page=1&size=10`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"http": 200}`

### 期望（响应 / 页面 / DB）

- **db**：order_item 快照不随商品变更；同 order+product 仅一行
- **page**：历史展示快照字段

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

- `python3 scripts/reset_namespace.py --case-id PB-B03-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B03-AC3-POS · 订单快照与历史

- AC：`PB-B03-AC3` · PB：`PB-B03` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.3` · 场景：`V05、V08 / W06～W08、W10`
- 实现任务：B-001、B-004、B-010、B-011、B-015、B-016、B-022、B-023、B-024 · 测试任务：B-029、B-032、B-033、B-035、B-036
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

客户入口名为「订单历史」：仅展示当前登录客户本人的全部五态订单（含进行中与已取消），按时间倒序并支持分页；已取消订单须展示取消发起方（客户/商家）与取消时间，以及订单号、商品清单、总金额、下单时间、状态。商家入口名为「订单管理」：展示全站订单，按时间倒序并支持分页，商家可在此推进状态并按 `US-B06` / `PB-B06` 取消。「下单历史」这一名称废弃。状态筛选非必须（可选，不强制）。不另做独立的全站订单总览页。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：「下单历史」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B03-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 下单

- 操作：`{"ref": "helper:place_order", "qty": "2"}`
- 提取：`{"orderId": "id", "unit": "items[0].unitPrice", "qty": "items[0].quantity"}`

#### 步骤 2 · SELLER · 改价改库存改名

- 操作：`{"ref": "helper:mutate_product"}`

#### 步骤 3 · CUSTOMER_A · GET 订单详情

- HTTP `GET` `/api/me/orders/${orderId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"snapshot_unchanged": true}`

#### 步骤 4 · CUSTOMER_A · 订单历史分页

- HTTP `GET` `/api/me/orders?page=1&size=10`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"http": 200}`

### 期望（响应 / 页面 / DB）

- **db**：order_item 快照不随商品变更；同 order+product 仅一行
- **page**：历史展示快照字段

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

- `python3 scripts/reset_namespace.py --case-id PB-B03-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B03-AC4-POS · 订单快照与历史

- AC：`PB-B03-AC4` · PB：`PB-B03` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.3` · 场景：`V05、V08 / W06～W08、W10`
- 实现任务：B-001、B-004、B-010、B-011、B-015、B-016、B-022、B-023、B-024 · 测试任务：B-029、B-032、B-033、B-035、B-036
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

客户与商家查看、下单均须登录并由服务端校验。客户未登录提示「请先登录」，登录失效提示「请重新登录」；客户访问他人订单须拒绝。同一客户可同时存在多笔未完成订单（含同一商品），但每次必须独立通过下单校验。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请先登录」, 「请重新登录」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B03-AC4-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 下单

- 操作：`{"ref": "helper:place_order", "qty": "2"}`
- 提取：`{"orderId": "id", "unit": "items[0].unitPrice", "qty": "items[0].quantity"}`

#### 步骤 2 · SELLER · 改价改库存改名

- 操作：`{"ref": "helper:mutate_product"}`

#### 步骤 3 · CUSTOMER_A · GET 订单详情

- HTTP `GET` `/api/me/orders/${orderId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"snapshot_unchanged": true}`

#### 步骤 4 · CUSTOMER_A · 订单历史分页

- HTTP `GET` `/api/me/orders?page=1&size=10`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"http": 200}`

### 期望（响应 / 页面 / DB）

- **db**：order_item 快照不随商品变更；同 order+product 仅一行
- **page**：历史展示快照字段

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

- `python3 scripts/reset_namespace.py --case-id PB-B03-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B03-AC5-POS · 订单快照与历史

- AC：`PB-B03-AC5` · PB：`PB-B03` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.3` · 场景：`V05、V08 / W06～W08、W10`
- 实现任务：B-001、B-004、B-010、B-011、B-015、B-016、B-022、B-023、B-024 · 测试任务：B-029、B-032、B-033、B-035、B-036
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

旧的成功、失败记录保留为只读历史，不迁移到新订单。旧的排队中、交易中意向：关闭、不迁移、不视为「已取消」（它们不属于新订单体系，无「取消」概念）；原记录与快照不丢失。客户和商家可通过只读归档入口查看这些记录，但不可操作、不可进入新订单流转。关闭时原冻结商品解冻并恢复在售；库存不回补（旧意向从未按口径 A 扣过库存）。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「已取消」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B03-AC5-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 下单

- 操作：`{"ref": "helper:place_order", "qty": "2"}`
- 提取：`{"orderId": "id", "unit": "items[0].unitPrice", "qty": "items[0].quantity"}`

#### 步骤 2 · SELLER · 改价改库存改名

- 操作：`{"ref": "helper:mutate_product"}`

#### 步骤 3 · CUSTOMER_A · GET 订单详情

- HTTP `GET` `/api/me/orders/${orderId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"snapshot_unchanged": true}`

#### 步骤 4 · CUSTOMER_A · 订单历史分页

- HTTP `GET` `/api/me/orders?page=1&size=10`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"http": 200}`

### 期望（响应 / 页面 / DB）

- **db**：order_item 快照不随商品变更；同 order+product 仅一行
- **page**：历史展示快照字段

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

- `python3 scripts/reset_namespace.py --case-id PB-B03-AC5-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B03-AC5-POS · 旧意向只读归档

- AC：`PB-B03-AC5` · PB：`PB-B03` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.3` · 场景：`V05、V08 / W06～W08、W10`
- 实现任务：B-001、B-004、B-010、B-011、B-015、B-016、B-022、B-023、B-024 · 测试任务：B-029、B-032、B-033、B-035、B-036
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：LEGACY_INTENT

### 验收标准原文

旧的成功、失败记录保留为只读历史，不迁移到新订单。旧的排队中、交易中意向：关闭、不迁移、不视为「已取消」（它们不属于新订单体系，无「取消」概念）；原记录与快照不丢失。客户和商家可通过只读归档入口查看这些记录，但不可操作、不可进入新订单流转。关闭时原冻结商品解冻并恢复在售；库存不回补（旧意向从未按口径 A 扣过库存）。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「已取消」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B03-AC5-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · GET legacy

- HTTP `GET` `/api/me/legacy-intents?page=1&size=10`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"http": 200}`

#### 步骤 2 · SELLER · GET admin legacy

- HTTP `GET` `/api/admin/legacy-intents?page=1&size=10`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`
- 断言：`{"http": 200}`

#### 步骤 3 · ASSERT · 不可当新单推进；拍卖未改

- 操作：`{"note": "B035 回归单列"}`

### 期望（响应 / 页面 / DB）

- **db**：legacy_closed_at 非空；原 status 保留

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

- `python3 scripts/reset_namespace.py --case-id PB-B03-AC5-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
