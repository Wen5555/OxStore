# B-035 独立验收包 · 旧意向归档 + 拍卖回归（PB-B02 ×5、PB-B03 ×5）

> 结论（2026-11-21，SUT `develop@29c20ea`）：**10 AC / 10 通过 / 0 失败 / 0 阻塞**，
> 另有拍卖回归 19 个合取全通过；总计 **63 个合取**。
>
> 真实执行了仓库内的 V8 迁移文件（不是复述 SQL），并在拍卖数据存在后**重复执行一次**，
> 证明 V8 幂等且不触碰拍卖会话/出价/提醒/中标意向。

## 被测对象

| 项 | 值 |
|---|---|
| SUT | `develop@29c20ea0927528a98f873f4a1a0e169a6fa12281` |
| 迁移 | `backend/src/main/resources/db/migrations/V8__close_legacy_fixed_price_intents.sql`（真实文件，mysql CLI） |
| 后端 | Spring Boot `:8082`（本机 jar，独立实例） |
| 数据库 | MySQL 8.0 `oxstore_test_b035`（与 b033/b034 隔离） |
| 前端 | 不涉及；V/W 界面项在 B-036 |

## 结果

| 证据 | 内容 |
|---|---|
| [evidence/results.json](./evidence/results.json) | 执行窗口、SUT、DB、V8 路径、10 AC 汇总 |
| [evidence/results.md](./evidence/results.md) | 结果表与失败合取（本次为空） |
| [evidence/cases/](./evidence/cases/) | 每 AC + AUCTION-REG 的合取明细（HTTP/DB/迁移输出） |
| [acs-10.json](./acs-10.json) | AC ↔ 用例 ↔ 合取清单 |

## 本轮实际验证到的关键点

- **V8 关闭语义**：QUEUING/IN_TRANSACTION 的 `status` 原样保留（未改写为 CANCELLED/FAILED），
  只写 `legacy_closed_at + FIXED_PRICE_CHALLENGE_B`；对应未完成 `trade_attempt` 关闭且 `result/finished_at` 仍为 NULL。
- **解冻规则**：`freeze_source=TRADE` 的商品恢复 `ONLINE`；`freeze_source=MANUAL` 的变 `OFFLINE/MANUAL`，
  库存一律不动；库存从 0 改正数不会自动上架，须商家手动上架。
- **旧成功记录**：`SUCCESS` 历史不被 V8 标记关闭。
- **归档只读**：客户/商家 `/api/me|admin/legacy-intents` 可读、`displayStatus=CLOSED`、`readOnly=true`；
  写方法一律拒绝且不改行；旧一口价入口 `POST /api/products/{id}/intents` 返回 409「一口价旧购买意向已关闭」，
  旧队列 GET 已无路由（405）。
- **隔离**：新订单/取消不走旧意向；V8 重复执行 `0/0/0/0`；拍卖会话、出价、提醒数量前后一致，
  拍卖中标意向不被 V8 关闭。
- **拍卖回归**：发布→LIVE→两人出价（低于最小加价 409）→SSE `snapshot`→到点 `ENDED_SOLD`
  →WON/LOST→买家 AUCTION_WON / 商家 AUCTION_SOLD→中标意向 IN_TRANSACTION→拍卖商品拒绝加购（409）；
  无出价场次 `ENDED_UNSOLD`、商品 OFFLINE、商家 AUCTION_UNSOLD。

## 复现

```powershell
cd docs/iterationB/B-030-本轮验收用例
$env:B030_BASE_URL="http://127.0.0.1:8082"; $env:B030_DB_NAME="oxstore_test_b035"
python scripts/prepare_fixtures.py
cd ../B-035-验收执行
python scripts/run_acs.py        # 退出码 0 = 无 FAIL/BLOCKED
```

脚本会：重置命名空间 → 造 3 条旧意向（QUEUING/IN_TRANSACTION/SUCCESS）并冻结 3 个商品 →
执行 V8 → 跑 10 AC → 造两场拍卖并等待结拍（约 70 秒，合同要求 endsAt≥60s）→ 再跑一次 V8。
`runs/.env.local` 保存本机 DB/root 连接信息（已 gitignore）。

## 环境事实

- 拍卖截止时间合同为「当前时间 60 秒至 30 天内」，因此回归用例需等待约 70 秒，不能用 8/18 秒的短场次。
- 购物车加购接口要求 `Idempotency-Key` 为 UUID，缺失时返回 400（不是 409）；用例已按真实契约携带。
- `product_db()`/`query()` 使用完整商品名（不是 fixture code），B-035 脚本内统一从 `LEGACY` 常量取全名。
