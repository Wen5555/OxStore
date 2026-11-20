# B-032 本地核验包（未推送 · in-flight 已执行）

本目录是**当前工作区**副本，不是远端 tip `3a6c975`。  
核验模型：**cursor-grok-4.6-high**。禁止 git commit/push/amend/rebase/reset/force。

证据窗：`evidence/results.json` → `2026-11-20T14:19:31Z` → `14:20:47Z`。

独立重算：26 AC / **25 PASS** / 1 FAIL（余数）/ **0 NOT_EXECUTED** / 149 合取。

PB-B13-AC5 **PASS**。`in_flight_pre_lock_delete_add` 窗口已构成并按观察 **PASS**（禁止 confirm 后串行替代）。

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

工作区同源：`/workspace/docs/iterationB/B-032-验收执行/`。  
交付：`/cursor/stores/self/docs/b032-round-delivery.md`（**未推送**）。
