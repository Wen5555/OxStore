# B-032 in-flight 锁前 DELETE/ADD（本窗执行）

核验模型：**cursor-grok-4.6-high**  
Git：历史执行窗内未提交；最终态由 `6d37086` 推送（不改写历史）。  
远端最终提交 `6d37086`；`3a6c975` 为中间审计提交。  
证据窗：`evidence/results.json` `execution_window` **2026-11-20T14:19:31Z → 14:20:47Z**（SGT 22:19:31–22:20:47）  
独立重算：26 AC / **25 PASS / 1 FAIL / 0 NOT_EXECUTED** / 149 合取 / 0 占位。

**禁止 confirm 后串行替代 in-flight。已闭合项未推翻。余数 FAIL 保留。V8 / 三断点未推翻。**

---

## PB-B13-AC5 与 in-flight

| 项 | 结论 |
|---|---|
| 窗口是否构成 | **构成**（DELETE attempt 2、ADD attempt 32；均 `window.hit=true`） |
| `in_flight_pre_lock_delete_add` | **PASS**（`disposition_if_fail=FAIL`，非 skip） |
| PB-B13-AC5 整 AC | **PASS**（11/11 合取） |
| 锁前串行 | 仍单独合取 `lock_before_patch_delete_add_serial_rejects` **PASS**，`not_in_flight=true`，`serial=true`；**未**拿来顶替 in-flight |

判定口径（脚本 `_in_flight_pre_lock_once`）：submit HTTP 字节已发出（`issued` 在 `endheaders`+`send` 之后）且 mutation 2xx 在 `submit_end` 前结束、耗时 &lt;0.5s（未等待 checkout 的 customer FOR UPDATE / after_stock hold）。

本窗观察（非串行）：

- **DELETE** attempt 2：issued ≤ mut_start；mut_dur=0.00492s；mut HTTP 200「已移除」；submit HTTP 409「所选商品无法下单」；orders=0。pre-lock DELETE 进入本次校验。
- **ADD** attempt 32：issued ≤ mut_start；mut_dur=0.00501s；mut HTTP 200「已加入购物车」；submit HTTP 409「确认信息已变化，请重新确认」；cart qty=2；orders=0。digest 含 qty，pre-lock ADD 进入本次校验。
- `not_serial_before_submit=true`。submit 409 + 无单，排除 post-commit 误命中。

证据：`evidence/cases/PB-B13-AC5.json` 合取 `in_flight_pre_lock_delete_add`。

锁后（during_hold，未推翻）：DELETE 201+1 单+qty=1；ADD 余量 qty=1 且订单 qty=1。

---

## 本窗 totals（独立重算 `results[]` + `conjunct_table`）

- PASS 25 / FAIL 1 / BLOCKED 0 / NOT_EXECUTED 0 / total 26
- 唯一 FAIL：`PB-B13-AC2` 合取 `remainder_gt0_via_public_api`
- 唯一 still_unproven：余数 FAIL（in-flight 已从 `still_unproven` 去掉）

---

## 未推翻

- B03-AC3 商家 GET page=2：ids `745,744` / `743,742`，overlap `[]`，total=7
- B12-AC6 UI 确认后 submit；B03-AC5 真实意图入口；B12-AC3 行级勾选；B03-AC3 取消详情 UI；B03-AC2 图片不可改
- 锁前串行合取；V8 `upgrade_oxstore_v8`；三断点 `breakpoint_after_*_rollback_and_probe`

---

## 仍未证实

- **余数** `PB-B13-AC2 remainder_gt0_via_public_api`（FAIL，digest 含 qty；保留）
