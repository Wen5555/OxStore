# B-032 in-flight 执行 — 本地未提交

- **模型：** cursor-grok-4.6-high
- **对象：** 工作区未提交文件，**不是** tip `3a6c975`
- **Git：** 未 commit / push / amend
- **窗口：** UTC `2026-11-20T14:19:31Z` → `14:20:47Z`

## 独立重算

26 AC / 25 PASS / 1 FAIL / 0 NOT_EXECUTED / 149 合取 / 0 占位。

## AC5 与 in-flight

- 窗口 **构成**（DELETE attempt 2、ADD attempt 32）。
- `in_flight_pre_lock_delete_add` **PASS**：DELETE 200 + submit 409 + 0 单；ADD 200 + submit 409 digest + cart qty 2。
- 整 AC **PB-B13-AC5 PASS**。
- 锁前串行合取仍独立 PASS，`not_in_flight=true`；**未**用作 in-flight 替代。

## 仍未证实

- `PB-B13-AC2 remainder_gt0_via_public_api` FAIL（保留）
