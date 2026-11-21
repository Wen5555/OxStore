# PB-B11 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B11-AC1-POS · 加购与改数量

- AC：`PB-B11-AC1` · PB：`PB-B11` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.7` · 场景：`V03 / W03`
- 实现任务：B-002、B-008、B-009、B-020、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-09` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

已在购物车中的商品随后下架或售罄：该行保留并标注「已下架」，由客户手动删除，不自动删除、不自动调减数量。商品仍在售但库存大于 0 且少于车中数量：该行不标注失效、保持原数量，下单时再因库存不足被拒绝。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已下架」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B11-AC1-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 加购

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k1}"}`
- Body：`{"productId": "${P-ON-10.id}"}`
- 提取：`{"cartId": "data.cartItemId"}`
- 断言：`{"message": "已加入购物车", "data.quantity": "1"}`

#### 步骤 2 · CUSTOMER_A · 同键重放

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k1}"}`
- Body：`{"productId": "${P-ON-10.id}"}`
- 断言：`{"message": "已加入购物车", "data.cartItemId": "${cartId}", "data.quantity": "1"}`

#### 步骤 3 · CUSTOMER_A · 改量 5

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "5"}`
- 断言：`{"message": "已更新", "data.quantity": "5"}`

#### 步骤 4 · CUSTOMER_A · 改量 0 删行

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "0"}`
- 断言：`{"message": "已移除"}`

#### 步骤 5 · CUSTOMER_A · 旧 id 再改量

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "2"}`
- 断言：`{"message": "该商品已不在购物车，请刷新页面后查看。"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已加入购物车、已更新、已移除、该商品已不在购物车，请刷新页面后查看。
- **db**：删行后 tombstone；旧 id 不 upsert

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

- `python3 scripts/reset_namespace.py --case-id PB-B11-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B11-AC2-POS · 加购与改数量

- AC：`PB-B11-AC2` · PB：`PB-B11` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.7` · 场景：`V03 / W03`
- 实现任务：B-002、B-008、B-009、B-020、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

空购物车展示「购物车是空的」。提供清空购物车，须二次确认；清空与勾选操作均不创建订单、不影响库存。勾选、全选及默认勾选规则见 `US-B12` / `PB-B12` 与 `US-B14` / `PB-B14`。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「购物车是空的」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B11-AC2-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 加购

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k1}"}`
- Body：`{"productId": "${P-ON-10.id}"}`
- 提取：`{"cartId": "data.cartItemId"}`
- 断言：`{"message": "已加入购物车", "data.quantity": "1"}`

#### 步骤 2 · CUSTOMER_A · 同键重放

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k1}"}`
- Body：`{"productId": "${P-ON-10.id}"}`
- 断言：`{"message": "已加入购物车", "data.cartItemId": "${cartId}", "data.quantity": "1"}`

#### 步骤 3 · CUSTOMER_A · 改量 5

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "5"}`
- 断言：`{"message": "已更新", "data.quantity": "5"}`

#### 步骤 4 · CUSTOMER_A · 改量 0 删行

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "0"}`
- 断言：`{"message": "已移除"}`

#### 步骤 5 · CUSTOMER_A · 旧 id 再改量

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "2"}`
- 断言：`{"message": "该商品已不在购物车，请刷新页面后查看。"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已加入购物车、已更新、已移除、该商品已不在购物车，请刷新页面后查看。
- **db**：删行后 tombstone；旧 id 不 upsert

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

- `python3 scripts/reset_namespace.py --case-id PB-B11-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B11-AC2-POS · 空车与清空

- AC：`PB-B11-AC2` · PB：`PB-B11` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.7` · 场景：`V03 / W03`
- 实现任务：B-002、B-008、B-009、B-020、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

空购物车展示「购物车是空的」。提供清空购物车，须二次确认；清空与勾选操作均不创建订单、不影响库存。勾选、全选及默认勾选规则见 `US-B12` / `PB-B12` 与 `US-B14` / `PB-B14`。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「购物车是空的」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B11-AC2-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 空车 GET

- HTTP `GET` `/api/me/cart`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"empty_message_or_items": "购物车是空的"}`

#### 步骤 2 · CUSTOMER_A · 加购后 DELETE /api/me/cart

- HTTP `DELETE` `/api/me/cart`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"http": 200}`

### 期望（响应 / 页面 / DB）

- **ui_empty**：购物车是空的

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

- `python3 scripts/reset_namespace.py --case-id PB-B11-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B11-AC3-POS · 加购与改数量

- AC：`PB-B11-AC3` · PB：`PB-B11` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.7` · 场景：`V03 / W03`
- 实现任务：B-002、B-008、B-009、B-020、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-08` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

已登录客户的购物车必须服务端持久化：刷新、退出后重新登录、服务重启后仍在。同一账号多端看到同一份购物车。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B11-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 加购

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k1}"}`
- Body：`{"productId": "${P-ON-10.id}"}`
- 提取：`{"cartId": "data.cartItemId"}`
- 断言：`{"message": "已加入购物车", "data.quantity": "1"}`

#### 步骤 2 · CUSTOMER_A · 同键重放

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k1}"}`
- Body：`{"productId": "${P-ON-10.id}"}`
- 断言：`{"message": "已加入购物车", "data.cartItemId": "${cartId}", "data.quantity": "1"}`

#### 步骤 3 · CUSTOMER_A · 改量 5

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "5"}`
- 断言：`{"message": "已更新", "data.quantity": "5"}`

#### 步骤 4 · CUSTOMER_A · 改量 0 删行

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "0"}`
- 断言：`{"message": "已移除"}`

#### 步骤 5 · CUSTOMER_A · 旧 id 再改量

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "2"}`
- 断言：`{"message": "该商品已不在购物车，请刷新页面后查看。"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已加入购物车、已更新、已移除、该商品已不在购物车，请刷新页面后查看。
- **db**：删行后 tombstone；旧 id 不 upsert

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

- `python3 scripts/reset_namespace.py --case-id PB-B11-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B11-AC3-CON · 多端最后写入

- AC：`PB-B11-AC3` · PB：`PB-B11` · 类型：`CON` · 状态：**待执行**
- V3：`5.1.7` · 场景：`V03 / W03`
- 实现任务：B-002、B-008、B-009、B-020、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-08` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

已登录客户的购物车必须服务端持久化：刷新、退出后重新登录、服务重启后仍在。同一账号多端看到同一份购物车。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B11-AC3-CON
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · BARRIER · 两端同时改量

- 操作：`{"barrier": "SEQ-08", "mode": "simultaneous"}`

### 期望（响应 / 页面 / DB）

- **db**：同商品一行；以服务端最后成功为准

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

- `python3 scripts/reset_namespace.py --case-id PB-B11-AC3-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B11-AC4-POS · 加购与改数量

- AC：`PB-B11-AC4` · PB：`PB-B11` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.7` · 场景：`V03 / W03`
- 实现任务：B-002、B-008、B-009、B-020、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-09` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

同一账号两端同时修改同一行数量或同时删除：以服务端最后成功写入为准，按实际落库先后，不按客户端发起时间。最终同一商品仍然只有一行。最后一次成功写入是删除，则该行移除；最后一次成功写入是改数量，则数量等于最后写入值。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B11-AC4-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 加购

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k1}"}`
- Body：`{"productId": "${P-ON-10.id}"}`
- 提取：`{"cartId": "data.cartItemId"}`
- 断言：`{"message": "已加入购物车", "data.quantity": "1"}`

#### 步骤 2 · CUSTOMER_A · 同键重放

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k1}"}`
- Body：`{"productId": "${P-ON-10.id}"}`
- 断言：`{"message": "已加入购物车", "data.cartItemId": "${cartId}", "data.quantity": "1"}`

#### 步骤 3 · CUSTOMER_A · 改量 5

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "5"}`
- 断言：`{"message": "已更新", "data.quantity": "5"}`

#### 步骤 4 · CUSTOMER_A · 改量 0 删行

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "0"}`
- 断言：`{"message": "已移除"}`

#### 步骤 5 · CUSTOMER_A · 旧 id 再改量

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "2"}`
- 断言：`{"message": "该商品已不在购物车，请刷新页面后查看。"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已加入购物车、已更新、已移除、该商品已不在购物车，请刷新页面后查看。
- **db**：删行后 tombstone；旧 id 不 upsert

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

- `python3 scripts/reset_namespace.py --case-id PB-B11-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B11-AC4-CON · 多端最后写入

- AC：`PB-B11-AC4` · PB：`PB-B11` · 类型：`CON` · 状态：**待执行**
- V3：`5.1.7` · 场景：`V03 / W03`
- 实现任务：B-002、B-008、B-009、B-020、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-08` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

同一账号两端同时修改同一行数量或同时删除：以服务端最后成功写入为准，按实际落库先后，不按客户端发起时间。最终同一商品仍然只有一行。最后一次成功写入是删除，则该行移除；最后一次成功写入是改数量，则数量等于最后写入值。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B11-AC4-CON
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · BARRIER · 两端同时改量

- 操作：`{"barrier": "SEQ-08", "mode": "simultaneous"}`

### 期望（响应 / 页面 / DB）

- **db**：同商品一行；以服务端最后成功为准

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

- `python3 scripts/reset_namespace.py --case-id PB-B11-AC4-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B11-AC5-POS · 加购与改数量

- AC：`PB-B11-AC5` · PB：`PB-B11` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.7` · 场景：`V03 / W03`
- 实现任务：B-002、B-008、B-009、B-020、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-09` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

一端已成功删除某购物车行后，另一端仍用旧页面对该行提交「修改数量」：拒绝该请求，该行保持已删除，不重建；库存与订单不变，其他行不变，提示「该商品已不在购物车，请刷新页面后查看。」该改数量不是一次成功写入，因此「最后成功写入」仍是先前的删除。要让该商品回到购物车，客户必须主动执行「加入购物车」，不得靠旧页面的改数量隐式重建。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「该商品已不在购物车，请刷新页面后查看。」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B11-AC5-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 加购

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k1}"}`
- Body：`{"productId": "${P-ON-10.id}"}`
- 提取：`{"cartId": "data.cartItemId"}`
- 断言：`{"message": "已加入购物车", "data.quantity": "1"}`

#### 步骤 2 · CUSTOMER_A · 同键重放

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k1}"}`
- Body：`{"productId": "${P-ON-10.id}"}`
- 断言：`{"message": "已加入购物车", "data.cartItemId": "${cartId}", "data.quantity": "1"}`

#### 步骤 3 · CUSTOMER_A · 改量 5

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "5"}`
- 断言：`{"message": "已更新", "data.quantity": "5"}`

#### 步骤 4 · CUSTOMER_A · 改量 0 删行

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "0"}`
- 断言：`{"message": "已移除"}`

#### 步骤 5 · CUSTOMER_A · 旧 id 再改量

- HTTP `PATCH` `/api/me/cart/items/${cartId}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- Body：`{"quantity": "2"}`
- 断言：`{"message": "该商品已不在购物车，请刷新页面后查看。"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已加入购物车、已更新、已移除、该商品已不在购物车，请刷新页面后查看。
- **db**：删行后 tombstone；旧 id 不 upsert

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

- `python3 scripts/reset_namespace.py --case-id PB-B11-AC5-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
