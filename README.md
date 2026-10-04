# OxStore（单卖家、单商品 MVP）

Java 17 / Spring Boot 3.2 / JPA / MySQL 8，前端 React + TypeScript。买家匿名排队，卖家以 JWT 管理商品与线下交易。

## 首次建库与运行

1. 复制 `.env.example` 为 **不提交版本库**的 `.env`；设置独立的 `DB_PASSWORD`、`JWT_SECRET`、`TOKEN_LOOKUP_KEY` 和首次建号用的 `ADMIN_INITIAL_PASSWORD`。分别用 `openssl rand -hex 32` 生成 JWT 与口令索引密钥；管理员密码须为 8–64 位且含字母、数字和特殊字符。旧公开的初始密码及 JWT 密钥均不能继续使用。
2. Docker：`docker compose up --build`。空 MySQL 卷自动执行 `backend/src/main/resources/db/schema.sql`。卖家用户名仍为 `admin`，密码由首次配置决定。
3. 本地运行：先新建 UTF8MB4 的 MySQL `shop` 库并执行同一个 `schema.sql`，导出 `DB_HOST/DB_PORT/DB_NAME/DB_USERNAME/DB_PASSWORD/JWT_SECRET/TOKEN_LOOKUP_KEY/ADMIN_INITIAL_PASSWORD`（已有账号时可不设置初始密码），再在 `backend/` 运行 `./mvnw spring-boot:run`；前端在 `frontend/` 运行 `npm install && npm run dev`。业务时区为 **Asia/Shanghai**，数据库/应用环境的 `TZ` 也保持一致。

首次创建 `admin` 后，即使删除 `ADMIN_INITIAL_PASSWORD` 再启动也不会重置已有密码。请登录后立即改密。更换 `JWT_SECRET` 会使旧 JWT 失效；更换它**不会**自动更改卖家密码。已用旧公开密钥/默认密码部署的实例必须两者都换。不要把真实密钥或密码写入仓库/日志。

`TOKEN_LOOKUP_KEY` 用于 HMAC 索引新买家口令，**不得跟随 JWT 密钥一起轮换**：只要还有有效买家口令，就必须保留原口令索引密钥及其备份，否则新口令的索引查找将失效。数据库仍存 BCrypt 哈希进行验证，不返回索引摘要给客户端。

### 现有数据升级

**禁止将空库 `schema.sql` 当成旧表升级脚本**：已有 MySQL 卷不会重新执行 Docker 初始化。暂停业务写入，备份数据，在副本上演练 `backend/src/main/resources/db/migrations/V2__queue_history.sql`，先结束全部 `IN_TRANSACTION` 意向（脚本会阻止带交易升级）；再以 MySQL 命令行一次性执行，核对迁移前后行数、状态分布、序号无空/无重复及新表约束。若中途失败，不要盲目重跑；[MySQL DDL 会隐式提交](https://dev.mysql.com/doc/refman/8.0/en/implicit-commit.html)。

旧行以迁移时 `submitted_at` 值排序回填 `queue_seq`；曾被旧版 REQUEUE 覆盖的原始时间、此前失败交易及手动操作历史**不能恢复**。设置 `HISTORY_COMPLETE_SINCE=升级截止时间`（格式如 `2026-10-01T10:00:00`），后台记录接口会返回 `legacyRecordsMayBeIncomplete=true` 与该截止时间。迁移后的新交易必有开始时间。不能把旧应用直接回退后继续写入，否则又会覆盖首次提交时间且不写新历史；必要时停写并从备份恢复。

若 V2 仅在前置检查被交易中意向拦截，且确认还未执行任何表变更，可在结束交易后重试修订后的 V2；脚本会清理遗留的辅助过程并重新检查。其他中途失败仍须先核对结构，不能盲目重跑。已经执行旧版 V2 的实例另用 `V3__trade_attempt_completion_check.sql` 收紧交易结果非空约束；脚本遇到不完整旧记录会拒绝升级，须核实真实结果后处理，不自动补造历史。新库或修订后的 V2 无须额外执行 V3。

旧口令的 `token_lookup` 保持 `NULL`，继续按原 BCrypt 全量比对，不会因迁移失效；**若同一商品仍有大量旧有效码，该兼容回退路径可能超过 2 秒**。待旧商品正常成交/口令自然失效后，新口令走索引查询。不要为追求速度强制清除旧口令。

## 新增/变更 API 与记录权限

- `GET /api/admin/products/{id}/records`：商品任意业务状态均可读 `product/intents/tradeAttempts/statusEvents/legacyRecordsMayBeIncomplete/historyCompleteSince`；不存在为 404。`GET /api/admin/products/history/{id}` 仍只支持 `SOLD`，但返回相同结构。`GET /api/admin/intents` 仍仅是当前交易中及排队队列，排队位置从 1 起。
- `ProductResponse` 新增 `statusUpdatedAt`。`IntentResponse` 新增 `processedAt`（**最近一次意向状态处理时间**）和 `currentTradeAttemptId`（仅后台队列中的交易中意向及失败自动递补响应有值）。`submittedAt` 是首次提交时间；`queueSeq` 仅内部排序，不等于动态位次。
- `POST /api/admin/intents/{id}/start` 保持原请求与空响应；随后刷新队列取得 `currentTradeAttemptId`。成功确认须发送 `{ "tradeAttemptId": 12 }`；失败确认须发送 `{ "action": "REQUEUE", "tradeAttemptId": 12 }`（或 `DISCARD`）。缺字段返回 400；重复/延迟的旧尝试 ID 返回 409，须刷新队列；失败响应的 `data` 为新的交易中意向或 `null`。
- 成功商品为 `SOLD`，`soldAt` 是成交时间；意向 `SUCCESS/FAILED/CANCELLED/UNSOLD` 为最终状态。一个意向可有多次尝试，早先的失败只在 `tradeAttempts` 列表中展示；未结束尝试的 `finishedAt/result/failAction` 为 `null`。事件按时间及 ID 排序，同一事务内失败恢复在售和再冻结分别记录。
- 输入电话遵循 V1：**恰好 11 位数字**，不限定 1 开头。公开商品接口不返回买家数据；意向及尝试/事件记录仅后台可读；买家凭码仅可查本人。

前端已提交队列及历史页面实现；完整页面联调与UI验收仍需R3/R4核验。

### 重排口令规则（2026-10-04对齐）

按课程第11组9月28日澄清，口令跟随意向：失败后选择`REQUEUE`保留原口令，可继续查询，排队时可修改或撤销；`DISCARD`、主动撤销、成交和商品售出使对应口令失效。重排只改变`queue_seq`，首次`submitted_at`保持不变。

## 测试与注意事项

后端：`cd backend && ./mvnw test`；前端：`cd frontend && npm run build`。本机曾在独立 MySQL 8 测试库跑锁等待并发、回滚、迁移及保留卷重启；真实目标部署环境仍须复验。接口仅能读取并不等于页面或全量性能达标。发布失败后尝试清理孤儿图片；已售商品的裸图片 URL 是否也要禁止买家访问属于待确认的需求解释问题，不能假定当前实现已经满足。

业务状态变更以现有 Service 事务为边界，商品行锁作为卖家操作和提交意向的串行化点；参考 [Spring Data JPA 锁说明](https://docs.spring.io/spring-data/jpa/reference/jpa/locking.html)与[事务说明](https://docs.spring.io/spring-data/jpa/reference/jpa/transactions.html)。

## R5数据库交付

- [数据库设计、ER图与建库/迁移说明](docs/design/database.md)
- [数据库验证报告与复现方法](docs/test/db-validation.md)
- [R5个人成果说明](docs/personal/R5.md)

在`backend`运行`mvn test package`后，在项目根目录执行`python scripts/verify_database.py`。脚本需要Docker和Java17，自动创建独立MySQL8容器，生成无凭据的验证记录，结束后清理本次专用容器。它不会连接现有业务库。
