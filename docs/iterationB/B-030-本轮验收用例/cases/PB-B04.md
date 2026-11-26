# PB-B04 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B04-AC1-POS · 取消主路径

- AC：`PB-B04-AC1` · PB：`PB-B04` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-04` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

客户可以取消自己符合条件的订单，并非仅可查看。可取消的最后状态是「备货完成」，即在「客户下单」「商家确认」「备货完成」均可取消；一旦进入「开始发货」，立即不可取消。判定以系统成功变更状态为准，不是按钮点击时间。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「备货完成」, 「开始发货」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC1-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py order_in_status --status PREPARED --product P-ON-10 --qty 1
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC1-NEG · SHIPPED 客户不可取消

- AC：`PB-B04-AC1` · PB：`PB-B04` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

客户可以取消自己符合条件的订单，并非仅可查看。可取消的最后状态是「备货完成」，即在「客户下单」「商家确认」「备货完成」均可取消；一旦进入「开始发货」，立即不可取消。判定以系统成功变更状态为准，不是按钮点击时间。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「备货完成」, 「开始发货」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC1-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · SHIPPED 单

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py advance_to --order-id "$ORDER_ID" --status SHIPPED
# HTTP：按 PLACED→CONFIRMED→PREPARED→SHIPPED→COMPLETED 依次
# POST /api/admin/orders/{id}/actions {action, expectedStatus}
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC1-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC1-NEG · 完成后不可取消

- AC：`PB-B04-AC1` · PB：`PB-B04` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

客户可以取消自己符合条件的订单，并非仅可查看。可取消的最后状态是「备货完成」，即在「客户下单」「商家确认」「备货完成」均可取消；一旦进入「开始发货」，立即不可取消。判定以系统成功变更状态为准，不是按钮点击时间。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「备货完成」, 「开始发货」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC1-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · COMPLETED

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py advance_to --order-id "$ORDER_ID" --status COMPLETED
# HTTP：按 PLACED→CONFIRMED→PREPARED→SHIPPED→COMPLETED 依次
# POST /api/admin/orders/{id}/actions {action, expectedStatus}
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC1-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC2-POS · 取消主路径

- AC：`PB-B04-AC2` · PB：`PB-B04` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

客户只能取消本人订单。未登录提示「请先登录」，登录失效提示「请重新登录」；操作他人订单拒绝，提示「无权操作该订单」。订单不存在时拒绝，提示「订单不存在」。以上失败均不改变订单状态与库存。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请先登录」, 「请重新登录」, 「无权操作该订单」
- **禁止作为状态/中间态/旧规则出现**：「订单不存在」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC2-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py order_in_status --status PLACED --product P-ON-10 --qty 1
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC3-POS · 取消主路径

- AC：`PB-B04-AC3` · PB：`PB-B04` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

只能整单取消。试图部分取消：整单拒绝，提示「不支持部分取消」，状态与库存不变。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「不支持部分取消」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py order_in_status --status PLACED --product P-ON-10 --qty 1
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC3-NEG · 部分取消拒绝

- AC：`PB-B04-AC3` · PB：`PB-B04` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

只能整单取消。试图部分取消：整单拒绝，提示「不支持部分取消」，状态与库存不变。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「不支持部分取消」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC3-NEG
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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC3-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC4-POS · 取消主路径

- AC：`PB-B04-AC4` · PB：`PB-B04` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

取消成功后进入终态「已取消」，不可恢复、不设任何恢复通道，也不再重新排队。列表与详情展示订单号、商品清单、总金额、下单时间、状态为已取消，以及取消发起方（客户）与取消时间；已取消订单与五态订单出现在同一「订单历史」列表，按时间倒序。取消时间与发起方随订单保留、可追溯。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「已取消」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC4-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py order_in_status --status PLACED --product P-ON-10 --qty 1
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC5-POS · 取消主路径

- AC：`PB-B04-AC5` · PB：`PB-B04` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-04` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

对已是「已取消」的订单再次取消：拒绝，提示「订单已取消」，状态不变，库存不再次回补。客户在「开始发货」状态取消：拒绝，提示「订单已开始发货，不可取消」，状态与库存不变。客户在「交易完成」之后取消：拒绝，提示「订单已完成，不可取消」，状态与库存不变。不可取消状态不显示或禁用「取消订单」入口，而不是仅在点击后报错。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「订单已取消」, 「订单已开始发货，不可取消」, 「订单已完成，不可取消」
- **禁止作为状态/中间态/旧规则出现**：「开始发货」
- **UI 状态标签（非错误提示）**：「已取消」, 「交易完成」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC5-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py order_in_status --status PREPARED --product P-ON-10 --qty 1
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC5-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC5-NEG · SHIPPED 客户不可取消

- AC：`PB-B04-AC5` · PB：`PB-B04` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

对已是「已取消」的订单再次取消：拒绝，提示「订单已取消」，状态不变，库存不再次回补。客户在「开始发货」状态取消：拒绝，提示「订单已开始发货，不可取消」，状态与库存不变。客户在「交易完成」之后取消：拒绝，提示「订单已完成，不可取消」，状态与库存不变。不可取消状态不显示或禁用「取消订单」入口，而不是仅在点击后报错。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「订单已取消」, 「订单已开始发货，不可取消」, 「订单已完成，不可取消」
- **禁止作为状态/中间态/旧规则出现**：「开始发货」
- **UI 状态标签（非错误提示）**：「已取消」, 「交易完成」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC5-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · SHIPPED 单

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py advance_to --order-id "$ORDER_ID" --status SHIPPED
# HTTP：按 PLACED→CONFIRMED→PREPARED→SHIPPED→COMPLETED 依次
# POST /api/admin/orders/{id}/actions {action, expectedStatus}
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC5-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC5-NEG · 完成后不可取消

- AC：`PB-B04-AC5` · PB：`PB-B04` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

对已是「已取消」的订单再次取消：拒绝，提示「订单已取消」，状态不变，库存不再次回补。客户在「开始发货」状态取消：拒绝，提示「订单已开始发货，不可取消」，状态与库存不变。客户在「交易完成」之后取消：拒绝，提示「订单已完成，不可取消」，状态与库存不变。不可取消状态不显示或禁用「取消订单」入口，而不是仅在点击后报错。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「订单已取消」, 「订单已开始发货，不可取消」, 「订单已完成，不可取消」
- **禁止作为状态/中间态/旧规则出现**：「开始发货」
- **UI 状态标签（非错误提示）**：「已取消」, 「交易完成」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC5-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · COMPLETED

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py advance_to --order-id "$ORDER_ID" --status COMPLETED
# HTTP：按 PLACED→CONFIRMED→PREPARED→SHIPPED→COMPLETED 依次
# POST /api/admin/orders/{id}/actions {action, expectedStatus}
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC5-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC5-BND · 取消回补与自动恢复边界

- AC：`PB-B04-AC5` · PB：`PB-B04` · 类型：`BND` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-0, P-OFF-M

### 验收标准原文

对已是「已取消」的订单再次取消：拒绝，提示「订单已取消」，状态不变，库存不再次回补。客户在「开始发货」状态取消：拒绝，提示「订单已开始发货，不可取消」，状态与库存不变。客户在「交易完成」之后取消：拒绝，提示「订单已完成，不可取消」，状态与库存不变。不可取消状态不显示或禁用「取消订单」入口，而不是仅在点击后报错。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「订单已取消」, 「订单已开始发货，不可取消」, 「订单已完成，不可取消」
- **禁止作为状态/中间态/旧规则出现**：「开始发货」
- **UI 状态标签（非错误提示）**：「已取消」, 「交易完成」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC5-BND
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 造单使某商品扣至 0→AUTO_ZERO；另一单商品为 MANUAL 下架

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py cancel_restock_matrix
# 下 P-ON-1×1 使库存归零；保留 P-OFF-M 人工下架对照
```

#### 步骤 2 · CUSTOMER_A · 取消 AUTO_ZERO 来源单

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py cancel --order-id "$ORDER_ID" --status "$EXPECTED_STATUS"
# 商家取消加 --as-seller
# HTTP：POST /api/me/orders/{id}/cancel 或 /api/admin/orders/{id}/cancel
# body={expectedStatus, reason:"B030-test"}
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC5-BND`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC6-POS · 取消主路径

- AC：`PB-B04-AC6` · PB：`PB-B04` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

入口在客户「订单历史」列表和订单详情；仅可取消状态显示「取消订单」。须二次确认。取消原因选填，不填也允许。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC6-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py order_in_status --status PLACED --product P-ON-10 --qty 1
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC6-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC7-POS · 取消主路径

- AC：`PB-B04-AC7` · PB：`PB-B04` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

已关闭、不迁移的旧意向仍不可取消，也不进入新取消流程。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC7-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · 准备可取消状态订单并记录 stock_before 与 snapshot_qty

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py order_in_status --status PLACED --product P-ON-10 --qty 1
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC7-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B04-AC7-NEG · SHIPPED 客户不可取消

- AC：`PB-B04-AC7` · PB：`PB-B04` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.9` · 场景：`V05 / W06、W07`
- 实现任务：B-005、B-014、B-022 · 测试任务：B-033、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

已关闭、不迁移的旧意向仍不可取消，也不进入新取消流程。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B04-AC7-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · SETUP · SHIPPED 单

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py advance_to --order-id "$ORDER_ID" --status SHIPPED
# HTTP：按 PLACED→CONFIRMED→PREPARED→SHIPPED→COMPLETED 依次
# POST /api/admin/orders/{id}/actions {action, expectedStatus}
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B04-AC7-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
