# PB-B14 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B14-AC1-POS · 转收藏同事务

- AC：`PB-B14-AC1` · PB：`PB-B14` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.10` · 场景：`V09 / W03、W11、W12`
- 实现任务：B-005、B-009、B-020、B-025、B-027 · 测试任务：B-034、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

「转为收藏」是移动，不是复制：成功后对应购物车行整行移出，不是把商品复制一份到收藏后再留在购物车。收藏不持有数量；一行数量为 5 时，也只产生一条收藏，二次确认与成功提示中的 N 按商品行数计，N = 1。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B14-AC1-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作：`{"ref": "helper:cart_two_lines"}`

#### 步骤 2 · UI · 二次确认文案

- 操作：`{"page": "/buyer/cart", "assert_text": "所选 2 件商品将从购物车移除并加入收藏"}`

#### 步骤 3 · CUSTOMER_A · move-to-favorites

- HTTP `POST` `/api/me/cart/move-to-favorites`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}`
- Body：`{"cartItemIds": ["${c1}", "${c2}"]}`
- 断言：`{"message_match": "已收藏 2 件商品"}`

#### 步骤 4 · DB · 车行移除且收藏存在；库存不变；无订单

- 操作：`{"sql": ["SELECT COUNT(*) FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username='b030_buyer_a'; -- 0 for moved", "SELECT COUNT(*) FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username='b030_buyer_a'; -- >=2", "SELECT COUNT(*) FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username='b030_buyer_a' AND so.created_at > ${t0}; -- 0"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已收藏 N 件商品
- **forbidden**：中间结果
- **db**：收藏写入与移车同事务

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

- `python3 scripts/reset_namespace.py --case-id PB-B14-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B14-AC2-POS · 转收藏同事务

- AC：`PB-B14-AC2` · PB：`PB-B14` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.10` · 场景：`V09 / W03、W11、W12`
- 实现任务：B-005、B-009、B-020、B-025、B-027 · 测试任务：B-034、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

转收藏须登录，并校验购物车与目标收藏均属当前客户。未登录提示「请先登录」，登录失效提示「请重新登录」。混入他人购物车行，或试图写入他人收藏：整次拒绝，提示「无权操作」，所有数据不变。商家无代客户转收藏的权限与入口；该操作拒绝，提示「无此权限」。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请先登录」, 「请重新登录」, 「无权操作」, 「无此权限」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B14-AC2-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作：`{"ref": "helper:cart_two_lines"}`

#### 步骤 2 · UI · 二次确认文案

- 操作：`{"page": "/buyer/cart", "assert_text": "所选 2 件商品将从购物车移除并加入收藏"}`

#### 步骤 3 · CUSTOMER_A · move-to-favorites

- HTTP `POST` `/api/me/cart/move-to-favorites`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}`
- Body：`{"cartItemIds": ["${c1}", "${c2}"]}`
- 断言：`{"message_match": "已收藏 2 件商品"}`

#### 步骤 4 · DB · 车行移除且收藏存在；库存不变；无订单

- 操作：`{"sql": ["SELECT COUNT(*) FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username='b030_buyer_a'; -- 0 for moved", "SELECT COUNT(*) FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username='b030_buyer_a'; -- >=2", "SELECT COUNT(*) FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username='b030_buyer_a' AND so.created_at > ${t0}; -- 0"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已收藏 N 件商品
- **forbidden**：中间结果
- **db**：收藏写入与移车同事务

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

- `python3 scripts/reset_namespace.py --case-id PB-B14-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B14-AC3-POS · 转收藏同事务

- AC：`PB-B14-AC3` · PB：`PB-B14` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.10` · 场景：`V09 / W03、W11、W12`
- 实现任务：B-005、B-009、B-020、B-025、B-027 · 测试任务：B-034、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

沿用逐行勾选、全选与取消全选，但「可收藏」与「可下单」不同，以是否在售为准：默认全选可收藏行（即在售行）；已下架或不存在的行不可勾选，全选不包含它们。仍在售但库存大于 0 且少于购物车数量的行可以转收藏（只看是否在售，不看数量是否够下单）。空购物车或未勾选任何行：拒绝，提示「请选择商品」，数据不变。只选部分行时，未选行的数量与状态全部不变；未选行即使已失效，也不影响本次处理。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请选择商品」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B14-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作：`{"ref": "helper:cart_two_lines"}`

#### 步骤 2 · UI · 二次确认文案

- 操作：`{"page": "/buyer/cart", "assert_text": "所选 2 件商品将从购物车移除并加入收藏"}`

#### 步骤 3 · CUSTOMER_A · move-to-favorites

- HTTP `POST` `/api/me/cart/move-to-favorites`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}`
- Body：`{"cartItemIds": ["${c1}", "${c2}"]}`
- 断言：`{"message_match": "已收藏 2 件商品"}`

#### 步骤 4 · DB · 车行移除且收藏存在；库存不变；无订单

- 操作：`{"sql": ["SELECT COUNT(*) FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username='b030_buyer_a'; -- 0 for moved", "SELECT COUNT(*) FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username='b030_buyer_a'; -- >=2", "SELECT COUNT(*) FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username='b030_buyer_a' AND so.created_at > ${t0}; -- 0"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已收藏 N 件商品
- **forbidden**：中间结果
- **db**：收藏写入与移车同事务

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

- `python3 scripts/reset_namespace.py --case-id PB-B14-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B14-AC3-CON · 转收藏 vs 取消收藏

- AC：`PB-B14-AC3` · PB：`PB-B14` · 类型：`CON` · 状态：**待执行**
- V3：`5.1.10` · 场景：`V09 / W03、W11、W12`
- 实现任务：B-005、B-009、B-020、B-025、B-027 · 测试任务：B-034、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

沿用逐行勾选、全选与取消全选，但「可收藏」与「可下单」不同，以是否在售为准：默认全选可收藏行（即在售行）；已下架或不存在的行不可勾选，全选不包含它们。仍在售但库存大于 0 且少于购物车数量的行可以转收藏（只看是否在售，不看数量是否够下单）。空购物车或未勾选任何行：拒绝，提示「请选择商品」，数据不变。只选部分行时，未选行的数量与状态全部不变；未选行即使已失效，也不影响本次处理。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请选择商品」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B14-AC3-CON
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · BARRIER · SEQ-10

- 操作：`{"barrier": "SEQ-10", "mode": "simultaneous"}`

### 期望（响应 / 页面 / DB）

- **db**：车行已移除；最终收藏可为空；同键重试不复活

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

- `python3 scripts/reset_namespace.py --case-id PB-B14-AC3-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B14-AC3-CON · 转收藏期间删光所选行

- AC：`PB-B14-AC3` · PB：`PB-B14` · 类型：`CON` · 状态：**待执行**
- V3：`5.1.10` · 场景：`V09 / W03、W11、W12`
- 实现任务：B-005、B-009、B-020、B-025、B-027 · 测试任务：B-034、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-11` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

沿用逐行勾选、全选与取消全选，但「可收藏」与「可下单」不同，以是否在售为准：默认全选可收藏行（即在售行）；已下架或不存在的行不可勾选，全选不包含它们。仍在售但库存大于 0 且少于购物车数量的行可以转收藏（只看是否在售，不看数量是否够下单）。空购物车或未勾选任何行：拒绝，提示「请选择商品」，数据不变。只选部分行时，未选行的数量与状态全部不变；未选行即使已失效，也不影响本次处理。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请选择商品」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B14-AC3-CON
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · BARRIER · SEQ-11

- 操作：`{"barrier": "SEQ-11", "mode": "b_first"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：请选择商品
- **db**：无半成功

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

- `python3 scripts/reset_namespace.py --case-id PB-B14-AC3-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B14-AC4-POS · 转收藏同事务

- AC：`PB-B14-AC4` · PB：`PB-B14` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.10` · 场景：`V09 / W03、W11、W12`
- 实现任务：B-005、B-009、B-020、B-025、B-027 · 测试任务：B-034、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

须二次确认，确认文案为「所选 N 件商品将从购物车移除并加入收藏」，N 等于所选商品行数。全部成功提示「已收藏 N 件商品」。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「所选 N 件商品将从购物车移除并加入收藏」, 「已收藏 N 件商品」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B14-AC4-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作：`{"ref": "helper:cart_two_lines"}`

#### 步骤 2 · UI · 二次确认文案

- 操作：`{"page": "/buyer/cart", "assert_text": "所选 2 件商品将从购物车移除并加入收藏"}`

#### 步骤 3 · CUSTOMER_A · move-to-favorites

- HTTP `POST` `/api/me/cart/move-to-favorites`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}`
- Body：`{"cartItemIds": ["${c1}", "${c2}"]}`
- 断言：`{"message_match": "已收藏 2 件商品"}`

#### 步骤 4 · DB · 车行移除且收藏存在；库存不变；无订单

- 操作：`{"sql": ["SELECT COUNT(*) FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username='b030_buyer_a'; -- 0 for moved", "SELECT COUNT(*) FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username='b030_buyer_a'; -- >=2", "SELECT COUNT(*) FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username='b030_buyer_a' AND so.created_at > ${t0}; -- 0"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已收藏 N 件商品
- **forbidden**：中间结果
- **db**：收藏写入与移车同事务

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

- `python3 scripts/reset_namespace.py --case-id PB-B14-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B14-AC5-POS · 转收藏同事务

- AC：`PB-B14-AC5` · PB：`PB-B14` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.10` · 场景：`V09 / W03、W11、W12`
- 实现任务：B-005、B-009、B-020、B-025、B-027 · 测试任务：B-034、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

同一商品已在收藏中时，再转收藏视为成功：保持原收藏，不新增、不取消、不刷新收藏时间；但购物车行仍须整行移除，不能因「无需新增收藏」而跳过移车。这不是详情页「再次点击即取消收藏」。未收藏的在售商品则新增一条收藏，收藏时间为当前时间。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B14-AC5-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作：`{"ref": "helper:cart_two_lines"}`

#### 步骤 2 · UI · 二次确认文案

- 操作：`{"page": "/buyer/cart", "assert_text": "所选 2 件商品将从购物车移除并加入收藏"}`

#### 步骤 3 · CUSTOMER_A · move-to-favorites

- HTTP `POST` `/api/me/cart/move-to-favorites`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}`
- Body：`{"cartItemIds": ["${c1}", "${c2}"]}`
- 断言：`{"message_match": "已收藏 2 件商品"}`

#### 步骤 4 · DB · 车行移除且收藏存在；库存不变；无订单

- 操作：`{"sql": ["SELECT COUNT(*) FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username='b030_buyer_a'; -- 0 for moved", "SELECT COUNT(*) FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username='b030_buyer_a'; -- >=2", "SELECT COUNT(*) FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username='b030_buyer_a' AND so.created_at > ${t0}; -- 0"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已收藏 N 件商品
- **forbidden**：中间结果
- **db**：收藏写入与移车同事务

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

- `python3 scripts/reset_namespace.py --case-id PB-B14-AC5-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B14-AC5-CON · 转收藏 vs 取消收藏

- AC：`PB-B14-AC5` · PB：`PB-B14` · 类型：`CON` · 状态：**待执行**
- V3：`5.1.10` · 场景：`V09 / W03、W11、W12`
- 实现任务：B-005、B-009、B-020、B-025、B-027 · 测试任务：B-034、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

同一商品已在收藏中时，再转收藏视为成功：保持原收藏，不新增、不取消、不刷新收藏时间；但购物车行仍须整行移除，不能因「无需新增收藏」而跳过移车。这不是详情页「再次点击即取消收藏」。未收藏的在售商品则新增一条收藏，收藏时间为当前时间。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B14-AC5-CON
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · BARRIER · SEQ-10

- 操作：`{"barrier": "SEQ-10", "mode": "simultaneous"}`

### 期望（响应 / 页面 / DB）

- **db**：车行已移除；最终收藏可为空；同键重试不复活

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

- `python3 scripts/reset_namespace.py --case-id PB-B14-AC5-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B14-AC5-CON · 转收藏期间删光所选行

- AC：`PB-B14-AC5` · PB：`PB-B14` · 类型：`CON` · 状态：**待执行**
- V3：`5.1.10` · 场景：`V09 / W03、W11、W12`
- 实现任务：B-005、B-009、B-020、B-025、B-027 · 测试任务：B-034、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-11` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

同一商品已在收藏中时，再转收藏视为成功：保持原收藏，不新增、不取消、不刷新收藏时间；但购物车行仍须整行移除，不能因「无需新增收藏」而跳过移车。这不是详情页「再次点击即取消收藏」。未收藏的在售商品则新增一条收藏，收藏时间为当前时间。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B14-AC5-CON
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · BARRIER · SEQ-11

- 操作：`{"barrier": "SEQ-11", "mode": "b_first"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：请选择商品
- **db**：无半成功

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

- `python3 scripts/reset_namespace.py --case-id PB-B14-AC5-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B14-AC6-POS · 转收藏同事务

- AC：`PB-B14-AC6` · PB：`PB-B14` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.10` · 场景：`V09 / W03、W11、W12`
- 实现任务：B-005、B-009、B-020、B-025、B-027 · 测试任务：B-034、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

仅在售商品可经本操作新建收藏。「仅在售可新建收藏」完整适用于转收藏。购物车中已下架或不存在的行不可勾选；服务端若收到这类行，该行视为失败项。若某商品先前已有一条失效收藏，本次仍因商品此刻不在售而拒绝，不可因「已有失效收藏」视为成功，也不改写其失效状态。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B14-AC6-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作：`{"ref": "helper:cart_two_lines"}`

#### 步骤 2 · UI · 二次确认文案

- 操作：`{"page": "/buyer/cart", "assert_text": "所选 2 件商品将从购物车移除并加入收藏"}`

#### 步骤 3 · CUSTOMER_A · move-to-favorites

- HTTP `POST` `/api/me/cart/move-to-favorites`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}`
- Body：`{"cartItemIds": ["${c1}", "${c2}"]}`
- 断言：`{"message_match": "已收藏 2 件商品"}`

#### 步骤 4 · DB · 车行移除且收藏存在；库存不变；无订单

- 操作：`{"sql": ["SELECT COUNT(*) FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username='b030_buyer_a'; -- 0 for moved", "SELECT COUNT(*) FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username='b030_buyer_a'; -- >=2", "SELECT COUNT(*) FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username='b030_buyer_a' AND so.created_at > ${t0}; -- 0"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已收藏 N 件商品
- **forbidden**：中间结果
- **db**：收藏写入与移车同事务

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

- `python3 scripts/reset_namespace.py --case-id PB-B14-AC6-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B14-AC7-POS · 转收藏同事务

- AC：`PB-B14-AC7` · PB：`PB-B14` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.10` · 场景：`V09 / W03、W11、W12`
- 实现任务：B-005、B-009、B-020、B-025、B-027 · 测试任务：B-034、B-036、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

混合批次必须全部成功或全部失败，不允许部分成功。成功项 = 在售（无论是否已收藏）；失败项 = 已下架或不存在。批次中任一失败项，则整次失败并回滚：不新增任何收藏、不移除任何购物车行；提示须逐项指出问题商品及原因（已下架用「商品已下架」，不存在用「商品不存在」），不静默跳过失败项却提示全部成功，也不再用「无货」作为另一种并存标注。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「商品已下架」
- **禁止作为状态/中间态/旧规则出现**：「商品不存在」, 「无货」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B14-AC7-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作：`{"ref": "helper:cart_two_lines"}`

#### 步骤 2 · UI · 二次确认文案

- 操作：`{"page": "/buyer/cart", "assert_text": "所选 2 件商品将从购物车移除并加入收藏"}`

#### 步骤 3 · CUSTOMER_A · move-to-favorites

- HTTP `POST` `/api/me/cart/move-to-favorites`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}`
- Body：`{"cartItemIds": ["${c1}", "${c2}"]}`
- 断言：`{"message_match": "已收藏 2 件商品"}`

#### 步骤 4 · DB · 车行移除且收藏存在；库存不变；无订单

- 操作：`{"sql": ["SELECT COUNT(*) FROM cart_item ci JOIN customer c ON c.id=ci.customer_id WHERE c.username='b030_buyer_a'; -- 0 for moved", "SELECT COUNT(*) FROM favorite f JOIN customer c ON c.id=f.customer_id WHERE c.username='b030_buyer_a'; -- >=2", "SELECT COUNT(*) FROM shop_order so JOIN customer c ON c.id=so.customer_id WHERE c.username='b030_buyer_a' AND so.created_at > ${t0}; -- 0"]}`

### 期望（响应 / 页面 / DB）

- **required_messages**：已收藏 N 件商品
- **forbidden**：中间结果
- **db**：收藏写入与移车同事务

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

- `python3 scripts/reset_namespace.py --case-id PB-B14-AC7-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
