# 拍卖模式数据字典与迁移说明（P-A01 / P-A02）

- 负责人：R5 张耀文；P-A01 审核 R1，P-A02 审核 R2
- 日期：2026-11-06（Asia/Shanghai）
- 契约：[P-A00 拍卖增量契约](P-A00-拍卖增量契约.md)
- 文件：空库 [schema.sql](../../backend/src/main/resources/db/schema.sql)；旧库 [V6__auction_mode.sql](../../backend/src/main/resources/db/migrations/V6__auction_mode.sql)；升级入口 [migrate_iteration2.py](../../scripts/migrate_iteration2.py)
- 验证：[拍卖数据库验证报告](../test/auction-database-validation.md)

## 1. 变更概览

| 对象 | 变更 | 任务 |
| --- | --- | --- |
| `product` | 新增 `selling_mode`（默认 `FIXED_PRICE`）、模式与拍卖库存约束、`idx_product_mode_status_time`、模式不可修改触发器 | P-A01 |
| `product_status_event` | `chk_event_type` 增加 `AUCTION_UNSOLD` | P-A01 |
| `auction_session` | 新表：拍卖参数、当前价、领先者、状态、截止时间、结拍时间、中标意向 | P-A01 |
| `auction_bid` | 新表：有效出价记录 | P-A02 |
| `auction_notification` | 新表：结拍站内提醒 | P-A02 |

既有九张表的其他列、约束和索引不变；`purchase_intent`、`trade_attempt`、`order_history` 不加列，中标履约通过 `auction_session.winner_intent_id` 关联。

## 2. 字段字典

### 2.1 `product` 增量

| 列 | 类型 | 空 | 说明 |
| --- | --- | --- | --- |
| `selling_mode` | VARCHAR(20) | 否 | `FIXED_PRICE`/`AUCTION`，默认 `FIXED_PRICE`；发布后不可改 |

| 约束/索引 | 规则 |
| --- | --- |
| `chk_product_selling_mode` | 只允许两种模式 |
| `chk_product_auction_stock` | `AUCTION` 商品库存只能是 0 或 1（成交后为 0） |
| `trg_product_selling_mode_immutable` | `BEFORE UPDATE` 拒绝修改模式（MySQL 错误 1644） |
| `idx_product_mode_status_time` | `(selling_mode, status, published_at, id)`，按模式筛选在售列表 |

拍卖商品的 `price` 写入起拍价，满足既有 `price > 0` 约束并让旧列表接口有可显示价格；实时价格以 `auction_session` 为准。

### 2.2 `auction_session`

| 列 | 类型 | 空 | 说明 |
| --- | --- | --- | --- |
| `id` | BIGINT | 否 | 主键 |
| `product_id` | BIGINT | 否 | 商品，唯一（与商品一对一） |
| `start_price` | DECIMAL(10,2) | 否 | 起拍价 > 0 |
| `min_increment` | DECIMAL(10,2) | 否 | 最小加价 > 0 |
| `current_price` | DECIMAL(10,2) | 是 | 当前最高有效出价；无出价为 NULL |
| `leader_customer_id` | BIGINT | 是 | 当前领先顾客；无出价为 NULL |
| `bid_count` | INT | 否 | 有效出价数，默认 0；也是最新出价的 `bid_seq` |
| `status` | VARCHAR(20) | 否 | `LIVE`/`ENDED_SOLD`/`ENDED_UNSOLD` |
| `starts_at` | DATETIME(6) | 否 | 开拍时间（发布时间） |
| `ends_at` | DATETIME(6) | 否 | 截止时间，晚于 `starts_at` |
| `settled_at` | DATETIME(6) | 是 | 结拍时间，`LIVE` 时为 NULL |
| `winner_intent_id` | BIGINT | 是 | 中标后创建的 `purchase_intent`，唯一 |
| `version` | BIGINT | 否 | JPA 乐观锁版本 |

| 约束/索引 | 规则 |
| --- | --- |
| `uk_auction_product` | 一个商品至多一个场次 |
| `uk_auction_winner_intent` | 一条意向至多挂接一个场次 |
| `fk_auction_product` / `fk_auction_leader` / `fk_auction_winner_intent` | 指向 `product`、`customer`、`purchase_intent` |
| `chk_auction_prices` | 起拍价、最小加价均 > 0 |
| `chk_auction_window` | `ends_at > starts_at` |
| `chk_auction_status` | 三种状态 |
| `chk_auction_leading` | 无出价时当前价、领先者都为空；有出价时两者都非空且当前价 ≥ 起拍价 |
| `chk_auction_settlement` | `LIVE` 无结拍时间和中标意向；`ENDED_SOLD` 必须有出价、结拍时间和中标意向；`ENDED_UNSOLD` 必须无出价、无中标意向 |
| `idx_auction_status_ends` | `(status, ends_at, id)`，结拍扫描 |
| `idx_auction_leader` | 按领先者查询“我领先的拍卖” |

### 2.3 `auction_bid`

| 列 | 类型 | 空 | 说明 |
| --- | --- | --- | --- |
| `id` | BIGINT | 否 | 主键 |
| `auction_id` | BIGINT | 否 | 场次 |
| `bid_seq` | INT | 否 | 场次内序号，从 1 递增，等于接受后的 `bid_count` |
| `customer_id` | BIGINT | 否 | 出价顾客 |
| `amount` | DECIMAL(10,2) | 否 | 出价金额 > 0 |
| `bid_at` | DATETIME(6) | 否 | 接受时间（Asia/Shanghai） |

| 约束/索引 | 规则 |
| --- | --- |
| `uk_bid_auction_seq` | 同场次序号唯一：两个事务基于同一旧状态写入时后者失败（映射 40904） |
| `uk_bid_auction_amount` | 同场次金额唯一：英式增价下有效出价严格递增，重复金额必为并发冲突 |
| `idx_bid_customer_time` | 顾客出价记录 |
| `fk_bid_auction` / `fk_bid_customer` | 外键 |

只保存有效出价；被拒绝的出价不落库，原因通过错误码返回。

### 2.4 `auction_notification`

| 列 | 类型 | 空 | 说明 |
| --- | --- | --- | --- |
| `id` | BIGINT | 否 | 主键 |
| `auction_id` | BIGINT | 否 | 场次 |
| `notification_type` | VARCHAR(30) | 否 | `AUCTION_SOLD`/`AUCTION_UNSOLD`/`AUCTION_WON` |
| `recipient_role` | VARCHAR(10) | 否 | `SELLER`/`CUSTOMER` |
| `recipient_customer_id` | BIGINT | 是 | `CUSTOMER` 提醒的收件人；卖家提醒为 NULL（全部卖家账号共享后台） |
| `product_name_snapshot` | VARCHAR(200) | 否 | 结拍时商品名快照 |
| `final_price` | DECIMAL(10,2) | 是 | 成交价；流拍为 NULL |
| `created_at` | DATETIME(6) | 否 | 生成时间 |
| `read_at` | DATETIME(6) | 是 | 已读时间 |

| 约束/索引 | 规则 |
| --- | --- |
| `uk_notification_auction_type` | 同场次同类型一条；类型决定收件人，因此等价于“场次 + 收件人 + 类型”幂等 |
| `chk_notification_type` | 三种类型 |
| `chk_notification_recipient` | `SOLD/UNSOLD` 只发卖家且无顾客；`WON` 只发顾客且必须有顾客 |
| `chk_notification_price` | 流拍无价格；成交类必须有 > 0 的价格 |
| `chk_notification_read` | 已读时间不早于生成时间 |
| `idx_notification_customer_time` / `idx_notification_role_time` | 顾客/卖家提醒列表倒序分页 |

## 3. 迁移与旧库兼容

| 当前库 | 升级入口识别 | 执行 |
| --- | --- | --- |
| 迭代1 五表 | `legacy` | 备份 → V4 → V5 → V6 |
| 迭代2 九表 | `iteration2` | 备份 → V5 → V6 |
| 已含拍卖的十二表 | `auction` | 备份 → V5 → V6（均可重复执行，无数据变化） |
| 其他/残缺结构 | 拒绝 | 不执行任何迁移 |

```powershell
python -X utf8 scripts/migrate_iteration2.py --container <mysql容器> --database <库名>
```

- 旧商品全部得到 `selling_mode='FIXED_PRICE'`，不把任何旧商品转为拍卖；既有列数据不变。
- V6 先检查 V5 已完成（`product_image.size_bytes`），否则在任何改动前停止；各步骤按存在性判断，可在中断后直接重跑。
- 新库由 `schema.sql` 一次建好十二张表，含触发器；`docker-compose.yml` 通过 `docker-entrypoint-initdb.d` 执行，支持其中的 `DELIMITER`。
- 回滚：停应用写入后用升级前自动备份恢复（已验证恢复后数据指纹与升级前一致）。不提供逆向删表脚本，避免误删拍卖数据。

## 4. 后端使用约定（交付 R1）

1. 时间：所有截止判断由应用传入 `BusinessTime.now()`。数据库会话时区不一定是 Asia/Shanghai，SQL 内不用 `NOW()` 判断截止。
2. 出价：事务内 `AuctionSessionRepository.findByProductIdForUpdate` 锁行 → `AuctionSession.acceptBid(customer, amount, now)`（内部校验截止 40906、最低价 40907）→ 保存返回的 `AuctionBid`。`DataIntegrityViolationException`、`OptimisticLockingFailureException` 映射为 40904。
3. 结拍：`findDueIds(LIVE, now, PageRequest.of(0, 50))` 取 ID，逐个新事务 `findByIdForUpdate` 复查 `isDueAt(now)`：
   - 有出价：`PurchaseIntent.submit(product, leader, 1)` → `enterTrade(now)` → 保存 → `product.startTrade(now)` → 新建 `TradeAttempt` 与 `TRADE_STARTED` 事件 → `auction.markSold(intent, now)` → 保存 `AUCTION_SOLD`、`AUCTION_WON` 提醒。意向必须先落库，`ENDED_SOLD` 约束要求中标意向非空。
   - 无出价：`product.takeOffline(now)` 并写 `AUCTION_UNSOLD` 事件 → `auction.markUnsold(now)` → 保存 `AUCTION_UNSOLD` 提醒。
   - 提醒用 `AuctionNotification.forSettlement(auction, type, now)` 构造，保存前可用 `existsByAuctionIdAndType` 跳过，并发重复由唯一键兜底。
4. 拍卖商品 `queue_seq` 固定为 1；该商品不会有排队意向，既有队列查询不受影响。
5. 快照：`findByProductId` 已抓取商品与领先者；出价列表 `findTop10ByAuctionIdOrderByBidSeqDesc`；`myStatus` 结合 `leader` 与 `existsByAuctionIdAndCustomerId` 计算。
6. H2 集成测试按实体建表，不含 MySQL CHECK 与触发器；约束行为以真实 MySQL 验证为准。

## 5. 查询样例

以下 SQL 已在验证容器中实际执行，结果见验证证据 `query_samples`。

```sql
-- 公开快照（领先者脱敏）
SELECT p.id product_id, p.name, p.selling_mode, a.status, a.start_price, a.min_increment,
       a.current_price, a.bid_count, a.ends_at,
       CASE WHEN a.bid_count = 0 THEN a.start_price ELSE a.current_price + a.min_increment END next_min_bid,
       CONCAT(LEFT(c.username, 1), '***', RIGHT(c.username, 1)) leader_alias
FROM auction_session a JOIN product p ON p.id = a.product_id
LEFT JOIN customer c ON c.id = a.leader_customer_id WHERE p.id = ?;

-- 出价前锁定
SELECT id, bid_count, current_price FROM auction_session WHERE product_id = ? FOR UPDATE;

-- 结拍扫描（:now 由应用传入）
SELECT id FROM auction_session WHERE status = 'LIVE' AND ends_at <= ? ORDER BY ends_at, id LIMIT 50;

-- 最近出价
SELECT bid_seq, amount, bid_at FROM auction_bid WHERE auction_id = ? ORDER BY bid_seq DESC LIMIT 10;

-- 顾客 / 卖家提醒
SELECT id, notification_type, product_name_snapshot, final_price, read_at
FROM auction_notification WHERE recipient_customer_id = ? ORDER BY created_at DESC, id DESC LIMIT 20;
SELECT id, notification_type, product_name_snapshot, final_price, read_at
FROM auction_notification WHERE recipient_role = 'SELLER' ORDER BY created_at DESC, id DESC LIMIT 20;

-- 中标履约追溯
SELECT a.id auction_id, a.status, a.current_price final_price, i.id intent_id, i.status intent_status,
       h.status history_status
FROM auction_session a JOIN purchase_intent i ON i.id = a.winner_intent_id
LEFT JOIN order_history h ON h.intent_id = i.id WHERE a.id = ?;
```
