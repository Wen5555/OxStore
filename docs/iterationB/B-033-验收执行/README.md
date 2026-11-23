# B-033 独立验收包 · 五态/双方取消/回补（PB-B04 ×7、B05 ×4、B06 ×6、B07 ×2）

> **最终态更新（2026-11-23，配置经理按 B-040 同步，原结果未改动）**
>
> 本包里 5 条验收标准（PB-B04-AC5、AC6、AC7，PB-B06-AC5、AC6）的状态是 `PASS_API_DEFERRED`：API 与数据库部分通过，UI 入口、二次确认等部分转后续任务，**当时不计为最终通过**。
> [B-040 的 coverage-final.json](../B-040-验收执行/coverage-final.json) 记录这 5 条已由 B-036 的真实浏览器流程补齐
> （PB-B04-AC5～AC7 对应 `V05-HISTORY`，PB-B06-AC5、AC6 对应 `V06-SELLER-FLOW`），并计为 PASS。本包的证据未改动，补齐部分的证据在 [B-036](../B-036-验收执行/README.md)，未在本包内重跑。


> 结论（2026-11-21，SUT `develop@29c20ea`）：**19 AC / 19 通过 / 0 失败 / 0 阻塞，79 个合取**
> （含 SEQ-12 一条并发序列）。5 条 AC 的 UI 入口/二次确认/旧意向数据仍待后续任务承接，
> 状态标为 `PASS_API_DEFERRED`，不计为整条 AC 的最终通过。
>
> 执行的是 B-030 冻结的方案（cases/PB-B04～B07.md、concurrency/SEQ.md、execution/B033.md），
> 不重定义 AC、不改写提示原文。

## 被测对象

| 项 | 值 |
|---|---|
| SUT | `develop@29c20ea0927528a98f873f4a1a0e169a6fa12281` |
| 交付基线 | `topic/r2@0cef9ec`（文档分支 `cursor/b030-acceptance-cases-392f`） |
| 后端 | Spring Boot `:8081`（本机 jar，独立实例） |
| 数据库 | MySQL 8.0 `oxstore_test_b033`（与 B-034 的 b034 库隔离） |
| 前端 | 未启动；UI 项转 B-036 |

## 结果

| 证据 | 内容 |
|---|---|
| [evidence/results.json](./evidence/results.json) | 执行窗口、SUT、DB、19 AC 汇总 |
| [evidence/results.md](./evidence/results.md) | 结果表与失败合取（本次为空） |
| [evidence/cases/](./evidence/cases/) | 每 AC 合取明细（HTTP + DB 快照，JWT 脱敏） |
| [acs-19.json](./acs-19.json) | AC ↔ 用例 ↔ 合取清单 |

## 覆盖要点

- **五态**：PLACED→CONFIRMED→PREPARED 客户可取消；SHIPPED 起客户不可取消；商家在 SHIPPED 仍可取消；
  COMPLETED 双方不可取消；`allowedActions` 随状态收敛。
- **回补**：按快照数量、只回补一次（重复/三次取消均 409）；AUTO_ZERO 且补后>0 自动上架；
  手动下架保持 OFFLINE/MANUAL；商家后续调库存与回补叠加。
- **并发**：客户取消 vs 发货、取消 vs 确认/备货、双方取消、商家取消 vs 完成、双 CONFIRM，
  均用线程栅栏同时发起，只接受合法终态，库存只变一次。
- **元数据**：CANCELLED + cancelledBy(CUSTOMER/SELLER) + cancelledAt + cancelReason 可由
  `/api/me/orders`、`/api/admin/orders` 列表/详情追溯。
- **整单**：`items`/`itemIds` 部分取消一律 400「不支持部分取消」。

## 边界与转交

| 项 | 承接任务 |
|---|---|
| 取消入口显示/禁用、二次确认、列表与详情交互 | B-036 |
| 已关闭旧意向（purchase_intent.legacy_closed / V8 归档）不可取消 | B-035（本包已证明新订单接口无此路径） |
| 固定提示原文、持久化/重启、安全负例 | B-037 |
| 全量 AC 收口与缺陷复验 | B-040 |

## 复现

```powershell
cd docs/iterationB/B-030-本轮验收用例
$env:B030_BASE_URL="http://127.0.0.1:8081"; $env:B030_DB_NAME="oxstore_test_b033"
python scripts/prepare_fixtures.py
cd ../B-033-验收执行
python scripts/run_acs.py                # 退出码 0 = 无 FAIL/BLOCKED
```

`--only PB-B05-AC3` 可单跑一条。`runs/.env.local` 保存本机连接信息（已 gitignore）。

## 环境事实

- 本包复用 B-030 的 `reset_namespace.py`，但在 `b033_common.reset()` 中先剥离注释行再按 `;` 执行，
  避免 B-030 脚本“注释开头语句被整段跳过”导致商品状态未复位（B-034 已记录同一问题）。
- 两套后端实例（8080/b034、8081/b033）共用同一 MySQL 服务但库名隔离；`prepare_fixtures.py`
  会用当前 env 重写 `B-030/runs/fixture-ids.json`，切换任务前必须用对应 env 重新 prepare。
