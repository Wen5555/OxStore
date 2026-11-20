# PB-B09 · B-030 可执行用例（重写）

> 全部状态：**待执行**。未跑业务验收不得标通过。
> 交付基线 topic/r2@0cef9ec；被测 SHA 另记于 runs/。

## PB-B09-AC1-POS · 首次与重复收藏

- AC：`PB-B09-AC1` · PB：`PB-B09` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

已收藏商品随后下架或售罄：该项保留，统一标注「已下架」，不自动移除；不并存「无货」与「已下架」两种标注。失效项仍展示名称、价格、主图及「已下架」标注，仍可取消收藏；点击不进入可购买详情，仅提示「已下架」。同一商品身份重新上架或库存恢复后，原收藏恢复有效并清除标注。重新发布成另一件商品时，原收藏仍指向旧商品（已下架并标注），不自动转移到新商品。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已下架」
- **禁止作为状态/中间态/旧规则出现**：「无货」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC1-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC1-NEG · 下架商品不可新收藏

- AC：`PB-B09-AC1` · PB：`PB-B09` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-OFF-M

### 验收标准原文

已收藏商品随后下架或售罄：该项保留，统一标注「已下架」，不自动移除；不并存「无货」与「已下架」两种标注。失效项仍展示名称、价格、主图及「已下架」标注，仍可取消收藏；点击不进入可购买详情，仅提示「已下架」。同一商品身份重新上架或库存恢复后，原收藏恢复有效并清除标注。重新发布成另一件商品时，原收藏仍指向旧商品（已下架并标注），不自动转移到新商品。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已下架」
- **禁止作为状态/中间态/旧规则出现**：「无货」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC1-NEG
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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC1-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC1-POS · 取消收藏

- AC：`PB-B09-AC1` · PB：`PB-B09` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

已收藏商品随后下架或售罄：该项保留，统一标注「已下架」，不自动移除；不并存「无货」与「已下架」两种标注。失效项仍展示名称、价格、主图及「已下架」标注，仍可取消收藏；点击不进入可购买详情，仅提示「已下架」。同一商品身份重新上架或库存恢复后，原收藏恢复有效并清除标注。重新发布成另一件商品时，原收藏仍指向旧商品（已下架并标注），不自动转移到新商品。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已下架」
- **禁止作为状态/中间态/旧规则出现**：「无货」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC1-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC1-POS · 列表失效项展示

- AC：`PB-B09-AC1` · PB：`PB-B09` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

已收藏商品随后下架或售罄：该项保留，统一标注「已下架」，不自动移除；不并存「无货」与「已下架」两种标注。失效项仍展示名称、价格、主图及「已下架」标注，仍可取消收藏；点击不进入可购买详情，仅提示「已下架」。同一商品身份重新上架或库存恢复后，原收藏恢复有效并清除标注。重新发布成另一件商品时，原收藏仍指向旧商品（已下架并标注），不自动转移到新商品。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已下架」
- **禁止作为状态/中间态/旧规则出现**：「无货」
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC1-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 收藏后商家下架

- 操作：`{"ref": "helper:favorite_then_offline"}`

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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC1-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC2-POS · 取消收藏

- AC：`PB-B09-AC2` · PB：`PB-B09` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

收藏绑定商品身份，列表展示实时名称、价格、主图，而不是下单那样的交易快照。失效标注在读取时按当前商品状态实时判断。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC2-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC2-POS · 列表失效项展示

- AC：`PB-B09-AC2` · PB：`PB-B09` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

收藏绑定商品身份，列表展示实时名称、价格、主图，而不是下单那样的交易快照。失效标注在读取时按当前商品状态实时判断。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC2-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 收藏后商家下架

- 操作：`{"ref": "helper:favorite_then_offline"}`

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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC2-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC3-POS · 取消收藏

- AC：`PB-B09-AC3` · PB：`PB-B09` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

收藏列表和详情页均可取消收藏，无需二次确认；普通路径下取消成功后立即从列表移除，提示「已取消收藏」。对已不存在的收藏重复取消：幂等成功，提示「未收藏」（仅此一种，不再使用其他成功文案），其他收藏不变。无业务数量上限。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已取消收藏」, 「未收藏」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC3-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC3-POS · 列表失效项展示

- AC：`PB-B09-AC3` · PB：`PB-B09` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

收藏列表和详情页均可取消收藏，无需二次确认；普通路径下取消成功后立即从列表移除，提示「已取消收藏」。对已不存在的收藏重复取消：幂等成功，提示「未收藏」（仅此一种，不再使用其他成功文案），其他收藏不变。无业务数量上限。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「已取消收藏」, 「未收藏」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC3-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 收藏后商家下架

- 操作：`{"ref": "helper:favorite_then_offline"}`

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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC3-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC4-POS · 首次与重复收藏

- AC：`PB-B09-AC4` · PB：`PB-B09` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

收藏列表按收藏时间倒序，分页每页 10 条。幂等重复收藏不改变排序时间；取消后再收藏视为新收藏，时间更新。空列表提示「暂无收藏」。本系统无商品硬删除，「已收藏商品被删除」不适用。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「暂无收藏」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC4-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC4-POS · 取消收藏

- AC：`PB-B09-AC4` · PB：`PB-B09` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

收藏列表按收藏时间倒序，分页每页 10 条。幂等重复收藏不改变排序时间；取消后再收藏视为新收藏，时间更新。空列表提示「暂无收藏」。本系统无商品硬删除，「已收藏商品被删除」不适用。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「暂无收藏」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC4-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC4-POS · 列表失效项展示

- AC：`PB-B09-AC4` · PB：`PB-B09` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A, SELLER / S-CUSTOMER_A, S-SELLER
- Fixtures：P-ON-10

### 验收标准原文

收藏列表按收藏时间倒序，分页每页 10 条。幂等重复收藏不改变排序时间；取消后再收藏视为新收藏，时间更新。空列表提示「暂无收藏」。本系统无商品硬删除，「已收藏商品被删除」不适用。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：「暂无收藏」
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC4-POS
4. Authorization 使用对应会话 JWT；需幂等的请求带新 UUID Idempotency-Key（重试用同键）。

### 步骤（可直接执行）

#### 步骤 1 · CUSTOMER_A · 收藏后商家下架

- 操作：`{"ref": "helper:favorite_then_offline"}`

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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC4-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC5-POS · 首次与重复收藏

- AC：`PB-B09-AC5` · PB：`PB-B09` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

收藏须服务端持久化：刷新、退出后重新登录、服务重启后均保留。同一账号在不同设备看到同一份收藏。同时收藏或取消同一商品，以最后成功写入为准，结果唯一，任何路径不得产生重复收藏记录。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC5-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC5-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC5-NEG · 未登录收藏

- AC：`PB-B09-AC5` · PB：`PB-B09` · 类型：`NEG` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：ANON / S-ANON
- Fixtures：P-ON-10

### 验收标准原文

收藏须服务端持久化：刷新、退出后重新登录、服务重启后均保留。同一账号在不同设备看到同一份收藏。同时收藏或取消同一商品，以最后成功写入为准，结果唯一，任何路径不得产生重复收藏记录。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC5-NEG
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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC5-NEG`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---

## PB-B09-AC5-POS · 取消收藏

- AC：`PB-B09-AC5` · PB：`PB-B09` · 类型：`POS` · 状态：**待执行**
- V3：`5.1.5` · 场景：`V02 / W02`
- 实现任务：B-002、B-007、B-019、B-026 · 测试任务：B-029、B-031、B-037
- 角色/会话：CUSTOMER_A / S-CUSTOMER_A
- Fixtures：P-ON-10

### 验收标准原文

收藏须服务端持久化：刷新、退出后重新登录、服务重启后均保留。同一账号在不同设备看到同一份收藏。同时收藏或取消同一商品，以最后成功写入为准，结果唯一，任何路径不得产生重复收藏记录。

### 文案/标签语义分类（禁止机械摘引号）

- **必须匹配的接口提示（fixedMessages）**：（本 AC 无强制成功/失败提示，或见步骤内 assert）
- **禁止作为状态/中间态/旧规则出现**：（无）
- **UI 状态标签（非错误提示）**：（无）

### 前置

1. 被测候选优先 develop（或已集成挑战 B 的分支）；记录 B030_SUT_SHA，与交付基线 topic/r2@0cef9ec 分开。
2. 独立测试库名 oxstore_b030_* / oxstore_test_*；已跑 scripts/prepare_fixtures.py。
3. 用例前：python3 scripts/reset_namespace.py --case-id PB-B09-AC5-POS
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

- `python3 scripts/reset_namespace.py --case-id PB-B09-AC5-POS`
- `证据写入 runs/<case_id>/（请求响应脱敏 JSON、SQL 快照、可选截图）`

---
