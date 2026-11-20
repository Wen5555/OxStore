# B-030 并发 SEQ（可运行栅栏）

工具：`python3 scripts/barrier_runner.py --seq SEQ-XX --mode {a_first|b_first|simultaneous} --a-cmd '...' --b-cmd '...'`

全部 SEQ 状态：**待执行**。禁止仅靠人工连点宣称通过。故障注入仅测试侧（如 mock 抛错），不改业务代码。

环境变量：`${BASE}`=`$B030_BASE_URL`；`${TA}`/`${TB}`/`${TS}` 为客户 A/B、商家 JWT；商品/订单 ID 来自 `runs/fixture-ids.json`。

## SEQ-01 库存1双买（高风险 · B032）

| 项 | 内容 |
|---|---|
| 映射用例 | `PB-B13-AC5-CON`、`PB-B02-AC2` |
| Fixtures | `P-ON-1` stock=`1`；A/B 各确认 qty=1，不同 Idempotency-Key |
| 双会话 | S-CUSTOMER_A、S-CUSTOMER_B |
| 模式 | `simultaneous`（另跑 `a_first`/`b_first`） |
| A 命令 | `curl -sS -X POST "$BASE/api/me/orders" -H "Authorization: Bearer $TA" -H "Idempotency-Key: $KA" -H "Content-Type: application/json" -d "{\"confirmationToken\":\"$CA\"}"` |
| B 命令 | 同上换 `$TB/$KB/$CB` |
| 观察点 | HTTP message；`product.stock`；`shop_order` 行数；车行 |
| 合法结果 | 恰 1 单成功扣至 0；另一整单拒绝；无半单；库存非负 |

## SEQ-02 同结算同键重放（B032）

| 项 | 内容 |
|---|---|
| 映射 | `PB-B13-AC4-BND` |
| 模式 | `a_first`：A 成功后丢弃响应；A' 同 token+同键重放（可用单线程两次，不必双进程） |
| 合法结果 | message=`订单已提交，请勿重复下单`；订单仍 1；库存/车不二次处理 |

## SEQ-03 锁前改量 vs 锁后加购（B032）

| 项 | 内容 |
|---|---|
| 映射 | `PB-B13-AC5` / `PB-B13-AC2` |
| 模式 | `a_first`（锁前改）与注入延迟提交（锁后加购）分两次跑 |
| 合法结果 | 锁前变更进入最新校验或要求重确认；锁后增量保留为余数 |

## SEQ-04 取消 vs 发货（B033）

| 项 | 内容 |
|---|---|
| 映射 | `PB-B05` 并发取消 |
| Fixtures | 订单 `PREPARED` |
| A | 客户 `POST /api/me/orders/{id}/cancel` `expectedStatus=PREPARED` |
| B | 商家 `POST /api/admin/orders/{id}/actions` `action=SHIP` `expectedStatus=PREPARED` |
| 模式 | `simultaneous` / `a_first` / `b_first` |
| 合法结果 | 先成功；后到拒绝；库存只按最终结果变一次 |

## SEQ-05 取消 vs 确认/备货（B033）

同 SEQ-04，B 端改为 `CONFIRM` 或 `PREPARE`。

## SEQ-06 双方取消（B033）

A 客户取消 vs B 商家取消；先成功 `CANCELLED`；后到 `订单已取消`；回补一次。

## SEQ-07 商家取消 vs 完成（B033）

`SHIPPED` 上 cancel vs `COMPLETE`；互斥单终态。

## SEQ-08 多端购物车最后写入（B031）

两端同时 `PATCH` 同行数量；最终一行；以服务端最后成功为准。

## SEQ-09 旧页改量 vs 已删行（B031）

B 先删行（`b_first`）；A 旧 `cartItemId` 改量 → `该商品已不在购物车，请刷新页面后查看。`；不重建行。

## SEQ-10 转收藏 vs 取消收藏（B034 · 高风险相关）

A：`POST /api/me/cart/move-to-favorites`；B：`DELETE /api/me/favorites/{productId}`（取消锁更晚可用 `a_first`）。车行已移除；最终可无收藏；同键重试不复活。

## SEQ-11 转收藏期间删光所选行（B034 · 高风险 3 行 1 下架配套）

准备 3 行车；B 先删光所选；A move → `请选择商品`；无半成功（部分收藏+部分留车禁止）。

## SEQ-12 五态推进并发（B033）

两连接对同一 `PLACED` 单同时 `CONFIRM`；恰一成功；不跳步、不重复扣库。

## 高风险三例落地入口

| 例 | SEQ/用例 | 命令入口 |
|---|---|---|
| 库存1双买 | SEQ-01 + `PB-B13-AC5-CON` | `barrier_runner.py --seq SEQ-01 --mode simultaneous ...` |
| 3 行转收藏且 1 下架 | `execution/B034.md` HR-2 + SEQ-11 变体 | 见 B034 |
| 下单 3 次回补不双倍 | `execution/B033.md` HR-3 | 取消三次同单 → 库存只回补一次 |

## 记录模板

结果 JSON：`runs/SEQ-XX-<mode>.json`；另存 SQL 快照与 `B030_SUT_SHA`。未跑不标通过。
