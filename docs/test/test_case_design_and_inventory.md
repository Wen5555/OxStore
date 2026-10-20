# OxStore 测试用例设计及清单

更新日期：2026-10-20。本文档以当前接口、测试源码和自动化测试资产为依据，按需求和验证入口说明覆盖范围。测试条数不等同于需求覆盖率；执行结果以对应的测试报告和退出码为准。命令与环境准备见[自动化测试执行手册](automation_runbook.md)。

## 1. 范围与判定

测试资产分为后端 JUnit、真实容器/API 验证、数据库专项验证、前端模拟 API 交互、真实浏览器 Selenium 冒烟及 JMeter 性能/并发验证。

- 后端当前有 11 个测试类、50 个 JUnit 测试方法；以当前源码的 `@Test` 方法统计，执行结果须以 Surefire XML 为准。
- `scripts/verify_docker_release.py` 通过 Nginx 调用真实 Java/MySQL 服务，执行容器和 API 场景；覆盖计数以该次运行输出为准。
- `scripts/verify_database.py` 使用隔离数据库验证表结构、约束、迁移、交易记录和持久化。
- `frontend/e2e/buyer-seller-flows.spec.ts` 使用模拟 API 验证前端交互，不等同于真实服务端到端验证。
- Selenium 用例 UI-001 使用真实 Chrome 和运行中的前后端，已完成并通过一条业务闭环；完整 UI 失败路径与页面覆盖仍待补。
- 性能及并发测试使用 JMeter；测试结果和具体负载条件见项目 `outputs/` 下相应报告。写入型场景只能在隔离测试库运行。
- 人工录屏不由自动化测试代替；是否完成以实际交付的视频证据为准。

## 2. 功能与自动化对应

需求编号使用 Wiki《需求规格说明书V1》的 B/S 用例编号。

| 用例 | 功能与预期 | 自动化入口与检查点 |
| --- | --- | --- |
| B-001～B-003 | 展示在售/冻结商品；无商品时返回空数据并提示 | 容器 D04、D08、D10、D18；前端页面显示另行核对 |
| B-004 | 姓名/电话有效且商品可售时成功排队，返回个人口令与位次 | 容器 D12、D13、D26；冻结期间拒绝新增 |
| B-005 | 原码查询本人状态、重排后仍可查询；终态与无效码拒绝 | 容器 D13、D14、D16、D18、D24、D25 |
| B-006 | 排队中修改姓名和电话，位次不变；交易中拒绝修改 | 容器 D14、D15 |
| B-007 | 排队中撤销后退出，原码失效；交易中拒绝撤销 | 容器 D14、D15 |
| S-001 | 登录成功取得 JWT；错误密码和未登录访问拒绝 | 容器 D05、D06、D20；Selenium UI-001 检查错误密码与成功登录 |
| S-002 | 修改密码后旧密码失效，新密码与重启后记录保留 | 容器 D20、D21 |
| S-003 | 发布商品及主图；拒绝第二件活跃商品和超限图片 | 容器 D07～D09；图片类型/多文件另由 JUnit 验证；Selenium UI-001 发布测试商品 |
| S-004 | 后台查看当前商品，内容与发布结果一致 | 容器 D22 |
| S-005、S-006 | 手动冻结/解冻；交易冻结不能手动解冻 | 容器 D10、D11、D15 |
| S-007、S-008 | 展示排队及交易中意向，仅队首开始交易 | 容器 D13、D15、D24；Selenium UI-001 处理队首 |
| S-009 | 成交下架，相关口令失效，完整记录保留 | 容器 D18～D21；Selenium UI-001 确认成交并验证商品下架 |
| S-010 | REQUEUE 保留原码并移到队尾；DISCARD 使码失效；自动递补或恢复在售 | 容器 D16、D24～D26；数据库 DB-10～DB-16 |
| S-011 | 历史列表按 1 起始分页，展示已售商品 | 容器 D19、D23 |
| S-012 | 历史详情与完整记录一致，保留全部意向/尝试/状态事件 | 容器 D18、D19、D21、D23、D25 |

### 2.1 Selenium UI 冒烟用例

| 用例 | 覆盖流程 | 数据影响 | 状态 |
| --- | --- | --- | --- |
| UI-001：卖家发布、买家排队并完成交易 | 错误密码不能登录；卖家成功登录；发布唯一命名商品；买家提交意向并取得查询口令；凭口令查看排队状态；卖家处理队首并成交；验证队列清空且商品不再显示 | 创建商品、意向及交易记录；不会自动清理 | 已自动化并通过：1 个测试，0 失败、0 错误，Maven `BUILD SUCCESS` |

UI-001 运行真实 Chrome 和真实前后端，不模拟 API。每次运行必须使用一次性隔离测试数据库；不可连接生产库或日常开发库。UI-001 只在业务流程中验证了错误密码和成功登录，不代表其他页面、表单错误及未登录后台访问等失败路径均已覆盖。

## 3. 接口清单

以下为当前 19 个业务接口。表中“覆盖”指至少执行一项对应检查，不表示所有异常输入组合均已穷举。容器验证的脱敏路由、状态码与覆盖计数以对应结果 JSON 为准。

| 编号 | 方法 | 路径 | 核心检查 |
| --- | --- | --- | --- |
| API-01 | GET | `/api/products/current` | 空库、在售、冻结、恢复及售出后空数据 |
| API-02 | POST | `/api/admin/auth/login` | 正确/错误密码与改密后登录 |
| API-03 | PUT | `/api/admin/auth/password` | 修改密码并跨重启保留 |
| API-04 | GET | `/api/admin/products/current` | 后台当前商品 |
| API-05 | POST | `/api/admin/products` | 正常发布、超限主图、重复活跃商品 |
| API-06 | POST | `/api/admin/products/current/freeze` | 手动冻结 |
| API-07 | POST | `/api/admin/products/current/unfreeze` | 手动恢复与交易冻结拒绝 |
| API-08 | GET | `/api/admin/products/history` | 历史列表与分页 |
| API-09 | GET | `/api/admin/products/history/{id}` | 未售商品拒绝、售出后完整详情 |
| API-10 | GET | `/api/admin/products/{id}/records` | 任意状态商品的完整记录 |
| API-11 | POST | `/api/intents` | 合法提交、冻结拒绝、姓名/电话校验 |
| API-12 | GET | `/api/intents/{code}` | 有效码、重排码、无效码和终态码 |
| API-13 | PUT | `/api/intents/{code}` | 姓名/电话修改、位次保持、交易中拒绝 |
| API-14 | DELETE | `/api/intents/{code}` | 撤销与交易中拒绝 |
| API-15 | GET | `/api/admin/intents` | 队列与当前交易尝试 ID |
| API-16 | POST | `/api/admin/intents/{id}/start` | 队首开始交易 |
| API-17 | POST | `/api/admin/intents/{id}/success` | 成交、缺少尝试 ID 和旧尝试拒绝 |
| API-18 | POST | `/api/admin/intents/{id}/fail` | REQUEUE、DISCARD、单人重排与空队列 |
| API-19 | GET | `/api/images/{filename}` | 上传图片可取回，重建容器后内容一致 |

## 4. JUnit 清单

路径均位于 `backend/src/test/java/com/team/shop/`。

| 测试类 | 测试数 | 主要内容 |
| --- | ---: | --- |
| controller/admin/AdminProductControllerTest | 2 | 主图数量与 multipart 契约 |
| domain/ProductStateMachineTest | 20 | 商品状态迁移、冻结来源、可接收意向状态 |
| domain/IntentStateMachineTest | 10 | 意向修改、撤销、开始与结束约束 |
| domain/TokenGeneratorTest | 5 | 口令生成、哈希、校验 |
| dto/PhoneAndTradeRequestTest | 3 | 姓名/电话、交易尝试 ID 必填 |
| entity/TradeHistoryTest | 3 | 重排保留凭证/首次时间、终态清空、结果不可覆盖 |
| security/JwtUtilTest | 2 | 密钥约束与 JWT 验证 |
| security/TokenLookupTest | 1 | HMAC 摘要稳定性 |
| service/ImageStorageServiceTest | 1 | 有效图片、伪造或类型不符拒绝 |
| service/TradeServiceImplTest | 2 | 旧尝试不能结束新交易、单买家重排 |
| exception/GlobalExceptionHandlerBugFixTest | 1 | 错误 HTTP 方法返回 405 |
| **合计** | **50** | JUnit 不等同于真实 MySQL、完整 UI 或全接口验收 |

测试方法数依据当前源码中的 11 个测试类和 `@Test` 方法统计。每次新增或删除测试，应同步本表；执行状态须核对 Surefire XML 和 Maven 退出码。

## 5. 重点边界

- 商品图支持 JPG/PNG，业务上限 5 MiB；代理允许 multipart 开销。
- 联系电话为 11 位数字，姓名最多 20 字；提交意向只收姓名、电话。备注字段争议由缺陷库跟踪。
- 无当前商品：`GET /api/products/current` 返回 HTTP 200、`data=null`；不能把旧 404 记录当成现行预期。
- 交易确认必须携带队列返回的 `currentTradeAttemptId`，请求字段名为 `tradeAttemptId`；缺失返回 400，旧尝试返回 409。
- `submittedAt` 保留首次时间，重排使用独立 `queue_seq`；动态位次从 1 起，后台交易中意向显示 0。
- 重新排队原口令有效；作废、撤销、成交、未成交等终态使相应口令失效。
- Selenium UI-001 会创建并成交测试数据，不会自动清理；每轮运行前应新建隔离数据库。

## 6. 结果与待补

- 容器/API、数据库专项及 JUnit 结果以[验收核对报告](acceptance-2026-10-18.md)、[数据库验证报告](db-validation.md)及各自本次生成的报告为准。
- JUnit 当前源码清单为 50 个测试方法；实际通过与否必须以本次 Surefire XML 和退出码判定。
- Selenium UI-001 主流程已通过；全量页面真实浏览器覆盖、独立 UI 失败路径仍待补。
- JMeter 性能及并发测试报告保留在 `outputs/`，结果仅适用于报告记录的环境和负载，不构成生产容量保证。
- 本次人工录屏及教师意见由实际交付证据填写；不得以截图、JSON 或旧视频替代。
- BUG-002 等待需求确认事项按缺陷库状态跟踪。

> 19 个接口的基本场景覆盖不等于所有异常条件、页面路径或并发条件均已通过验收。
