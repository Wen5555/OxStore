# B-037 验收执行结果（固定提示 / 持久化 / 安全负例 + 3 条失败 AC 复验）

- 执行窗口：2026-11-21T14:43:06Z → 2026-11-21T14:44:58Z
- SUT：`develop@29c20ea0927528a98f873f4a1a0e169a6fa12281`；DB：`oxstore_test_b037`；BASE：http://127.0.0.1:8083

| 检查 | 状态 | 合取 | 失败合取 |
|---|---|---|---|
| FIXED-PROMPTS | **PASS** | 26 | — |
| B08-AC1-REVERIFY | **PASS** | 5 | — |
| B09-AC1-REVERIFY | **PASS** | 4 | — |
| B13-AC2-REVERIFY | **FAIL** | 1 | remainder_observable_via_public_api |
| PERSISTENCE-SETUP | **PASS** | 1 | — |
| PERSISTENCE-RESTART | **PASS** | 5 | — |

合计：6 检查 / **5 通过** / 1 失败 / 0 阻塞；合取 42 个。

## 未通过项

- `B13-AC2-REVERIFY` / `remainder_observable_via_public_api`：期望 order qty < cart qty with a kept remainder line
  - 实际：{"submit": 409, "order_qty": null, "cart_left": ["3", "2"], "note": "B-032 已判 FAIL（remainder_gt0_via_public_api）；本轮用公开 API 串行/并发重试"}
