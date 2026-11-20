# PB-B10 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B10-AC1-POS · 加购与改数量

- AC：`PB-B10-AC1` · PB：`PB-B10` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.6` · 场景：`V01、V03 / W01、W03`
- 实现任务：B-002、B-003、B-005、B-008、B-018、B-020 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

加购是写操作，必须登录。不允许游客购物车，不做本地暂存，不做登录后合并。未登录点击加购：拒绝，提示「请先登录」，不在任何客户名下生成购物车记录；登录失效：拒绝，提示「请重新登录」。登录成功后回到原页面，由客户重新点击，不自动补做刚才的加购。客户只能查看和修改自己的购物车；操作他人购物车：拒绝，提示「无权操作」，数据不变。本轮不提供商家查看或修改客户购物车的权限；卖家把商品加入客户购物车：拒绝，不支持。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请先登录」, 「请重新登录」, 「无权操作」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B10-AC1-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B10-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B10-AC1-NEG · 未登录/越权购物车

- AC：`PB-B10-AC1` · PB：`PB-B10` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.6` · 场景：`V01、V03 / W01、W03`
- 实现任务：B-002、B-003、B-005、B-008、B-018、B-020 · 测试任务：B-031、B-036、B-037
- 角色/会话：ANON, CUSTOMER_B / S-ANON, S-CUSTOMER_B
- Fixtures：P-ON-10

### 验收标准原文

加购是写操作，必须登录。不允许游客购物车，不做本地暂存，不做登录后合并。未登录点击加购：拒绝，提示「请先登录」，不在任何客户名下生成购物车记录；登录失效：拒绝，提示「请重新登录」。登录成功后回到原页面，由客户重新点击，不自动补做刚才的加购。客户只能查看和修改自己的购物车；操作他人购物车：拒绝，提示「无权操作」，数据不变。本轮不提供商家查看或修改客户购物车的权限；卖家把商品加入客户购物车：拒绝，不支持。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请先登录」, 「请重新登录」, 「无权操作」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B10-AC1-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · ANON · 加购

- HTTP `POST` `/api/me/cart/items`
- Headers：`{"Idempotency-Key": "${k}"}`
- Body：`{"productId": "${P-ON-10.id}"}`
- 断言：`{"message": "请先登录"}`

#### 步骤 2 · CUSTOMER_B · 改 A 的 cartItemId

- HTTP `PATCH` `/api/me/cart/items/${cartIdA}`
- Headers：`{"Authorization": "Bearer ${tokenB}"}`
- Body：`{"quantity": "9"}`
- 断言：`{"message": "无权操作"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：请先登录、无权操作

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

- `python3 scripts/reset_namespace.py --case-id PB-B10-AC1-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B10-AC2-POS · 加购与改数量

- AC：`PB-B10-AC2` · PB：`PB-B10` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.6` · 场景：`V01、V03 / W01、W03`
- 实现任务：B-002、B-003、B-005、B-008、B-018、B-020 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-08` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

一个购物车可同时放多个不同商品，同一客户与同一商品始终只有一行，数量承载在该行上，任何路径不得产生两行。同一商品再次加购时数量累加，不新增多行。同一请求被网络重试或双击重复提交时须幂等，不得把数量加两次，提示「已加入购物车」。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：「已加入购物车」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B10-AC2-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B10-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B10-AC2-CON · 多端最后写入

- AC：`PB-B10-AC2` · PB：`PB-B10` · 类型：`CON` · 状态：**待执行**
- V3：`5.1.6` · 场景：`V01、V03 / W01、W03`
- 实现任务：B-002、B-003、B-005、B-008、B-018、B-020 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-08` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

一个购物车可同时放多个不同商品，同一客户与同一商品始终只有一行，数量承载在该行上，任何路径不得产生两行。同一商品再次加购时数量累加，不新增多行。同一请求被网络重试或双击重复提交时须幂等，不得把数量加两次，提示「已加入购物车」。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：「已加入购物车」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B10-AC2-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B10-AC2-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B10-AC3-POS · 加购与改数量

- AC：`PB-B10-AC3` · PB：`PB-B10` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.6` · 场景：`V01、V03 / W01、W03`
- 实现任务：B-002、B-003、B-005、B-008、B-018、B-020 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-09` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

加购、改数量、删除均不创建订单，不预占、不扣减、不锁定库存。加购成功不等于一定能买到；库存校验只在下单时发生（见 `US-B12` / `PB-B12`）。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B10-AC3-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B10-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B10-AC4-POS · 加购与改数量

- AC：`PB-B10-AC4` · PB：`PB-B10` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.6` · 场景：`V01、V03 / W01、W03`
- 实现任务：B-002、B-003、B-005、B-008、B-018、B-020 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-09` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

单行数量与购物车总件数均无上限，删除「超限」类提示。首次加购、再次加购、在购物车内改数量，均不校验「数量 ≤ 当前库存」。唯一数量校验：数量必须为正整数；改为 0 则删除该行，提示「已移除」；改为负数或小数则拒绝并保持原数量，提示「数量无效，请输入正整数」。手动删除单行同样提示「已移除」。合法改数量成功提示「已更新」。首次加购成功提示「已加入购物车」。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已移除」, 「数量无效，请输入正整数」, 「已更新」, 「已加入购物车」
- **禁止作为状态/中间态/旧规则出现**：「超限」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B10-AC4-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B10-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B10-AC5-POS · 加购与改数量

- AC：`PB-B10-AC5` · PB：`PB-B10` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.6` · 场景：`V01、V03 / W01、W03`
- 实现任务：B-002、B-003、B-005、B-008、B-018、B-020 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

加购入口只出现在商品详情页；商品列表、搜索卡片不提供快捷加购。详情页加购默认加入 1 件，再到购物车内改数量，不在详情页先选件数。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B10-AC5-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B10-AC5-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B10-AC6-POS · 加购与改数量

- AC：`PB-B10-AC6` · PB：`PB-B10` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.6` · 场景：`V01、V03 / W01、W03`
- 实现任务：B-002、B-003、B-005、B-008、B-018、B-020 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

对已下架（含售罄、零库存自动下架）商品发起新加购：拒绝，提示「商品已下架」，不新增行。对不存在的商品发起新加购：拒绝，提示「商品不存在」，不新增行。不并用「无货」作为另一种拒绝文案。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「商品已下架」, 「商品不存在」
- **禁止作为状态/中间态/旧规则出现**：「无货」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B10-AC6-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B10-AC6-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
