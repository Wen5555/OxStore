# B-034 独立验收包 · 转收藏（PB-B14 ×7 + PB-B15 ×6）

> 结论（2026-11-21，SUT `develop@29c20ea`）：**13 AC / 13 通过 / 0 失败 / 0 阻塞，63 个合取**；
> 其中 PB-B14-AC4 的 UI 二次确认文案 1 个合取**转 B-036 真实页面**验证，API+DB 部分已通过。
>
> 本目录执行的是 **B-030 已冻结的方案**（cases/PB-B14.md、PB-B15.md、concurrency/SEQ.md），
> 不重新定义 AC、不改写预期文案；只补 AC 专属断言与证据归档。

## 被测对象

| 项 | 值 |
|---|---|
| SUT | `develop@29c20ea0927528a98f873f4a1a0e169a6fa12281` |
| 交付基线 | `topic/r2@0cef9ec`（文档分支 `cursor/b030-acceptance-cases-392f`） |
| 后端 | Spring Boot `:8080`（本机 jar 启动） |
| 数据库 | MySQL 8.0 `oxstore_test_b034`（隔离库，不复用 shop） |
| 前端 | 未启动；UI 项见下 |

## 结果

| 证据 | 内容 |
|---|---|
| [evidence/results.json](./evidence/results.json) | 执行窗口、SUT、DB、13 AC 汇总、合取数 |
| [evidence/results.md](./evidence/results.md) | 人读结果表与失败合取（本次为空） |
| [evidence/cases/](./evidence/cases/) | 每个 AC 的合取明细（HTTP 响应 + DB 快照，JWT 已脱敏） |
| [acs-13.json](./acs-13.json) | AC ↔ B-030 用例 ↔ 合取清单 |

## 目录结构

| 路径 | 用途 |
|---|---|
| `scripts/b034_common.py` | 复用 B-030 的 env/fixture/HTTP/DB 契约；隔离库与命名空间护栏 |
| `scripts/run_acs.py` | 13 AC 可执行入口（每 AC 前 reset 命名空间，逐合取断言） |
| `fixtures/env.example` | 本地 env 模板（真实值放 `runs/.env.local`，已 gitignore） |
| `evidence/` | 运行证据（脚本生成，不手填） |
| `runs/` | 本地密钥与原始日志（gitignore） |

## 复现

```powershell
# 1) 起被测后端（隔离库，首次需导入 schema.sql 并建 admin）
#    DB_NAME=oxstore_test_b034；JWT_SECRET/ADMIN_INITIAL_PASSWORD 自定
# 2) 准备 B-030 fixtures（建 B030-* 商品与 b030_* 客户）
cd docs/iterationB/B-030-本轮验收用例
python scripts/prepare_fixtures.py          # 要求 ready=true
# 3) 执行 B-034
cd ../B-034-验收执行
python scripts/run_acs.py                   # 退出码 0 = 无 FAIL/BLOCKED
```

`scripts/run_acs.py --only PB-B14-AC1` 可单跑一条 AC。

## 判定口径（与 B-030 一致）

- 每条 AC 由多个**合取**组成；任一合取失败即 `FAIL`，setup 异常为 `BLOCKED`；
- 只有实际发出的 HTTP 响应与 DB 前后快照都纳入证据，未执行不标通过；
- 并发用线程栅栏同时发起两请求（`race()`），只接受 AC 允许的终态组合，出现半成功即 FAIL；
- “不存在商品”用例在隔离库内用 `FOREIGN_KEY_CHECKS=0` 单行改写模拟（系统无硬删除），
  用后立即删除该行；已在 `b034_common.py` 注释说明；
- UI 文案/可勾选性属真实页面范畴，API 只能证明服务端拒绝与回滚，故 AC4 的 UI 合取显式
  `DEFER_TO_B036`，不计入本轮通过。

## 执行中确认的两个环境事实（写进证据，避免后续误判）

1. `B-030/scripts/reset_namespace.py` 按 `;` 切分后跳过“首行是注释”的语句，导致商品恢复
   UPDATE 实际从未执行（脚本仍打印 PASS）。B-034 在自己的 `reset()` 中先剥离注释行再执行，
   已修正；B-030 原文未改动，供 B-040 汇总时决定是否回修。
2. `operation_receipt` 同表记录 `CART_ADD` 与 `MOVE_TO_FAVORITES` 两类回执。B15-AC2/AC5 的
   “只处理一次”必须只统计 `MOVE_TO_FAVORITES`，否则会被加购回执干扰（首轮即因此误报 2 条，
   修正后通过）。

## 与相邻任务的边界

- B-031：收藏/购物车接口与多端（PB-B08～B11）——本包不重复其 21 AC；
- B-032：结算原子性（PB-B01～B03、B12、B13）——本包不重复其 26 AC；
- B-036：真实前后端 V01～V09 页面与主链路——承接本包 AC4 的 UI 二次确认文案；
- B-037：固定提示、持久化与安全负例——本包的消息原文可直接作为输入，但持久化/重启项由其覆盖。
