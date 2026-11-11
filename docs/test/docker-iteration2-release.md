# OxStore 迭代2 + 拍卖模式 Docker 交付版验证

版本：0.1.0-iteration2-auction-docker.1；日期：2026-11-12（Asia/Shanghai）；负责人：张耀文（R5）。

本版本在 `0.1.0-iteration2-docker.1`（提交 `6b84b68`，仅含挑战需求 A、不含拍卖）之后重新构建，业务源码取自 main `71bcd65`，其中包含个性化需求“拍卖模式”的发布、出价、公开快照、SSE、定时结拍、提醒与中标履约，以及 11-10 的流拍详情、实时状态和字段互斥修复。部署层沿用 `d818dd4` 的两处修复（健康检查改查 `/api/products`、初始密码 51 位）。

## 1. 构建

| 项 | 结果 |
| --- | --- |
| 后端镜像内 `mvn clean verify` | 45 项 JUnit，失败 0、错误 0、跳过 0；Java 17 / Maven 3.9 |
| 前端镜像内 TypeScript/Vite 构建 | 成功，3115 个模块转换；体积提示不影响构建 |
| 镜像 | `oxstore/backend`、`oxstore/frontend`（`0.1.0-iteration2-auction-docker.1`）、`mysql:8.0.46`，linux/amd64；镜像 ID 见包内 `manifest.json` |
| 空库初始化 | `database/schema.sql` 建出十二张表（含 `auction_session`、`auction_bid`、`auction_notification`） |

## 2. 真实容器验证

`scripts/verify_docker_iteration2.py` 在随机命名的独立 Compose 项目、临时端口和全新数据卷中运行，经 Nginx → 后端 → MySQL 调用公开接口，不使用模拟 API，不连接任何已有实例，结束后删除项目和数据卷。拍卖由应用自己的 5 秒定时扫描结拍，脚本不修改时钟、不直接调用扫描。

| 编号 | 检查内容 |
| --- | --- |
| D01～D02 | 三服务健康；仅前端端口发布到本机 |
| D03～D05 | 首页与后台登录路由；二级类目；卖家错误密码被拒、正确登录、未登录访问后台被拒 |
| D06～D07 | 一口价回归：带图片发布并经 Nginx 读取；对一口价商品出价被拒；意向排队、队首交易、成功、买家历史 |
| D08～D09 | 拍卖公开快照；拍卖商品不能提交意向；未登录 401、卖家自出价 403、金额精度 400、低于最小加价 409 |
| D10～D11 | 经 Nginx 的 SSE 收到 snapshot 与 bid 事件（出价后约 2 秒内）；被超越/领先状态、领先者脱敏 |
| D12～D15 | 三个拍卖（成交、失败履约、流拍）由应用自动结拍；中标意向挂接；买家/卖家提醒类型和数量；流拍详情仍可公开读取 |
| D16～D17 | 中标人经既有成功接口完成履约；失败履约时 REQUEUE 被拒（409）、DISCARD 留下 FAILED 历史 |
| D18 | 应用重启并整体重建容器后，拍卖、出价、提醒、历史和上传图片与重启前一致，重复扫描不产生重复提醒 |

结果：19 项检查全部通过，覆盖 16 个方法/路由组合、136 次请求，见 `evidence/container-verification/docker-iteration2-results.json`。从导出的 `images.tar.gz` 重新 `docker load`（先删除本机同名镜像）后，在解压出的独立目录再次运行，同样 19 项通过，见 `evidence/imported-smoke/`。

验证脚本在前几次运行中修正了两处自身问题（共 3 次未通过的中间运行）：拍卖截止时间需晚于当前时间 60 秒以上；一口价商品卖出后，未中选买家的意向历史状态为 FAILED（既有规则）。未发现需要修改业务代码的缺陷。`evidence/container-verification/earlier-attempts/` 保留了这些中间运行记录。

## 3. 范围与限制

- 本轮没有真实浏览器页面验收和录屏；随包 `verify_docker_ui.ps1` 与 `verify_docker_release.py` 针对 0.1.0 基线的单商品流程，不适用于本版本。
- SSE 只验证了经 Nginx 的连接建立、首个快照和出价事件，没有覆盖长时间连接、断线重连、15 秒心跳持续或多实例。
- 容器只验证新库初始化；旧库升级由 V5/V6 的独立 MySQL 验证脚本覆盖（见 `docs/test/auction-database-validation.md`），本轮未在容器里升级任何旧业务库。
- 未执行压力并发、ARM、目标 Linux 服务器、公网 HTTPS。
- 测试用拍卖等待真实结拍，单次运行约 2 分钟。
- 镜像基础标签可能随上游更新，实际使用的镜像以包内 `manifest.json` 为准。
