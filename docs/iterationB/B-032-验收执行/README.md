# B-032 核验包（最终态已推送 · in-flight 已执行）

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
