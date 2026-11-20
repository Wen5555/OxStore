# PB-B05 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B05-AC1-POS · 取消主路径

- AC：`PB-B05-AC1` · PB：`PB-B05` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.4` · 场景：`V05 / W07、W09`
- 实现任务：B-003、B-006、B-014、B-022 · 测试任务：B-028、B-033
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

库存回补按 `US-B02` / `PB-B02` 已选定的口径 A 执行：取消成功时按订单快照数量加回各商品库存。回补等于撤销下单时的那次扣减，数量精确等于快照，不会把库存补高；商家在下单后对库存的其他调整是独立操作，与回补叠加。重复取消不再次改变库存，只回补一次。取消后已下单商品不自动回到购物车；客户再次购买须重新加购，并以当时实时库存重新校验，不沿用已取消订单的快照库存关系。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B05-AC1-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B05-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B05-AC1-BND · 取消回补与自动恢复边界

- AC：`PB-B05-AC1` · PB：`PB-B05` · 类型：`BND` · 状态：**待执行**
- V3：`5.3.4` · 场景：`V05 / W07、W09`
- 实现任务：B-003、B-006、B-014、B-022 · 测试任务：B-028、B-033
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-0, P-OFF-M

### 验收标准原文

库存回补按 `US-B02` / `PB-B02` 已选定的口径 A 执行：取消成功时按订单快照数量加回各商品库存。回补等于撤销下单时的那次扣减，数量精确等于快照，不会把库存补高；商家在下单后对库存的其他调整是独立操作，与回补叠加。重复取消不再次改变库存，只回补一次。取消后已下单商品不自动回到购物车；客户再次购买须重新加购，并以当时实时库存重新校验，不沿用已取消订单的快照库存关系。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B05-AC1-BND
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

- `python3 scripts/reset_namespace.py --case-id PB-B05-AC1-BND`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B05-AC2-POS · 取消主路径

- AC：`PB-B05-AC2` · PB：`PB-B05` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.4` · 场景：`V05 / W07、W09`
- 实现任务：B-003、B-006、B-014、B-022 · 测试任务：B-028、B-033
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

自动恢复在售的唯一条件：该商品此前因库存为 0 被自动下架，且本次取消确实把库存补回大于 0。客户取消与商家取消的触发条件相同。若商品此前是商家手动下架（库存仍大于 0），取消回补后保持「已下架」，须商家手动上架；回补只撤销扣减，不改变商家主动下架的状态。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已下架」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B05-AC2-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B05-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B05-AC2-BND · 取消回补与自动恢复边界

- AC：`PB-B05-AC2` · PB：`PB-B05` · 类型：`BND` · 状态：**待执行**
- V3：`5.3.4` · 场景：`V05 / W07、W09`
- 实现任务：B-003、B-006、B-014、B-022 · 测试任务：B-028、B-033
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-0, P-OFF-M

### 验收标准原文

自动恢复在售的唯一条件：该商品此前因库存为 0 被自动下架，且本次取消确实把库存补回大于 0。客户取消与商家取消的触发条件相同。若商品此前是商家手动下架（库存仍大于 0），取消回补后保持「已下架」，须商家手动上架；回补只撤销扣减，不改变商家主动下架的状态。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已下架」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B05-AC2-BND
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

- `python3 scripts/reset_namespace.py --case-id PB-B05-AC2-BND`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B05-AC3-POS · 取消主路径

- AC：`PB-B05-AC3` · PB：`PB-B05` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.4` · 场景：`V05 / W07、W09`
- 实现任务：B-003、B-006、B-014、B-022 · 测试任务：B-028、B-033
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-04` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

与商家「开始发货」并发：以系统成功变更状态为准，最终只有一个结果。发货先成功，则订单进入「开始发货」，客户取消失败，提示「订单已开始发货，不可取消」；取消先成功，则进入「已取消」，商家发货失败，提示「订单已取消，不可发货」。库存只按最终结果变化一次。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「订单已开始发货，不可取消」, 「订单已取消，不可发货」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「开始发货」, 「已取消」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B05-AC3-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B05-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B05-AC3-NEG · SHIPPED 客户不可取消

- AC：`PB-B05-AC3` · PB：`PB-B05` · 类型：`NEG` · 状态：**待执行**
- V3：`5.3.4` · 场景：`V05 / W07、W09`
- 实现任务：B-003、B-006、B-014、B-022 · 测试任务：B-028、B-033
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

与商家「开始发货」并发：以系统成功变更状态为准，最终只有一个结果。发货先成功，则订单进入「开始发货」，客户取消失败，提示「订单已开始发货，不可取消」；取消先成功，则进入「已取消」，商家发货失败，提示「订单已取消，不可发货」。库存只按最终结果变化一次。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「订单已开始发货，不可取消」, 「订单已取消，不可发货」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「开始发货」, 「已取消」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B05-AC3-NEG
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

- `python3 scripts/reset_namespace.py --case-id PB-B05-AC3-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B05-AC3-CON · 取消竞争

- AC：`PB-B05-AC3` · PB：`PB-B05` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.4` · 场景：`V05 / W07、W09`
- 实现任务：B-003、B-006、B-014、B-022 · 测试任务：B-028、B-033
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-04` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

与商家「开始发货」并发：以系统成功变更状态为准，最终只有一个结果。发货先成功，则订单进入「开始发货」，客户取消失败，提示「订单已开始发货，不可取消」；取消先成功，则进入「已取消」，商家发货失败，提示「订单已取消，不可发货」。库存只按最终结果变化一次。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「订单已开始发货，不可取消」, 「订单已取消，不可发货」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「开始发货」, 「已取消」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B05-AC3-CON
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · BARRIER · 按 SEQ

- 操作：`{"barrier": "SEQ-04", "mode": "simultaneous"}`

### 期望（响应 / 页面 / DB）

- **db**：先成功；回补一次

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

- `python3 scripts/reset_namespace.py --case-id PB-B05-AC3-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B05-AC4-POS · 取消主路径

- AC：`PB-B05-AC4` · PB：`PB-B05` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.4` · 场景：`V05 / W07、W09`
- 实现任务：B-003、B-006、B-014、B-022 · 测试任务：B-028、B-033
- 角色/会话：CUSTOMER_A, CUSTOMER_A, SELLER / S-CUSTOMER_A, S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-04` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

与商家确认或备货完成并发：同样以先成功者为准。确认或备货先成功，订单进入对应状态后，客户仍可再取消（因此时尚未进入「开始发货」）；取消先成功，则商家确认或备货被拒绝。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「开始发货」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B05-AC4-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B05-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B05-AC4-NEG · SHIPPED 客户不可取消

- AC：`PB-B05-AC4` · PB：`PB-B05` · 类型：`NEG` · 状态：**待执行**
- V3：`5.3.4` · 场景：`V05 / W07、W09`
- 实现任务：B-003、B-006、B-014、B-022 · 测试任务：B-028、B-033
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

与商家确认或备货完成并发：同样以先成功者为准。确认或备货先成功，订单进入对应状态后，客户仍可再取消（因此时尚未进入「开始发货」）；取消先成功，则商家确认或备货被拒绝。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「开始发货」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B05-AC4-NEG
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

- `python3 scripts/reset_namespace.py --case-id PB-B05-AC4-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B05-AC4-NEG · 完成后不可取消

- AC：`PB-B05-AC4` · PB：`PB-B05` · 类型：`NEG` · 状态：**待执行**
- V3：`5.3.4` · 场景：`V05 / W07、W09`
- 实现任务：B-003、B-006、B-014、B-022 · 测试任务：B-028、B-033
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

与商家确认或备货完成并发：同样以先成功者为准。确认或备货先成功，订单进入对应状态后，客户仍可再取消（因此时尚未进入「开始发货」）；取消先成功，则商家确认或备货被拒绝。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「开始发货」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B05-AC4-NEG
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

- `python3 scripts/reset_namespace.py --case-id PB-B05-AC4-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B05-AC4-CON · 取消竞争

- AC：`PB-B05-AC4` · PB：`PB-B05` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.4` · 场景：`V05 / W07、W09`
- 实现任务：B-003、B-006、B-014、B-022 · 测试任务：B-028、B-033
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-04` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

与商家确认或备货完成并发：同样以先成功者为准。确认或备货先成功，订单进入对应状态后，客户仍可再取消（因此时尚未进入「开始发货」）；取消先成功，则商家确认或备货被拒绝。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：「开始发货」

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B05-AC4-CON
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · BARRIER · 按 SEQ

- 操作：`{"barrier": "SEQ-04", "mode": "simultaneous"}`

### 期望（响应 / 页面 / DB）

- **db**：先成功；回补一次

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

- `python3 scripts/reset_namespace.py --case-id PB-B05-AC4-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
