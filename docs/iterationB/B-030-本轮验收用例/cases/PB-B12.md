# PB-B12 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B12-AC1-POS · 结算选择与确认

- AC：`PB-B12-AC1` · PB：`PB-B12` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.8` · 场景：`V04 / W03～W05`
- 实现任务：B-005、B-009、B-010、B-011、B-012、B-020、B-021 · 测试任务：B-032、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-OFF-M

### 验收标准原文

客户必须先加入购物车才能下单，商品详情页不提供直接下单。从购物车下单必须登录，并由服务端校验登录态与归属。未登录提示「请先登录」，登录失效提示「请重新登录」。提交他人购物车行，或勾选中混入他人的行：整次拒绝，提示「无权操作」，不部分处理。以上均不生成订单，库存与购物车保持不变。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请先登录」, 「请重新登录」, 「无权操作」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B12-AC1-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B12-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B12-AC2-POS · 结算选择与确认

- AC：`PB-B12-AC2` · PB：`PB-B12` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.8` · 场景：`V04 / W03～W05`
- 实现任务：B-005、B-009、B-010、B-011、B-012、B-020、B-021 · 测试任务：B-032、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-OFF-M

### 验收标准原文

一次提交所选商品生成一张订单，初始状态为「客户下单」，之后按 `US-B01` / `PB-B01` 整单依次流转；取消也按整单执行。支持多个不同商品，也支持同一商品数量大于 1；同一商品仍只对应一条订单明细。只选一行、或一行数量为 1，也可正常下单。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B12-AC2-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B12-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B12-AC3-POS · 结算选择与确认

- AC：`PB-B12-AC3` · PB：`PB-B12` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.8` · 场景：`V04 / W03～W05`
- 实现任务：B-005、B-009、B-010、B-011、B-012、B-020、B-021 · 测试任务：B-032、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-OFF-M

### 验收标准原文

默认勾选购物车中可下单的行；支持逐行勾选、取消勾选、全选与取消全选。已下架等失效行不可勾选，全选不包含失效行。仍在售但库存大于 0 且少于车中数量的行不标注失效，允许客户勾选，但不把默认全选擅自改成「全选全部在售行」——默认全选仍以「可下单」为准。未选行即使失效或库存不足，也不影响本次提交；校验只作用于所选行。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B12-AC3-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B12-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B12-AC3-NEG · 确认后下架再提交

- AC：`PB-B12-AC3` · PB：`PB-B12` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.8` · 场景：`V04 / W03～W05`
- 实现任务：B-005、B-009、B-010、B-011、B-012、B-020、B-021 · 测试任务：B-032、B-036、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

默认勾选购物车中可下单的行；支持逐行勾选、取消勾选、全选与取消全选。已下架等失效行不可勾选，全选不包含失效行。仍在售但库存大于 0 且少于车中数量的行不标注失效，允许客户勾选，但不把默认全选擅自改成「全选全部在售行」——默认全选仍以「可下单」为准。未选行即使失效或库存不足，也不影响本次提交；校验只作用于所选行。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B12-AC3-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 确认

- 操作：`{"ref": "helper:confirm"}`

#### 步骤 2 · SELLER · 下架

- HTTP `POST` `/api/admin/products/${P-ON-10.id}/offline`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`

#### 步骤 3 · CUSTOMER_A · 提交

- 操作：`{"ref": "helper:submit"}`
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

- `python3 scripts/reset_namespace.py --case-id PB-B12-AC3-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B12-AC4-POS · 结算选择与确认

- AC：`PB-B12-AC4` · PB：`PB-B12` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.8` · 场景：`V04 / W03～W05`
- 实现任务：B-005、B-009、B-010、B-011、B-012、B-020、B-021 · 测试任务：B-032、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-OFF-M

### 验收标准原文

必须提供下单确认步骤，展示所选清单、数量、单价、总金额。复核时点以最终提交成功时为准（不是打开购物车或确认页时）。确认后、提交前数据若变化，须按最新数据重新校验，不满足则拒绝并要求重新确认，不直接建单。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B12-AC4-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B12-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B12-AC5-POS · 结算选择与确认

- AC：`PB-B12-AC5` · PB：`PB-B12` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.8` · 场景：`V04 / W03～W05`
- 实现任务：B-005、B-009、B-010、B-011、B-012、B-020、B-021 · 测试任务：B-032、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-OFF-M

### 验收标准原文

提供清空购物车，须二次确认；勾选与清空均不创建订单、不影响库存。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B12-AC5-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B12-AC5-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B12-AC6-POS · 结算选择与确认

- AC：`PB-B12-AC6` · PB：`PB-B12` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.8` · 场景：`V04 / W03～W05`
- 实现任务：B-005、B-009、B-010、B-011、B-012、B-020、B-021 · 测试任务：B-032、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-OFF-M

### 验收标准原文

提交时再次校验所选行。任一所选行已下架、不存在或库存不足，则整单失败：不生成订单、不扣库存、不清购物车，也不静默跳过问题行。失败必须逐项指出具体商品和原因，不写笼统的「缺货」。仍在售但 0 < 当前可售库存 < 所选数量时，提示「商品「XX」库存不足：当前可售 N 件，您选购了 M 件，请减少数量或移除后重试。」（XX 为商品名，N 为当前可售库存，M 为所选数量。）所选行已下架时，提示「商品「XX」已下架，请从购物车移除后重试。」多件同时不满足时逐项列出。空购物车或未勾选任何行：拒绝，提示「请选择商品」，数据不变。本条不另设单笔订单的明细行数、总件数或金额上限。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「商品「XX」, 「请选择商品」
- **禁止作为状态/中间态/旧规则出现**：「缺货」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B12-AC6-POS
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
- **forbidden**：缺货

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

- `python3 scripts/reset_namespace.py --case-id PB-B12-AC6-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B12-AC6-NEG · 确认后下架再提交

- AC：`PB-B12-AC6` · PB：`PB-B12` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.8` · 场景：`V04 / W03～W05`
- 实现任务：B-005、B-009、B-010、B-011、B-012、B-020、B-021 · 测试任务：B-032、B-036、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

提交时再次校验所选行。任一所选行已下架、不存在或库存不足，则整单失败：不生成订单、不扣库存、不清购物车，也不静默跳过问题行。失败必须逐项指出具体商品和原因，不写笼统的「缺货」。仍在售但 0 < 当前可售库存 < 所选数量时，提示「商品「XX」库存不足：当前可售 N 件，您选购了 M 件，请减少数量或移除后重试。」（XX 为商品名，N 为当前可售库存，M 为所选数量。）所选行已下架时，提示「商品「XX」已下架，请从购物车移除后重试。」多件同时不满足时逐项列出。空购物车或未勾选任何行：拒绝，提示「请选择商品」，数据不变。本条不另设单笔订单的明细行数、总件数或金额上限。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「商品「XX」, 「请选择商品」
- **禁止作为状态/中间态/旧规则出现**：「缺货」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B12-AC6-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 确认

- 操作：`{"ref": "helper:confirm"}`

#### 步骤 2 · SELLER · 下架

- HTTP `POST` `/api/admin/products/${P-ON-10.id}/offline`
- Headers：`{"Authorization": "Bearer ${tokenS}"}`

#### 步骤 3 · CUSTOMER_A · 提交

- 操作：`{"ref": "helper:submit"}`
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

- `python3 scripts/reset_namespace.py --case-id PB-B12-AC6-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
