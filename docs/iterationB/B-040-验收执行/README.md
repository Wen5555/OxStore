# B-040 收口报告 · 缺陷复验 / 全 AC 验收 / Review 记录

> **结论（2026-11-21，SUT `develop@29c20ea`）：79 AC / 78 通过 / 1 失败（阻断），Review 准入不成立。**
> 15 个 PB 故事中 **14 个全通过**；PB-B13 因 `PB-B13-AC2` 的结算余数无法通过公开 API 观察，保留 1 条
> 开放缺陷 **D-001**，责任任务 B-011 / R1。其余任务（B-030、B-031、B-032、B-033、B-034、B-035、
> B-036、B-037）均已执行并归档；B-031/B-032 遗留的 B08-AC1、B09-AC1 已由 B-037 复验通过。

## 全量结果

| 指标 | 数值 |
|---|---|
| AC 总数 | 79 |
| 通过 | **78** |
| 失败 | **1**（PB-B13-AC2） |
| 故事全通过 | 14 / 15 |
| 拍卖回归 | PASS（19 合取，不计 PB-B 新故事） |
| 本分支新增执行合取 | 247（B-033 79 + B-034 63 + B-035 63 + B-037 42） |
| 真实浏览器流程 | 12 PASS（B-036） |

机器可读：[coverage-final.json](./coverage-final.json)（每条 AC 含状态、证据包、UI 流程、备注）。

## R2 任务完成情况

| 任务 | 内容 | 状态 | 证据 |
|---|---|---|---|
| B-030 | AC/用例/并发方案 | 完成（方案基线） | [B-030](../B-030-本轮验收用例/README.md) |
| B-031 | 收藏/购物车 21 AC | 19 PASS + 2 由 B-037 复验通过 → **21/21** | 分支 `cursor/b031-favorites-cart-392f` |
| B-032 | 结算原子性 26 AC | 25 PASS + **1 FAIL（B13-AC2）** | 分支 `cursor/b032-checkout-atomicity-392f` |
| B-033 | 五态/取消/回补 19 AC | **19/19** PASS（79 合取） | [B-033](../B-033-验收执行/README.md) |
| B-034 | 转收藏 13 AC | **13/13** PASS（63 合取） | [B-034](../B-034-验收执行/README.md) |
| B-035 | 旧意向归档 + 拍卖回归 | **10/10** PASS + 拍卖 19 合取 | [B-035](../B-035-验收执行/README.md) |
| B-036 | 真实前后端 V01～V09 | 12 流程 PASS，14 截图 | [B-036](../B-036-验收执行/README.md) |
| B-037 | 固定提示/持久化/安全 + 复验 | 5/6 检查 PASS；B13 仍失败 | [B-037](../B-037-验收执行/README.md) |
| B-040 | 缺陷复验/全 AC 收口/Review | 完成收口，结论不通过 | 本目录 |

## 开放缺陷

| ID | AC | 严重度 | 责任 | 状态 |
|---|---|---|---|---|
| D-001 | PB-B13-AC2 | 阻断 | B-011 / R1 | **OPEN** |

详见 [defect-log.md](./defect-log.md)。

## Review 记录

见 [review-record.md](./review-record.md)：R2 给出不通过结论与行动项，待 B-011 修复/补测试窗口后复验。

## 交付与复现

- 所有包都用统一结构：`README.md` + `scripts/` + `evidence/` + `fixtures/env.example` + `runs/.gitignore`；
- 每个包可独立重跑（README 内含命令），SUT 固定 `develop@29c20ea`，数据库名均 `oxstore_test_b0xx`；
- 本地口令/Token 只在 gitignore 的 `runs/.env.local` / `runs/state.json`，证据 JSON 已扫描无 JWT；
- B-031/B-032 的证据在各自分支（PR 未合并），本报告通过分支名引用，未复制其内容。
