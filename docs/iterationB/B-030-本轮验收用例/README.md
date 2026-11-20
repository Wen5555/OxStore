# B-030 本轮验收材料（打回重写 · 可执行）

旧模板交付（占位步骤 / 机械摘引号 / 仅静态 79 计数）**作废**。本目录为按方法基线重写后的可执行验收材料。

## 范围

- 79 AC 全部语义审查并展开为可直接执行用例（角色/会话/fixture 数值/真实 API/响应·页面·DB 断言/清理）
- 可运行：准备、重置、并发栅栏、自审、代表性演练脚本
- B031–B037 直接执行入口
- **不建**长期回归平台；**不开 PR**；仅 push fork 分支

## 目录

| 路径 | 用途 |
|---|---|
| [00-索引.md](./00-索引.md) | AC ↔ case_id |
| [cases/](./cases/) | 分 PB 可执行用例 |
| [fixtures/catalog.json](./fixtures/catalog.json) | 账号/商品数值与 API 目录 |
| [fixtures/env.example](./fixtures/env.example) | 独立测试环境变量 |
| [scripts/](./scripts/) | prepare / reset / barrier / self_review / dry_run / generator |
| [concurrency/SEQ.md](./concurrency/SEQ.md) | 并发 SEQ + 高风险三例 |
| [execution/B031.md](./execution/B031.md) … [B037.md](./execution/B037.md) | 后续任务执行入口 |
| [review/](./review/) | 纠错清单、自审与演练记录 |
| [runs/](./runs/) | 本地证据（勿提交密钥） |

## 快速命令

```bash
cd docs/iterationB/B-030-本轮验收用例
python3 scripts/self_review.py
python3 scripts/dry_run_representative.py
# 有独立测试环境时：
cp fixtures/env.example runs/.env.local  # 编辑
python3 scripts/prepare_fixtures.py --dry-check
python3 scripts/reset_namespace.py --dry-run
```

## 状态纪律

- 用例默认 **待执行**
- 静态自审通过 ≠ 业务验收通过
- 未跑不标通过；阻塞如实写入 `review/dry-run-log.md`
