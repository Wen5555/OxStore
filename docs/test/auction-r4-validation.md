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
| P-A19 | 拍卖竞价、领先者变化及结拍 SSE；获胜者/卖家提醒、拍卖记录、中标意向履约和历史留痕 | 通过 | H2 + HTTP/SSE 集成测试；买家拍卖提醒 SSE 浏览器用例 |
| P-A20 | 后端构建测试、前端构建/交互测试、Compose 配置检查及本报告 | 自动化部分通过 | 下方运行记录 |
| P-A20 | Docker 实际启动、V6 MySQL 迁移与部署运行验收 | 未执行 | 本机 Docker Desktop Linux Engine 管道不可用；须在 Docker 可用环境补测 |

## 本次执行记录

| 命令/步骤 | 结果 |
| --- | --- |
| `mvn -B -ntp -f backend/pom.xml clean verify` | `BUILD SUCCESS`；38 项测试，0 失败、0 错误、0 跳过；其中 `Iteration2ApiIntegrationTest` 6/6 通过 |
| `npm.cmd ci --no-audit --no-fund`（`frontend/`） | 成功，按锁文件安装 165 个依赖包 |
| `npm.cmd run build`（`frontend/`） | 成功；TypeScript 与 Vite 构建通过。Vite 对大于 500 kB 的 bundle 给出既有体积警告，不影响构建 |
| `npm.cmd run test:e2e`（`frontend/`） | 8/8 Playwright 测试通过 |
| `docker compose config --quiet`（提供 CI 占位环境变量） | 通过 |
| `docker version --format '{{.Server.Version}}'` | 失败：找不到 `dockerDesktopLinuxEngine` 管道，Docker 服务端不可用；因此没有声称容器已部署或 V6 已实测 |

后端 Surefire 结果位于构建目录 `backend/target/surefire-reports/`；Playwright 的本地结果位于 `frontend/test-results/`。这些是可由上述命令重建的临时输出，不随源码报告提交。

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
