# B-040 缺陷记录

## 当前状态：0 个开放缺陷

| ID | AC | 严重度 | 责任 | 状态 |
|---|---|---|---|---|
| D-001 | PB-B13-AC2 | 阻断（原） | B-011 / R1 | **CLOSED** |
| D-002 | PB-B09-AC1 | 阻断（原） | R3 / B-019 | **CLOSED** |
| B08-AC1 | PB-B08-AC1 | 测试材料 | B-031 / R2 | **CLOSED（改判）** |

## D-001 · PB-B13-AC2 锁后加购（CLOSED）

| 项 | 内容 |
|---|---|
| 原问题 | B-032 无法通过公开 API 观察「锁定后加购保留余数」；B-037 串行改量得到 409 |
| 修复 | PR #36 / `topic/r1`，commit `d5bed99`：新增受控测试 `ChallengeBCheckoutPublicApiConcurrencyTest`，在 `ShopOrderRepository.saveAndFlush` 前暂停，真实 HTTP + 真实锁；无生产代码改动 |
| R2 复验 | 2026-11-23，`develop@ebe3f32`，MySQL 8.0 `oxstore_test_d001`（空库 schema），`mvn -Dtest=ChallengeBCheckoutPublicApiConcurrencyTest test` → **Tests run: 2, Failures: 0, Errors: 0**，BUILD SUCCESS |
| 观察 | 锁后加购进入服务并等待：提交 201、订单 qty=2、同商品新行 qty=1、库存 3；原键重试 40909。锁前改量：409/40913、无订单、车内 3 件、库存 5 |
| 判定依据 | B-000 §8「锁后加购串行至提交之后，新增量保留」；不要求沿用旧 `cartItemId`，余数按同商品最终数量判定 |
| 证据 | [B-037 evidence/d001](../B-037-验收执行/evidence/d001/)、`evidence/results-main.json` |

## D-002 · PB-B09-AC1 失效收藏点击提示（CLOSED）

| 项 | 内容 |
|---|---|
| 原问题 | B-031 判 FAIL：真实页面点击失效收藏无「已下架」提示（源码仅无点击处理的 `<span>`） |
| 修复 | PR #35 / `topic/r3`，commit `4e10352`：失效项改为可点击 span，点击 `message.warning(已下架)`，并补 Tooltip/键盘可访问 |
| R2 复验 | 2026-11-23，`develop@ebe3f32` + 真实 Chrome：点击失效行 → toast `["已下架"]`，URL 保持 `/me/favorites` |
| 证据 | [B-036 d002-ui-retest.json](../B-036-验收执行/evidence/d002-ui-retest.json)、`evidence/screenshots/15-d002-invalid-favorite-notice.png` |

## B08-AC1 · 测试期望错误（CLOSED）

- B-031 原判 FAIL：脚本期望商家「无此权限」，实际「角色无权访问」(40301)。
- AC 只要求商家不可访问客户收藏；B-037 `B08-AC1-REVERIFY` 5/5 PASS。
- B-031 已改判 PASS，原始 FAIL 观察保留在 `verdict_original`/`rejudge_reason`。

## 历史记录

- 2026-11-21：B-040 首轮结论 78/79，D-001 开放。
- 2026-11-22：复核 B-031/B-032 材料，发现 D-002（B09-AC1 UI）与 B-032 材料问题；B-040 口径修正为 77/79。
- 2026-11-23：PR #35/#36 合并；R2 复验 D-001/D-002 均通过，79/79。
