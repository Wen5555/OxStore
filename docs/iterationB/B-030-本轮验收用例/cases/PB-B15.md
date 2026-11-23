# PB-B15 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B15-AC1-POS · 转收藏同事务

- AC：`PB-B15-AC1` · PB：`PB-B15` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

收藏写入与购物车行移除必须在同一事务内，要么都成功，要么都回滚，不允许对客户呈现中间结果。本操作无论成功或失败，均不生成订单、不改变商品状态、不改变库存。转入后的收藏仍按商品身份绑定，展示实时名称、价格、主图；后续失效、恢复与重新发布的规则与 `US-B09` / `PB-B09` 相同。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC1-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py cart_two_lines
# 产出 c1/c2/tokenA（P-ON-10 与 P-ON-5 各一行）
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC1-CON · 转收藏 vs 取消收藏

- AC：`PB-B15-AC1` · PB：`PB-B15` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

收藏写入与购物车行移除必须在同一事务内，要么都成功，要么都回滚，不允许对客户呈现中间结果。本操作无论成功或失败，均不生成订单、不改变商品状态、不改变库存。转入后的收藏仍按商品身份绑定，展示实时名称、价格、主图；后续失效、恢复与重新发布的规则与 `US-B09` / `PB-B09` 相同。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC1-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC1-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC1-CON · 转收藏期间删光所选行

- AC：`PB-B15-AC1` · PB：`PB-B15` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-11` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

收藏写入与购物车行移除必须在同一事务内，要么都成功，要么都回滚，不允许对客户呈现中间结果。本操作无论成功或失败，均不生成订单、不改变商品状态、不改变库存。转入后的收藏仍按商品身份绑定，展示实时名称、价格、主图；后续失效、恢复与重新发布的规则与 `US-B09` / `PB-B09` 相同。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC1-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC1-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC2-POS · 转收藏同事务

- AC：`PB-B15-AC2` · PB：`PB-B15` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

同一次转收藏被双击、网络重试或刷新后重试：最多处理一次，收藏不重复、购物车不重复清理，提示「请勿重复操作」。服务端已完成但响应丢失时，客户通过收藏列表（应出现目标商品）和购物车（对应行应消失）确认原结果；重试靠同一请求的幂等键拦截。写入失败或移车失败时整单回滚，提示「操作失败，请重试」。客户后来主动再次发起的新操作使用新的幂等键。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请勿重复操作」, 「操作失败，请重试」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC2-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py cart_two_lines
# 产出 c1/c2/tokenA（P-ON-10 与 P-ON-5 各一行）
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC2-CON · 转收藏 vs 取消收藏

- AC：`PB-B15-AC2` · PB：`PB-B15` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

同一次转收藏被双击、网络重试或刷新后重试：最多处理一次，收藏不重复、购物车不重复清理，提示「请勿重复操作」。服务端已完成但响应丢失时，客户通过收藏列表（应出现目标商品）和购物车（对应行应消失）确认原结果；重试靠同一请求的幂等键拦截。写入失败或移车失败时整单回滚，提示「操作失败，请重试」。客户后来主动再次发起的新操作使用新的幂等键。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请勿重复操作」, 「操作失败，请重试」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC2-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC2-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC2-CON · 转收藏期间删光所选行

- AC：`PB-B15-AC2` · PB：`PB-B15` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-11` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

同一次转收藏被双击、网络重试或刷新后重试：最多处理一次，收藏不重复、购物车不重复清理，提示「请勿重复操作」。服务端已完成但响应丢失时，客户通过收藏列表（应出现目标商品）和购物车（对应行应消失）确认原结果；重试靠同一请求的幂等键拦截。写入失败或移车失败时整单回滚，提示「操作失败，请重试」。客户后来主动再次发起的新操作使用新的幂等键。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请勿重复操作」, 「操作失败，请重试」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC2-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC2-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC3-POS · 转收藏同事务

- AC：`PB-B15-AC3` · PB：`PB-B15` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间另一端改数量或再次加购：不影响（收藏不看数量，且为整行移动）；锁定后该行已移除，后续加购须重新加购。提交期间另端新增的数量因整行移动而一并移除，无「余数保留」（与下单清车不同）。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py cart_two_lines
# 产出 c1/c2/tokenA（P-ON-10 与 P-ON-5 各一行）
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC3-CON · 转收藏 vs 取消收藏

- AC：`PB-B15-AC3` · PB：`PB-B15` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间另一端改数量或再次加购：不影响（收藏不看数量，且为整行移动）；锁定后该行已移除，后续加购须重新加购。提交期间另端新增的数量因整行移动而一并移除，无「余数保留」（与下单清车不同）。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC3-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC3-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC3-CON · 转收藏期间删光所选行

- AC：`PB-B15-AC3` · PB：`PB-B15` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-11` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间另一端改数量或再次加购：不影响（收藏不看数量，且为整行移动）；锁定后该行已移除，后续加购须重新加购。提交期间另端新增的数量因整行移动而一并移除，无「余数保留」（与下单清车不同）。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC3-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC3-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC4-POS · 转收藏同事务

- AC：`PB-B15-AC4` · PB：`PB-B15` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间另一端删除被选中的某一行：该行不再处理、不视为失败项，其余在售行仍可成功。若被选中的行在提交前全部被删光：拒绝，提示「请选择商品」，数据不变，与空选一致。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请选择商品」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC4-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py cart_two_lines
# 产出 c1/c2/tokenA（P-ON-10 与 P-ON-5 各一行）
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC4-CON · 转收藏 vs 取消收藏

- AC：`PB-B15-AC4` · PB：`PB-B15` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间另一端删除被选中的某一行：该行不再处理、不视为失败项，其余在售行仍可成功。若被选中的行在提交前全部被删光：拒绝，提示「请选择商品」，数据不变，与空选一致。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请选择商品」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC4-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC4-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC4-CON · 转收藏期间删光所选行

- AC：`PB-B15-AC4` · PB：`PB-B15` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-11` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间另一端删除被选中的某一行：该行不再处理、不视为失败项，其余在售行仍可成功。若被选中的行在提交前全部被删光：拒绝，提示「请选择商品」，数据不变，与空选一致。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请选择商品」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC4-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC4-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC4-NEG · 空选转收藏

- AC：`PB-B15-AC4` · PB：`PB-B15` · 类型：`NEG` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：（无商品 fixture）

### 验收标准原文

提交期间另一端删除被选中的某一行：该行不再处理、不视为失败项，其余在售行仍可成功。若被选中的行在提交前全部被删光：拒绝，提示「请选择商品」，数据不变，与空选一致。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「请选择商品」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC4-NEG
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · cartItemIds=[]

- HTTP `POST` `/api/me/cart/move-to-favorites`
- Headers：`{"Authorization": "Bearer ${tokenA}", "Idempotency-Key": "${k}"}`
- Body：`{"cartItemIds": []}`
- 断言：`{"message": "请选择商品"}`

### 期望（响应 / 页面 / DB）

- **required_messages**：请选择商品

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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC4-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC5-POS · 转收藏同事务

- AC：`PB-B15-AC5` · PB：`PB-B15` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间另一端取消同一商品的收藏，且取消的锁定更晚：最终收藏保持已取消，但购物车该行仍被整行移除。转收藏请求返回「已收藏 N 件商品」，取消请求返回「已取消收藏」，最终收藏列表显示已取消。这与「原转收藏已成功后，客户再取消收藏，然后重试原请求」不同：重试同一幂等键时不重新执行、返回原结果、不重新收藏（该行已移出购物车，无对象可转）；取消收藏是新的独立操作。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已收藏 N 件商品」, 「已取消收藏」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC5-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py cart_two_lines
# 产出 c1/c2/tokenA（P-ON-10 与 P-ON-5 各一行）
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC5-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC5-CON · 转收藏 vs 取消收藏

- AC：`PB-B15-AC5` · PB：`PB-B15` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间另一端取消同一商品的收藏，且取消的锁定更晚：最终收藏保持已取消，但购物车该行仍被整行移除。转收藏请求返回「已收藏 N 件商品」，取消请求返回「已取消收藏」，最终收藏列表显示已取消。这与「原转收藏已成功后，客户再取消收藏，然后重试原请求」不同：重试同一幂等键时不重新执行、返回原结果、不重新收藏（该行已移出购物车，无对象可转）；取消收藏是新的独立操作。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已收藏 N 件商品」, 「已取消收藏」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC5-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC5-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC5-CON · 转收藏期间删光所选行

- AC：`PB-B15-AC5` · PB：`PB-B15` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-11` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间另一端取消同一商品的收藏，且取消的锁定更晚：最终收藏保持已取消，但购物车该行仍被整行移除。转收藏请求返回「已收藏 N 件商品」，取消请求返回「已取消收藏」，最终收藏列表显示已取消。这与「原转收藏已成功后，客户再取消收藏，然后重试原请求」不同：重试同一幂等键时不重新执行、返回原结果、不重新收藏（该行已移出购物车，无对象可转）；取消收藏是新的独立操作。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已收藏 N 件商品」, 「已取消收藏」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC5-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC5-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC6-POS · 转收藏同事务

- AC：`PB-B15-AC6` · PB：`PB-B15` · 类型：`POS` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10, P-ON-5
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间商品变为已下架或不存在：拒绝该行，整次失败并回滚。一次转收藏无额外行数上限。不新增收藏批量管理功能。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC6-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 车内两行在售

- 操作（已展开）：
**实现**
```bash
python3 scripts/run_helper.py cart_two_lines
# 产出 c1/c2/tokenA（P-ON-10 与 P-ON-5 各一行）
```

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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC6-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC6-CON · 转收藏 vs 取消收藏

- AC：`PB-B15-AC6` · PB：`PB-B15` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-10` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间商品变为已下架或不存在：拒绝该行，整次失败并回滚。一次转收藏无额外行数上限。不新增收藏批量管理功能。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC6-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC6-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B15-AC6-CON · 转收藏期间删光所选行

- AC：`PB-B15-AC6` · PB：`PB-B15` · 类型：`CON` · 状态：**待执行**
- V3：`5.3.6` · 场景：`V09 / W11、W12`
- 实现任务：B-003、B-025、B-026、B-027 · 测试任务：B-028、B-034、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10
- 并发 SEQ：`SEQ-11` → `concurrency/SEQ.md` + `scripts/barrier_runner.py`

### 验收标准原文

提交期间商品变为已下架或不存在：拒绝该行，整次失败并回滚。一次转收藏无额外行数上限。不新增收藏批量管理功能。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B15-AC6-CON
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

- `python3 scripts/reset_namespace.py --case-id PB-B15-AC6-CON`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
