# B-030 重写纠错清单

相对 `c2b8b61` 旧交付（已撤销完成结论）的逐项纠正。

| # | 旧问题 | 纠正 |
|---|---|---|
| 1 | 步骤为「按 AC 描述合法路径…」「查询 DB 验证不变量」占位 | 每用例改为真实 method/path/header/body、提取字段、逐步 assert、SQL |
| 2 | 机械摘引号：PB-B01-AC1 把「失败」「每笔数量固定为 1」当必须提示 | 归入 **禁止状态/旧规则**；断言 status≠FAILED 且不展示旧文案 |
| 3 | PB-B13-AC1 把禁止中间态「订单已生成但购物车未清理」等当可接受提示 | 归入 **forbidden**；成功仅允许「下单成功」；失败全回滚 |
| 4 | 176 编号 + 静态 PASS 当作合格 | 废除固定 176；以语义拆分为准；自审查占位与禁止文案误用 |
| 5 | 无具体 fixture 数值 | `fixtures/catalog.json`：库存 10/5/1/0、价格 12.50/8.00/…、大整数库存 |
| 6 | 无角色/会话 | 每用例声明 CUSTOMER_A/B、SELLER 与 S-* 会话 |
| 7 | 无准备/清理脚本 | `prepare_fixtures.py` / `reset_namespace.py`（DB 名前置门禁） |
| 8 | 并发仅文字 | `concurrency/SEQ.md` + `barrier_runner.py` 三模式 |
| 9 | B031–B037 无执行入口 | `execution/B031.md`…`B037.md` 含 case/SEQ/命令/证据路径 |
| 10 | 未做可执行性演练 | `dry_run_representative.py` + `review/dry-run-log.md`；未跑不标通过 |
| 11 | 长期回归库倾向 | 仍不建 `tests/regression`；仅本轮验收材料目录 |

## 文案语义规则（全 79 AC 适用）

1. `「」` 出现在「不使用/不再/不存在/不允许…」语境 → **禁止项**，不得写入 required tip。
2. 若文案属于 `fixedMessages` 且为成功/失败提示 → **required**。
3. 「备货完成」「开始发货」「交易完成」「已取消」等 → **UI 状态标签**，不是错误 tip。
4. 不得编造未在契约出现的提示；前端不得替换为无货/缺货/超限/下单历史。

## 相对 625ff10 的追加纠正（本提交）

| # | 问题 | 纠正 |
|---|---|---|
| 12 | cases 含未实现 helper:* | 全部展开 + `run_helper.py`/`helpers_lib.py` |
| 13 | prepare 空 POST / NEEDS_MANUAL | multipart 创建+响应校验；失败 ready=false |
| 14 | 未核实 API→DB | `verify_api_db.py` canary |
| 15 | B032 等悬空 $BASE/$TOK/$CMD_* | `env_from_fixtures.sh` 导出全变量 |
| 16 | 仅 echo 栅栏 | 真实双 curl SEQ-01 + 代表性 API 演练 |
| 17 | reset 外键失败 | 先删 confirmation_item |
| 18 | orderId 字段名 | 使用 data.orderId |
