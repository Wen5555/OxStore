# PB-B08 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B08-AC1-POS · 首次与重复收藏

- AC：`PB-B08-AC1` · PB：`PB-B08` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.4` · 场景：`V01 / W01`
- 实现任务：B-002、B-005、B-007、B-018 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

收藏是写操作，必须登录，仅能查看和操作本人收藏，无游客暂存、无本地暂存。商家不可访问客户收藏。未登录点击收藏：拒绝，提示「请先登录」，不创建记录；登录失效：拒绝，提示「请重新登录」。登录成功后回到原页面，由客户重新点击，不自动补做刚才的收藏。访问或修改他人收藏：拒绝，提示「无权操作」，数据不变。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请先登录」, 「请重新登录」, 「无权操作」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B08-AC1-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 登录

- HTTP `POST` `/api/auth/login`
- Body：`{"username": "b030_buyer_a", "password": "B030-BuyerA-Pass9"}`
- 提取：`{"tokenA": "data.token"}`

#### 步骤 2 · CUSTOMER_A · 首次收藏

- HTTP `PUT` `/api/me/favorites/${P-ON-10.id}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 提取：`{"createdAt": "data.createdAt", "favoriteId": "data.favoriteId"}`
- 断言：`{"http": 200, "message": "已收藏"}`

#### 步骤 3 · CUSTOMER_A · 重复收藏

- HTTP `PUT` `/api/me/favorites/${P-ON-10.id}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"http": 200, "message": "已收藏", "data.createdAt": "${createdAt}"}`

#### 步骤 4 · DB · 唯一行且 created_at 不变

- 操作：`{"sql": ["SELECT COUNT(*), MIN(created_at)=MAX(created_at) FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username='b030_buyer_a' AND f.product_id=${P-ON-10.id};"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已收藏
- **db**：UNIQUE(customer,product)；重复不刷新时间

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

- `python3 scripts/reset_namespace.py --case-id PB-B08-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B08-AC1-NEG · 未登录收藏

- AC：`PB-B08-AC1` · PB：`PB-B08` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.4` · 场景：`V01 / W01`
- 实现任务：B-002、B-005、B-007、B-018 · 测试任务：B-031、B-036、B-037
- 角色/会话：ANON / S-ANON
- Fixtures：P-ON-10

### 验收标准原文

收藏是写操作，必须登录，仅能查看和操作本人收藏，无游客暂存、无本地暂存。商家不可访问客户收藏。未登录点击收藏：拒绝，提示「请先登录」，不创建记录；登录失效：拒绝，提示「请重新登录」。登录成功后回到原页面，由客户重新点击，不自动补做刚才的收藏。访问或修改他人收藏：拒绝，提示「无权操作」，数据不变。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请先登录」, 「请重新登录」, 「无权操作」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B08-AC1-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · ANON · 无 Authorization 收藏

- HTTP `PUT` `/api/me/favorites/${P-ON-10.id}`
- 断言：`{"message": "请先登录"}`

#### 步骤 2 · DB · 无新收藏

- 操作：`{"sql": ["SELECT COUNT(*) FROM favorite f JOIN product p ON p.id=f.product_id WHERE p.name LIKE 'B030-%'; -- 0 new"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：请先登录
- **db**：不写入

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

- `python3 scripts/reset_namespace.py --case-id PB-B08-AC1-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B08-AC2-POS · 列表失效项展示

- AC：`PB-B08-AC2` · PB：`PB-B08` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.4` · 场景：`V01 / W01`
- 实现任务：B-002、B-005、B-007、B-018 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

收藏只作标记，不生成订单，不占用、不扣减、不预占库存，不改变商品状态。允许不收藏直接购买（购买路径仍须经购物车，见 `US-B12` / `PB-B12`）。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B08-AC2-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 收藏后商家下架

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py favorite_then_offline --product P-ON-10
# HTTP：PUT /api/me/favorites/{id} → POST /api/admin/products/{id}/offline
```

#### 步骤 2 · CUSTOMER_A · GET 列表

- HTTP `GET` `/api/me/favorites?page=1`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"contains_badge": "已下架"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：
- **ui_labels**：已下架
- **page**：失效项保留且不可进可购买详情

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

- `python3 scripts/reset_namespace.py --case-id PB-B08-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B08-AC3-POS · 首次与重复收藏

- AC：`PB-B08-AC3` · PB：`PB-B08` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.4` · 场景：`V01 / W01`
- 实现任务：B-002、B-005、B-007、B-018 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

同一客户对同一商品有且仅有一条收藏。重复收藏（含同一请求被网络重试、双击重复提交）为幂等成功：不新增、不取消、不刷新收藏时间，提示「已收藏」。UI 上，未收藏时点击为收藏，已收藏时点击为「取消收藏」；二者是不同操作，靠操作语义区分，不靠点击次数。首次收藏成功提示「已收藏」。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已收藏」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B08-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 登录

- HTTP `POST` `/api/auth/login`
- Body：`{"username": "b030_buyer_a", "password": "B030-BuyerA-Pass9"}`
- 提取：`{"tokenA": "data.token"}`

#### 步骤 2 · CUSTOMER_A · 首次收藏

- HTTP `PUT` `/api/me/favorites/${P-ON-10.id}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 提取：`{"createdAt": "data.createdAt", "favoriteId": "data.favoriteId"}`
- 断言：`{"http": 200, "message": "已收藏"}`

#### 步骤 3 · CUSTOMER_A · 重复收藏

- HTTP `PUT` `/api/me/favorites/${P-ON-10.id}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"http": 200, "message": "已收藏", "data.createdAt": "${createdAt}"}`

#### 步骤 4 · DB · 唯一行且 created_at 不变

- 操作：`{"sql": ["SELECT COUNT(*), MIN(created_at)=MAX(created_at) FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username='b030_buyer_a' AND f.product_id=${P-ON-10.id};"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已收藏
- **db**：UNIQUE(customer,product)；重复不刷新时间

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

- `python3 scripts/reset_namespace.py --case-id PB-B08-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B08-AC3-POS · 取消收藏

- AC：`PB-B08-AC3` · PB：`PB-B08` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.4` · 场景：`V01 / W01`
- 实现任务：B-002、B-005、B-007、B-018 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

同一客户对同一商品有且仅有一条收藏。重复收藏（含同一请求被网络重试、双击重复提交）为幂等成功：不新增、不取消、不刷新收藏时间，提示「已收藏」。UI 上，未收藏时点击为收藏，已收藏时点击为「取消收藏」；二者是不同操作，靠操作语义区分，不靠点击次数。首次收藏成功提示「已收藏」。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已收藏」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B08-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 确保已收藏

- HTTP `PUT` `/api/me/favorites/${P-ON-10.id}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"message": "已收藏"}`

#### 步骤 2 · CUSTOMER_A · 取消

- HTTP `DELETE` `/api/me/favorites/${P-ON-10.id}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"message": "已取消收藏"}`

#### 步骤 3 · CUSTOMER_A · 再取消

- HTTP `DELETE` `/api/me/favorites/${P-ON-10.id}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"message": "未收藏"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已取消收藏、未收藏

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

- `python3 scripts/reset_namespace.py --case-id PB-B08-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B08-AC3-POS · 列表失效项展示

- AC：`PB-B08-AC3` · PB：`PB-B08` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.4` · 场景：`V01 / W01`
- 实现任务：B-002、B-005、B-007、B-018 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

同一客户对同一商品有且仅有一条收藏。重复收藏（含同一请求被网络重试、双击重复提交）为幂等成功：不新增、不取消、不刷新收藏时间，提示「已收藏」。UI 上，未收藏时点击为收藏，已收藏时点击为「取消收藏」；二者是不同操作，靠操作语义区分，不靠点击次数。首次收藏成功提示「已收藏」。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已收藏」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B08-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 收藏后商家下架

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py favorite_then_offline --product P-ON-10
# HTTP：PUT /api/me/favorites/{id} → POST /api/admin/products/{id}/offline
```

#### 步骤 2 · CUSTOMER_A · GET 列表

- HTTP `GET` `/api/me/favorites?page=1`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"contains_badge": "已下架"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：
- **ui_labels**：已下架
- **page**：失效项保留且不可进可购买详情

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

- `python3 scripts/reset_namespace.py --case-id PB-B08-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B08-AC4-NEG · 下架商品不可新收藏

- AC：`PB-B08-AC4` · PB：`PB-B08` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.4` · 场景：`V01 / W01`
- 实现任务：B-002、B-005、B-007、B-018 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-OFF-M

### 验收标准原文

仅在售商品可新建收藏。对已下架（含因零库存自动下架）商品新建收藏：拒绝，提示「商品已下架」，不新建记录。对不存在的商品新建收藏：拒绝，提示「商品不存在」，不新建记录。零库存与已下架是同一状态，不并用「无货」作为另一种标注或另一种拒绝文案。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「商品已下架」, 「商品不存在」
- **禁止作为状态/中间态/旧规则出现**：「无货」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B08-AC4-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 收藏人工下架商品

- HTTP `PUT` `/api/me/favorites/${P-OFF-M.id}`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"message": "商品已下架"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：商品已下架
- **db**：不新建

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

- `python3 scripts/reset_namespace.py --case-id PB-B08-AC4-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B08-AC4-POS · 列表失效项展示

- AC：`PB-B08-AC4` · PB：`PB-B08` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.4` · 场景：`V01 / W01`
- 实现任务：B-002、B-005、B-007、B-018 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

仅在售商品可新建收藏。对已下架（含因零库存自动下架）商品新建收藏：拒绝，提示「商品已下架」，不新建记录。对不存在的商品新建收藏：拒绝，提示「商品不存在」，不新建记录。零库存与已下架是同一状态，不并用「无货」作为另一种标注或另一种拒绝文案。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「商品已下架」, 「商品不存在」
- **禁止作为状态/中间态/旧规则出现**：「无货」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B08-AC4-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 收藏后商家下架

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py favorite_then_offline --product P-ON-10
# HTTP：PUT /api/me/favorites/{id} → POST /api/admin/products/{id}/offline
```

#### 步骤 2 · CUSTOMER_A · GET 列表

- HTTP `GET` `/api/me/favorites?page=1`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"contains_badge": "已下架"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：
- **ui_labels**：已下架
- **page**：失效项保留且不可进可购买详情

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

- `python3 scripts/reset_namespace.py --case-id PB-B08-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B08-AC5-POS · 列表失效项展示

- AC：`PB-B08-AC5` · PB：`PB-B08` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.4` · 场景：`V01 / W01`
- 实现任务：B-002、B-005、B-007、B-018 · 测试任务：B-031、B-036、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

收藏入口只出现在商品详情页；商品列表、搜索卡片不提供快捷收藏。入口处须区分已收藏与未收藏。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B08-AC5-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 收藏后商家下架

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py favorite_then_offline --product P-ON-10
# HTTP：PUT /api/me/favorites/{id} → POST /api/admin/products/{id}/offline
```

#### 步骤 2 · CUSTOMER_A · GET 列表

- HTTP `GET` `/api/me/favorites?page=1`
- Headers：`{"Authorization": "Bearer ${tokenA}"}`
- 断言：`{"contains_badge": "已下架"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：
- **ui_labels**：已下架
- **page**：失效项保留且不可进可购买详情

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

- `python3 scripts/reset_namespace.py --case-id PB-B08-AC5-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
