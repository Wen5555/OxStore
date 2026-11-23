# B-040 收口报告 · 缺陷复验 / 全 AC 验收 / Review 记录

> **结论（2026-11-23，SUT `develop@ebe3f32`）：79 AC / 79 通过 / 0 失败，Review 准入通过。**
> 15 个 PB 故事全部通过。此前 2 条阻断缺陷均已关闭：
> **D-001（PB-B13-AC2 锁后加购）** 由 PR #36 测试钩子 + R2 在独立 MySQL 执行复验；
> **D-002（PB-B09-AC1 失效收藏点击提示）** 由 PR #35 修复 + B-036 真实 Chrome 复验。
> B-031 的 PB-B08-AC1 原 FAIL 属测试期望错误，已改判 PASS。

## 全量结果

| 指标 | 数值 |
|---|---|
| AC 总数 | 79 |
| 通过 | **79** |
| 失败 | **0** |
| 故事全通过 | **15 / 15** |
| 拍卖回归 | PASS（19 合取，不计 PB-B 新故事） |
| 本分支新增执行合取 | 253（B-033 79 + B-034 63 + B-035 63 + B-037 48） |
| 真实浏览器流程 | 12 PASS + D-002 复验（15 张截图） |

机器可读：[coverage-final.json](./coverage-final.json)（每条 AC 含状态、证据包、UI 流程、备注）。

## R2 任务完成情况

| 任务 | 内容 | 状态 | 证据 |
|---|---|---|---|
| B-030 | AC/用例/并发方案 | 完成（方案基线） | [B-030](../B-030-本轮验收用例/README.md) |
| B-031 | 收藏/购物车 21 AC | **21/21**（B08 改判，B09 由 D-002 修复后通过） | 分支 `cursor/b031-favorites-cart-392f` |
| B-032 | 结算原子性 26 AC | **26/26**（B13-AC2 受控复验通过） | 分支 `cursor/b032-checkout-atomicity-392f` |
| B-033 | 五态/取消/回补 19 AC | **19/19**（79 合取） | [B-033](../B-033-验收执行/README.md) |
| B-034 | 转收藏 13 AC | **13/13**（63 合取） | [B-034](../B-034-验收执行/README.md) |
| B-035 | 旧意向归档 + 拍卖回归 | **10/10** + 拍卖 19 合取 | [B-035](../B-035-验收执行/README.md) |
| B-036 | 真实前后端 V01～V09 | 12 流程 + D-002 复验 PASS | [B-036](../B-036-验收执行/README.md) |
| B-037 | 固定提示/持久化/安全 + 复验 | **6/6**（48 合取；D-001 受控复验） | [B-037](../B-037-验收执行/README.md) |
| B-040 | 缺陷复验/全 AC 收口/Review | **通过（79/79）** | 本目录 |

## 缺陷关闭

| ID | AC | 修复 | 复验结论 |
|---|---|---|---|
| D-001 | PB-B13-AC2 | PR #36（`topic/r1`，仅测试钩子） | 关闭：R2 在 MySQL `oxstore_test_d001` 跑 `ChallengeBCheckoutPublicApiConcurrencyTest` 2/2 PASS；订单 qty=2 + 新行 qty=1 + 库存 3 + 原键 40909 |
| D-002 | PB-B09-AC1 | PR #35（`topic/r3`，前端） | 关闭：真实 Chrome 点击失效收藏 toast=「已下架」，URL 不变 |
| B08-AC1 | PB-B08-AC1 | 测试期望纠正 | 关闭：B-037 按实际「角色无权访问」复验 5/5 PASS |

详见 [defect-log.md](./defect-log.md)。

## Review 记录

见 [review-record.md](./review-record.md)：R2 给出通过结论，门禁全部满足。

## 交付与复现

- 所有包统一结构：`README.md` + `scripts/` + `evidence/` + `fixtures/env.example` + `runs/.gitignore`；
- SUT 固定 `develop@ebe3f32`（PR #35/#36 合并后），数据库名均 `oxstore_test_b0xx` / `oxstore_test_d001`；
- 本地口令/Token 只在 gitignore 的 `runs/.env.local` / `runs/state.json`，证据 JSON 已扫描无 JWT；
- B-031/B-032 证据在各自分支（PR #33/#34），本报告通过分支名引用。
