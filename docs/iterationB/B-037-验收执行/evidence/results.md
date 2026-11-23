# B-037 验收执行结果（固定提示 / 持久化 / 安全负例 + D-001/D-002 复验）

- 原始执行：2026-11-21T14:43:06Z → 2026-11-21T14:44:58Z（SUT `29c20ea`）
- D-001 受控复验：2026-11-23，SUT `develop@ebe3f32`，MySQL `oxstore_test_d001`
- DB：`oxstore_test_b037`；BASE：http://127.0.0.1:8083

| 检查 | 状态 | 合取 | 失败合取 |
|---|---|---|---|
| FIXED-PROMPTS | **PASS** | 26 | — |
| B08-AC1-REVERIFY | **PASS** | 5 | — |
| B09-AC1-REVERIFY | **PASS** | 4 | — |
| B13-AC2-CONTROLLED | **PASS** | 7 | — |
| PERSISTENCE-SETUP | **PASS** | 1 | — |
| PERSISTENCE-RESTART | **PASS** | 5 | — |

合计：6 检查 / **6 通过** / 0 失败 / 0 阻塞；合取 48 个。

## D-001（PB-B13-AC2）受控复验

- 命令：`mvn -B -Dtest=ChallengeBCheckoutPublicApiConcurrencyTest test`（MySQL `oxstore_test_d001`）。
- 结果：2 个用例全部通过；锁后加购在服务端已持锁时进入并等待，提交 201、订单 qty=2、同商品新行 qty=1、库存 3、原键重试 40909；锁前改量对照返回 409/40913、无订单、车内 3 件。
- 依据：B-000 §8「锁后加购串行至提交之后，新增量保留」，不要求沿用旧 cartItemId；D-001 关闭。
- 证据：`evidence/d001/`（两个 JSON + surefire XML）。
