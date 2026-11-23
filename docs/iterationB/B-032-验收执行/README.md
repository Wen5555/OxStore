# B-032 核验包（最终态已推送 · in-flight 已执行）

> **最终态更新（2026-11-23，配置经理按 B-040 同步，原结果未改动）**
>
> 本包的执行结果是 2026-11-20 的 **25 PASS / 1 FAIL**（失败项 PB-B13-AC2，缺陷 D-001）。下文「以当前 25/1 为准」指本包当时的状态，**已被 B-040 取代**：
> [B-040 缺陷记录](../B-040-验收执行/defect-log.md)记录 D-001 已关闭——R1 的 PR #36 增加了受控测试（在提交前暂停，用真实 HTTP 与真实锁），
> R2 于 2026-11-23 在 `develop@ebe3f32` 和独立 MySQL 库 `oxstore_test_d001` 重跑该测试，2 项通过；判定依据是 B-000 §8
> 「锁后加购串行至提交之后，新增量保留」，余数按**同商品最终数量**判定，不要求沿用旧 `cartItemId`。按 B-040 口径，**B-032 的最终结果为 26 / 26**。
>
> 请注意两点：① 本包原先把 D-001 定性为「契约冲突」（确认摘要绑定购物车数量，余数结构性为 0），B-040 改用上述口径后才判通过，这是 AC 解读的变化；
> ② 该复验是重跑 R1 编写的测试，不是只经公开接口的黑盒观察。证据见 [B-037 evidence/d001](../B-037-验收执行/evidence/d001/) 与
> [results-main.json](../B-037-验收执行/evidence/results-main.json)。本包的 `results.json`、`results.md`、`GAP-12.md`、`INDEPENDENT-REVIEW.md` 仍是 11-20 的原始记录，**没有重跑**。


本目录对应分支 `cursor/b032-checkout-atomicity-392f` 的最终提交 `6d37086`；`3a6c975` 是中间审计提交，不是本包。  
核验模型：**cursor-grok-4.6-high**。最终态已推送，历史提交保留不改写。

证据窗：`evidence/results.json` → `2026-11-20T14:19:31Z` → `14:20:47Z`。

独立重算：26 AC / **25 PASS** / 1 FAIL（余数）/ **0 NOT_EXECUTED** / 149 合取。

PB-B13-AC5 **PASS**。`in_flight_pre_lock_delete_add` 窗口已构成并按观察 **PASS**（禁止 confirm 后串行替代）。

**最终态说明**：历史提交 `69c2e2b` 的 26/26 已被 `ce286c9`/`3a6c975`/`6d37086` 修正，以当前 25/1 为准。D-001 现定性为契约冲突：确认摘要绑定 cart qty，成功时 `confirmation.qty == cart.qty`，余数结构性为 0；B-037 串行复现也只能得到 409/整行保留，无法观察余数。

## 从这里读

| 文件 | 内容 |
|---|---|
| [GAP-12.md](GAP-12.md) | in-flight 窗口 / AC5 判定 / totals |
| [INDEPENDENT-REVIEW.md](INDEPENDENT-REVIEW.md) | 本窗独立重读摘要 |
| [evidence/self-review.json](evidence/self-review.json) | `still_unproven` 仅余数 FAIL |
| [evidence/cases/PB-B13-AC5.json](evidence/cases/PB-B13-AC5.json) | DELETE/ADD 时间线 |
| [evidence/SHA256SUMS.md](evidence/SHA256SUMS.md) | 统一窗内哈希 |
| [SHA256SUMS.md](SHA256SUMS.md) | 同上副本（包根） |
| [evidence/results.json](evidence/results.json) | 统一轮原始结果 |
| [scripts/second_audit_acs.py](scripts/second_audit_acs.py) | `_http_signal_issued` + 竞态 |

本目录即分支内 `docs/iterationB/B-032-验收执行/`。  
交付说明：以本目录 README 与 evidence 为准（早期本地便签未入库）。
