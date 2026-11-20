# B-030 本轮验收材料（打回重写 · 可执行）

旧模板交付（占位步骤 / 机械摘引号 / 仅静态 79 计数）**作废**。本目录为按方法基线重写后的可执行验收材料。

**勿宣称 B-030 完成**：全量 AC 仍待执行；代表性真实演练 ≠ 验收通过。

## 范围

- 79 AC 语义审查并展开为可直接执行用例（角色/会话/fixture/真实 API/断言/SQL/清理）
- 可运行：prepare / reset / helpers / verify_api_db / barrier / run_representative
- B031–B037 直接执行入口（`env_from_fixtures.sh` 导出变量，禁止手填）
- **不建**长期回归平台；**不开 PR**；仅 push fork 分支

## 被测栈（本轮演练）

优先 **develop** 候选并记录 `B030_SUT_SHA`（例：`29c20ea`）。独立库名必须 `oxstore_b030_*` / `oxstore_test_*`；本轮演练使用 `oxstore_b030_local` + BE `:8080` + FE `:5173`。

## 目录

| 路径 | 用途 |
|---|---|
| [00-索引.md](./00-索引.md) | AC ↔ case_id |
| [cases/](./cases/) | 分 PB 可执行用例（无悬空 helper） |
| [fixtures/](./fixtures/) | catalog / env.example / seed.png / 数据准备 |
| [scripts/](./scripts/) | prepare / reset / helpers / env_from_fixtures / verify_api_db / barrier / run_representative |
| [concurrency/SEQ.md](./concurrency/SEQ.md) | 并发 SEQ + 高风险三例 |
| [execution/B031.md](./execution/B031.md) … [B037.md](./execution/B037.md) | 后续任务执行入口 |
| [review/](./review/) | 纠错、自审、演练证据 |
| [runs/](./runs/) | 本地密钥与原始输出（gitignore） |

## 快速命令

```bash
cd docs/iterationB/B-030-本轮验收用例
cp fixtures/env.example runs/.env.local   # 编辑 DB/密码/SUT SHA
set -a; source runs/.env.local; set +a
python3 scripts/self_review.py
python3 scripts/prepare_fixtures.py       # 必须 ready=true
source scripts/env_from_fixtures.sh
python3 scripts/verify_api_db.py
python3 scripts/run_representative.py
```

## 状态纪律

- 用例默认 **待执行**
- 静态自审通过 ≠ 业务验收通过
- 未跑不标通过；阻塞如实写入 `review/dry-run-log.md`
