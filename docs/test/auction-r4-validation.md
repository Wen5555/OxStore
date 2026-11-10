# R4 拍卖与一口价回归验收记录

- 日期：2026-11-09（Asia/Shanghai）
- 工作分支：`feature/r4-completion`
- 基线提交：`04a90811f7f430ef8c2c9fccd77eaff0f600339e`
- 范围：P-A17～P-A20。测试使用 H2、模拟 API 和 Compose 配置校验；没有连接或改动真实业务数据库。

## 验证矩阵

| Task | 验收点 | 结果 | 证据 |
| --- | --- | --- | --- |
| P-A17 | 一口价商品默认 `FIXED_PRICE`；拒绝拍卖快照和出价；原意向队列、成交与 SUCCESS 历史正常 | 通过 | `Iteration2ApiIntegrationTest.fixedPriceProductsKeepTheIntentFlowAndRejectAuctionOperations` |
| P-A18 | 普通商品页面仍显示购买意向、不请求拍卖快照；购买历史的终态展示保持原行为 | 通过 | Playwright 一口价回归与购买历史用例 |
| P-A19 | 拍卖竞价、领先者变化及结拍 SSE；成功履约；失败时拒绝重新排队、下架商品并记录 FAILED 历史 | 自动化通过 | H2 HTTP/SSE 集成测试覆盖失败 API 和状态；真实 MySQL 专项脚本也加入 W03/W04 检查，待 Docker 可用后执行 |
| P-A20 | 后端构建测试、前端构建/交互测试、Compose 配置检查及本报告 | 自动化部分通过 | 下方运行记录 |
| P-A20 | Docker 实际启动、V6 MySQL 迁移与部署运行验收 | 未执行 | 本机 Docker Desktop Linux Engine 管道不可用；须在 Docker 可用环境补测 |

## 本次执行记录

| 命令/步骤 | 结果 |
| --- | --- |
| `mvn -B -ntp -f backend/pom.xml clean verify` | `BUILD SUCCESS`；39 项测试，0 失败、0 错误、0 跳过；其中 `Iteration2ApiIntegrationTest` 7/7 通过，包含拍卖失败履约及 REQUEUE 拒绝验收 |
| `npm.cmd ci --no-audit --no-fund`（`frontend/`） | 成功，按锁文件安装 165 个依赖包 |
| `npm.cmd run build`（`frontend/`） | 成功；TypeScript 与 Vite 构建通过。Vite 对大于 500 kB 的 bundle 给出既有体积警告，不影响构建 |
| `npm.cmd run test:e2e`（`frontend/`） | 8/8 Playwright 测试通过 |
| `docker compose config --quiet`（提供 CI 占位环境变量） | 通过 |
| `docker info`（启动 Docker Desktop 后重试） | 失败：Linux Engine 返回 HTTP 500；`docker desktop status` 仍为 `stopped`，因此没有声称容器已部署或 V6 已实测 |

后端 Surefire 结果位于构建目录 `backend/target/surefire-reports/`；Playwright 的本地结果位于 `frontend/test-results/`。这些是可由上述命令重建的临时输出，不随源码报告提交。

## 完成真实 MySQL 联调

`scripts/verify_auction_database.py` 使用一次性 MySQL 8 容器和临时数据库，不连接项目已有或业务数据库。脚本验证空库 schema、V6 升级/重复执行/恢复、Hibernate `ddl-auto=validate`、API 竞价与成功履约、数据库重启；W03/W04 另通过已有履约 API 验证失败分支：

- `REQUEUE` 应返回 HTTP 409，且意向仍为 `IN_TRANSACTION`、商品仍为 `FROZEN`，不得产生失败历史。
- `DISCARD` 应成功；拍卖商品库存保持 1、状态转为 `OFFLINE`，意向和交易尝试为 `FAILED`，失败动作为 `DISCARD`，并写入 `FAILED` 购买历史及 `TRADE_FAILED` 事件。

Windows PowerShell 执行：

```powershell
# 先启动 Docker Desktop，并等待此命令成功
docker info

# 在仓库根目录构建可供 MySQL 验证器启动的后端 JAR
mvn -B -ntp -f backend/pom.xml clean verify

# 对隔离的一次性 MySQL 执行联调，并保存机器可读结果
python -X utf8 scripts/verify_auction_database.py --output docs/test/evidence/r4-auction-mysql-results.json
```

以脚本退出码 0 且结果 JSON 中 `"success": true`、各项 `passed` 为验收通过；非零退出码或清理失败都需先处理并重跑。脚本会自动清理本次创建的容器；禁止把连接参数改成真实业务库。当前环境 Docker Desktop 的 Linux Engine 返回 HTTP 500 且状态为 `stopped`，因此这项仍待实际执行。

## Sprint Review 摘要

- 一口价与拍卖的 API/页面入口保持隔离；拍卖出价不进入普通购买意向队列。
- 竞价、结拍 SSE 更新与既有中标交易履约路径已在自动化范围内验证。
- 发现并修正一个前端状态问题：收到结拍事件后需更新 `canBid` 与 `myStatus`，避免界面仍允许出价或未显示中标/未中标结果。
- Compose 静态配置通过，但实际容器启动、迁移和浏览器访问待 Docker Engine 可用后验证。

## 回顾与后续行动

- 自动化 API/SSE 与 Playwright 场景可在本机重复执行，降低了手工验收对并发和结拍时序的依赖。
- 后续 CI 已加入 Playwright Chrome 安装及前端 E2E 步骤；合并前须检查 GitHub Actions 的真实运行结果。
- 在独立 MySQL 上执行 `scripts/verify_auction_database.py`，并在隔离数据卷完成 compose 启动、健康检查、关键买家/卖家流程和日志归档。
- 以上为基于本次验证的书面 Review/回顾记录；真实 Sprint Review/Retro 会议、PR 链接及最终提交 SHA 尚未生成，不应以本记录代填或虚构。

## PR 与提交信息

- PR：尚未创建。
- 最终提交 SHA：尚未生成；以上 SHA 是本次工作分支的基线提交。
- 后续创建 PR 时附上 GitHub Actions 运行链接、独立 Docker/MySQL 验证结果和最终提交 SHA。
