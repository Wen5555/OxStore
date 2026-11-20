# PB-B06 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B06-AC1-POS · 取消主路径

- AC：`PB-B06-AC1` · PB：`PB-B06` · 类型：`POS` · 状态：**待执行**
- V3：`5.2.4` · 场景：`V06 / W08`
- 实现任务：B-005、B-014、B-023 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

商家取消适用于本系统全部五态新订单。系统为单卖家，没有「按所属客户越权拒绝」的限制：已登录后台且订单处于可取消状态即可。须登录卖家后台；未登录或登录失效时拒绝，提示「请先登录后台」，订单状态与库存均不变。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请先登录后台」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B06-AC1-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作：`{"ref": "helper:order_in_status", "status": "PLACED"}`

#### 步骤 2 · CUSTOMER_A · 取消

- HTTP `POST` `/api/me/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${token}"}`
- Body：`{"expectedStatus": "${status}", "reason": "B030-test"}`
- 断言：`{"data.status": "CANCELLED"}`

#### 步骤 3 · DB · 回补一次；cancelled_by 正确

- 操作：`{"sql": ["SELECT status, cancelled_by, cancelled_at FROM shop_order WHERE id=${orderId};", "SELECT stock FROM product WHERE id=${productId}; -- stock_before + snapshot_qty （人工改库存交叉时按 B-000 串行规则）"]}`

### 期望（响应 / 页面 / DB）

- **db**：回补至多一次；终态 CANCELLED

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

- `python3 scripts/reset_namespace.py --case-id PB-B06-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B06-AC2-POS · 取消主路径

- AC：`PB-B06-AC2` · PB：`PB-B06` · 类型：`POS` · 状态：**待执行**
- V3：`5.2.4` · 场景：`V06 / W08`
- 实现任务：B-005、B-014、B-023 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-04` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

商家在「客户下单」「商家确认」「备货完成」「开始发货」均可取消；一旦进入「交易完成」，立即不可取消。商家在「开始发货」之后仍可取消，与客户在「开始发货」之后不可取消是已裁定的不同边界，不视为冲突。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「备货完成」, 「开始发货」, 「交易完成」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B06-AC2-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作：`{"ref": "helper:order_in_status", "status": "PREPARED"}`

#### 步骤 2 · CUSTOMER_A · 取消

- HTTP `POST` `/api/me/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${token}"}`
- Body：`{"expectedStatus": "${status}", "reason": "B030-test"}`
- 断言：`{"data.status": "CANCELLED"}`

#### 步骤 3 · DB · 回补一次；cancelled_by 正确

- 操作：`{"sql": ["SELECT status, cancelled_by, cancelled_at FROM shop_order WHERE id=${orderId};", "SELECT stock FROM product WHERE id=${productId}; -- stock_before + snapshot_qty （人工改库存交叉时按 B-000 串行规则）"]}`

### 期望（响应 / 页面 / DB）

- **db**：回补至多一次；终态 CANCELLED

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

- `python3 scripts/reset_namespace.py --case-id PB-B06-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B06-AC2-NEG · SHIPPED 客户不可取消

- AC：`PB-B06-AC2` · PB：`PB-B06` · 类型：`NEG` · 状态：**待执行**
- V3：`5.2.4` · 场景：`V06 / W08`
- 实现任务：B-005、B-014、B-023 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

商家在「客户下单」「商家确认」「备货完成」「开始发货」均可取消；一旦进入「交易完成」，立即不可取消。商家在「开始发货」之后仍可取消，与客户在「开始发货」之后不可取消是已裁定的不同边界，不视为冲突。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「备货完成」, 「开始发货」, 「交易完成」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B06-AC2-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · SHIPPED 单

- 操作：`{"ref": "helper:advance_to", "status": "SHIPPED"}`

#### 步骤 2 · CUSTOMER_A · 取消

- HTTP `POST` `/api/me/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"expectedStatus": "SHIPPED"}`
- 断言：`{"message": "订单已开始发货，不可取消"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：订单已开始发货，不可取消

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

- `python3 scripts/reset_namespace.py --case-id PB-B06-AC2-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B06-AC2-NEG · 完成后不可取消

- AC：`PB-B06-AC2` · PB：`PB-B06` · 类型：`NEG` · 状态：**待执行**
- V3：`5.2.4` · 场景：`V06 / W08`
- 实现任务：B-005、B-014、B-023 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

商家在「客户下单」「商家确认」「备货完成」「开始发货」均可取消；一旦进入「交易完成」，立即不可取消。商家在「开始发货」之后仍可取消，与客户在「开始发货」之后不可取消是已裁定的不同边界，不视为冲突。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「备货完成」, 「开始发货」, 「交易完成」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B06-AC2-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · COMPLETED

- 操作：`{"ref": "helper:advance_to", "status": "COMPLETED"}`

#### 步骤 2 · CUSTOMER_A · 取消

- HTTP `POST` `/api/me/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"expectedStatus": "COMPLETED"}`
- 断言：`{"message": "订单已完成，不可取消"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：订单已完成，不可取消

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

- `python3 scripts/reset_namespace.py --case-id PB-B06-AC2-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B06-AC3-POS · 取消主路径

- AC：`PB-B06-AC3` · PB：`PB-B06` · 类型：`POS` · 状态：**待执行**
- V3：`5.2.4` · 场景：`V06 / W08`
- 实现任务：B-005、B-014、B-023 · 测试任务：B-033、B-036、B-037
- 角色/会话：SELLER, CUSTOMER_A, SELLER / S-SELLER, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

成功后进入终态「已取消」，记录取消发起方为商家以及取消时间。列表与详情的展示字段与 `US-B04` / `PB-B04` 相同，出现在商家「订单管理」中，按时间倒序。取消时间与发起方永久保留、可追溯。已取消不可恢复，无「重新排队」，也无「交易失败」状态。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「已取消」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B06-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作：`{"ref": "helper:order_in_status", "status": "PLACED"}`

#### 步骤 2 · SELLER · 取消

- HTTP `POST` `/api/admin/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${token}"}`
- Body：`{"expectedStatus": "${status}", "reason": "B030-test"}`
- 断言：`{"data.status": "CANCELLED"}`

#### 步骤 3 · DB · 回补一次；cancelled_by 正确

- 操作：`{"sql": ["SELECT status, cancelled_by, cancelled_at FROM shop_order WHERE id=${orderId};", "SELECT stock FROM product WHERE id=${productId}; -- stock_before + snapshot_qty （人工改库存交叉时按 B-000 串行规则）"]}`

### 期望（响应 / 页面 / DB）

- **db**：回补至多一次；终态 CANCELLED

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

- `python3 scripts/reset_namespace.py --case-id PB-B06-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B06-AC4-POS · 取消主路径

- AC：`PB-B06-AC4` · PB：`PB-B06` · 类型：`POS` · 状态：**待执行**
- V3：`5.2.4` · 场景：`V06 / W08`
- 实现任务：B-005、B-014、B-023 · 测试任务：B-033、B-036、B-037
- 角色/会话：SELLER, CUSTOMER_A, SELLER / S-SELLER, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

对已是「已取消」的订单再次取消：拒绝，提示「订单已取消」，库存不再次回补。对已是「交易完成」的订单取消：拒绝，提示「订单已完成，不可取消」，状态与库存不变。「交易完成」与「已取消」不显示取消入口，或将入口禁用。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「订单已取消」, 「订单已完成，不可取消」
- **禁止作为状态/中间态/旧规则出现**：「交易完成」
- **UI 状态标签（非错误提示）**：「已取消」, 「交易完成」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B06-AC4-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作：`{"ref": "helper:order_in_status", "status": "PLACED"}`

#### 步骤 2 · SELLER · 取消

- HTTP `POST` `/api/admin/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${token}"}`
- Body：`{"expectedStatus": "${status}", "reason": "B030-test"}`
- 断言：`{"data.status": "CANCELLED"}`

#### 步骤 3 · DB · 回补一次；cancelled_by 正确

- 操作：`{"sql": ["SELECT status, cancelled_by, cancelled_at FROM shop_order WHERE id=${orderId};", "SELECT stock FROM product WHERE id=${productId}; -- stock_before + snapshot_qty （人工改库存交叉时按 B-000 串行规则）"]}`

### 期望（响应 / 页面 / DB）

- **db**：回补至多一次；终态 CANCELLED

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

- `python3 scripts/reset_namespace.py --case-id PB-B06-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B06-AC4-NEG · SHIPPED 客户不可取消

- AC：`PB-B06-AC4` · PB：`PB-B06` · 类型：`NEG` · 状态：**待执行**
- V3：`5.2.4` · 场景：`V06 / W08`
- 实现任务：B-005、B-014、B-023 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

对已是「已取消」的订单再次取消：拒绝，提示「订单已取消」，库存不再次回补。对已是「交易完成」的订单取消：拒绝，提示「订单已完成，不可取消」，状态与库存不变。「交易完成」与「已取消」不显示取消入口，或将入口禁用。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「订单已取消」, 「订单已完成，不可取消」
- **禁止作为状态/中间态/旧规则出现**：「交易完成」
- **UI 状态标签（非错误提示）**：「已取消」, 「交易完成」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B06-AC4-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · SHIPPED 单

- 操作：`{"ref": "helper:advance_to", "status": "SHIPPED"}`

#### 步骤 2 · CUSTOMER_A · 取消

- HTTP `POST` `/api/me/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"expectedStatus": "SHIPPED"}`
- 断言：`{"message": "订单已开始发货，不可取消"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：订单已开始发货，不可取消

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

- `python3 scripts/reset_namespace.py --case-id PB-B06-AC4-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B06-AC4-NEG · 完成后不可取消

- AC：`PB-B06-AC4` · PB：`PB-B06` · 类型：`NEG` · 状态：**待执行**
- V3：`5.2.4` · 场景：`V06 / W08`
- 实现任务：B-005、B-014、B-023 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

对已是「已取消」的订单再次取消：拒绝，提示「订单已取消」，库存不再次回补。对已是「交易完成」的订单取消：拒绝，提示「订单已完成，不可取消」，状态与库存不变。「交易完成」与「已取消」不显示取消入口，或将入口禁用。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「订单已取消」, 「订单已完成，不可取消」
- **禁止作为状态/中间态/旧规则出现**：「交易完成」
- **UI 状态标签（非错误提示）**：「已取消」, 「交易完成」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B06-AC4-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · COMPLETED

- 操作：`{"ref": "helper:advance_to", "status": "COMPLETED"}`

#### 步骤 2 · CUSTOMER_A · 取消

- HTTP `POST` `/api/me/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"expectedStatus": "COMPLETED"}`
- 断言：`{"message": "订单已完成，不可取消"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：订单已完成，不可取消

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

- `python3 scripts/reset_namespace.py --case-id PB-B06-AC4-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B06-AC4-BND · 取消回补与自动恢复边界

- AC：`PB-B06-AC4` · PB：`PB-B06` · 类型：`BND` · 状态：**待执行**
- V3：`5.2.4` · 场景：`V06 / W08`
- 实现任务：B-005、B-014、B-023 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-0, P-OFF-M

### 验收标准原文

对已是「已取消」的订单再次取消：拒绝，提示「订单已取消」，库存不再次回补。对已是「交易完成」的订单取消：拒绝，提示「订单已完成，不可取消」，状态与库存不变。「交易完成」与「已取消」不显示取消入口，或将入口禁用。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「订单已取消」, 「订单已完成，不可取消」
- **禁止作为状态/中间态/旧规则出现**：「交易完成」
- **UI 状态标签（非错误提示）**：「已取消」, 「交易完成」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B06-AC4-BND
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 造单使某商品扣至 0→AUTO_ZERO；另一单商品为 MANUAL 下架

- 操作：`{"ref": "helper:cancel_restock_matrix"}`

#### 步骤 2 · CUSTOMER_A · 取消 AUTO_ZERO 来源单

- 操作：`{"ref": "helper:cancel"}`

#### 步骤 3 · DB · 回补后 stock>0 且自动恢复在售；MANUAL 下架不因回补自动上架

- 操作：`{"sql": ["SELECT stock,status,offline_reason FROM product WHERE name='B030-零库存自动下架';", "SELECT stock,status,offline_reason FROM product WHERE name='B030-人工下架-库存5';"]}`

### 期望（响应 / 页面 / DB）

- **db**：AUTO_ZERO 可恢复；MANUAL 不自动恢复

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

- `python3 scripts/reset_namespace.py --case-id PB-B06-AC4-BND`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B06-AC5-POS · 取消主路径

- AC：`PB-B06-AC5` · PB：`PB-B06` · 类型：`POS` · 状态：**待执行**
- V3：`5.2.4` · 场景：`V06 / W08`
- 实现任务：B-005、B-014、B-023 · 测试任务：B-033、B-036、B-037
- 角色/会话：SELLER, CUSTOMER_A, SELLER / S-SELLER, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

入口在商家「订单管理」列表和订单详情；仅对可取消状态显示入口。须二次确认。取消原因选填，不填也允许。只能整单取消，不支持部分取消；试图部分取消时整单拒绝，状态与库存不变。旧的「按顾客购买历史」页仍只读，不可在该页取消。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B06-AC5-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作：`{"ref": "helper:order_in_status", "status": "PLACED"}`

#### 步骤 2 · SELLER · 取消

- HTTP `POST` `/api/admin/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${token}"}`
- Body：`{"expectedStatus": "${status}", "reason": "B030-test"}`
- 断言：`{"data.status": "CANCELLED"}`

#### 步骤 3 · DB · 回补一次；cancelled_by 正确

- 操作：`{"sql": ["SELECT status, cancelled_by, cancelled_at FROM shop_order WHERE id=${orderId};", "SELECT stock FROM product WHERE id=${productId}; -- stock_before + snapshot_qty （人工改库存交叉时按 B-000 串行规则）"]}`

### 期望（响应 / 页面 / DB）

- **db**：回补至多一次；终态 CANCELLED

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

- `python3 scripts/reset_namespace.py --case-id PB-B06-AC5-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B06-AC5-NEG · 部分取消拒绝

- AC：`PB-B06-AC5` · PB：`PB-B06` · 类型：`NEG` · 状态：**待执行**
- V3：`5.2.4` · 场景：`V06 / W08`
- 实现任务：B-005、B-014、B-023 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

入口在商家「订单管理」列表和订单详情；仅对可取消状态显示入口。须二次确认。取消原因选填，不填也允许。只能整单取消，不支持部分取消；试图部分取消时整单拒绝，状态与库存不变。旧的「按顾客购买历史」页仍只读，不可在该页取消。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B06-AC5-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · body 含 items

- HTTP `POST` `/api/me/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"expectedStatus": "PLACED", "items": ["1"]}`
- 断言：`{"message": "不支持部分取消"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：不支持部分取消

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

- `python3 scripts/reset_namespace.py --case-id PB-B06-AC5-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B06-AC6-POS · 取消主路径

- AC：`PB-B06-AC6` · PB：`PB-B06` · 类型：`POS` · 状态：**待执行**
- V3：`5.2.4` · 场景：`V06 / W08`
- 实现任务：B-005、B-014、B-023 · 测试任务：B-033、B-036、B-037
- 角色/会话：SELLER, CUSTOMER_A, SELLER / S-SELLER, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

已关闭、不迁移的旧意向不进入新的取消流程。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B06-AC6-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作：`{"ref": "helper:order_in_status", "status": "PLACED"}`

#### 步骤 2 · SELLER · 取消

- HTTP `POST` `/api/admin/orders/${orderId}/cancel`
- Headers：`{"Authorization": "Bearer ${token}"}`
- Body：`{"expectedStatus": "${status}", "reason": "B030-test"}`
- 断言：`{"data.status": "CANCELLED"}`

#### 步骤 3 · DB · 回补一次；cancelled_by 正确

- 操作：`{"sql": ["SELECT status, cancelled_by, cancelled_at FROM shop_order WHERE id=${orderId};", "SELECT stock FROM product WHERE id=${productId}; -- stock_before + snapshot_qty （人工改库存交叉时按 B-000 串行规则）"]}`

### 期望（响应 / 页面 / DB）

- **db**：回补至多一次；终态 CANCELLED

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

- `python3 scripts/reset_namespace.py --case-id PB-B06-AC6-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
