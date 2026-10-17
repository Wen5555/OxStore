# OxStore 测试用例设计及清单

更新日期：2026-10-18。沿用R4原有测试分类，由R5核对当前接口、既有JUnit和容器验证脚本后更新映射。自动化命令见[运行手册](automation_runbook.md)。

## 1. 范围与判定

测试分为后端JUnit、真实Docker/API验证、数据库专项验证和前端页面测试。功能覆盖按需求与接口逐项对应，不能用测试条数代替覆盖率。

- 当前后端共有11个测试类、50个JUnit测试方法；执行结果以Surefire XML为准。
- 容器脚本通过Nginx调用真实Java/MySQL服务，覆盖19个业务接口与镜像运行、重启持久化。
- 数据库专项脚本检查建表、约束、迁移及交易记录；历史结果保留原执行日期。
- `frontend/e2e/buyer-seller-flows.spec.ts`使用模拟API，验证前端交互；真实服务验证由容器脚本负责。
- 本次录屏由张耀文手动完成，状态为待补；截图、JSON及旧视频不代替本次录屏。

## 2. 功能与自动化对应

需求编号使用Wiki《需求规格说明书V1》的B/S用例编号，避免与旧REQ编号混用。

| 用例 | 功能与预期 | 自动化入口与检查点 |
| --- | --- | --- |
| B-001～B-003 | 展示在售/冻结商品；无商品时返回空数据并提示 | 容器D04、D08、D10、D18；前端页面显示另行人工核对 |
| B-004 | 姓名/电话有效且商品可售时成功排队，返回个人口令与位次 | 容器D12、D13、D26；冻结期间拒绝新增 |
| B-005 | 原码查询本人状态、重排后仍可查询；终态与无效码拒绝 | 容器D13、D14、D16、D18、D24、D25 |
| B-006 | 排队中修改姓名和电话，位次不变；交易中拒绝修改 | 容器D14、D15 |
| B-007 | 排队中撤销后退出，原码失效；交易中拒绝撤销 | 容器D14、D15 |
| S-001 | 登录成功取得JWT；错误密码和未登录访问拒绝 | 容器D05、D06、D20 |
| S-002 | 修改密码后旧密码失效，新密码与重启后记录保留 | 容器D20、D21 |
| S-003 | 发布商品及主图；拒绝第二件活跃商品和超限图片 | 容器D07～D09；图片类型/多文件另由JUnit验证 |
| S-004 | 后台查看当前商品，内容与发布结果一致 | 容器D22 |
| S-005、S-006 | 手动冻结/解冻；交易冻结不能手动解冻 | 容器D10、D11、D15 |
| S-007、S-008 | 展示排队及交易中意向，仅队首开始交易 | 容器D13、D15、D24；队首约束另见服务实现与专项用例 |
| S-009 | 成交下架，相关口令失效，完整记录保留 | 容器D18～D21 |
| S-010 | REQUEUE保留原码并移到队尾；DISCARD使码失效；自动递补或恢复在售 | 容器D16、D24～D26；数据库DB-10～DB-16 |
| S-011 | 历史列表按1起始分页，展示已售商品 | 容器D19、D23 |
| S-012 | 历史详情与完整记录一致，保留全部意向/尝试/状态事件 | 容器D18、D19、D21、D23、D25 |

## 3. 接口清单

以下为当前19个接口。表中“覆盖”指至少执行一项对应检查，不表示全部异常输入组合已穷举。实际请求的脱敏路由、状态码与覆盖计数写入容器结果JSON。

| 编号 | 方法 | 路径 | 核心检查 |
| --- | --- | --- | --- |
| API-01 | GET | `/api/products/current` | 空库、在售、冻结、恢复及售出后空数据 |
| API-02 | POST | `/api/admin/auth/login` | 正确/错误密码与改密后登录 |
| API-03 | PUT | `/api/admin/auth/password` | 修改密码并跨重启保留 |
| API-04 | GET | `/api/admin/products/current` | 后台当前商品 |
| API-05 | POST | `/api/admin/products` | 正常发布、超限主图、重复活跃商品 |
| API-06 | POST | `/api/admin/products/current/freeze` | 手动冻结 |
| API-07 | POST | `/api/admin/products/current/unfreeze` | 手动恢复与交易冻结拒绝 |
| API-08 | GET | `/api/admin/products/history` | 历史列表与page=1 |
| API-09 | GET | `/api/admin/products/history/{id}` | 未售商品拒绝、售出后完整详情 |
| API-10 | GET | `/api/admin/products/{id}/records` | 任意状态商品的完整记录 |
| API-11 | POST | `/api/intents` | 合法提交、冻结拒绝、姓名/电话校验 |
| API-12 | GET | `/api/intents/{code}` | 有效码、重排码、无效码和终态码 |
| API-13 | PUT | `/api/intents/{code}` | 姓名/电话修改、位次保持、交易中拒绝 |
| API-14 | DELETE | `/api/intents/{code}` | 撤销与交易中拒绝 |
| API-15 | GET | `/api/admin/intents` | 队列与当前交易尝试ID |
| API-16 | POST | `/api/admin/intents/{id}/start` | 队首开始交易 |
| API-17 | POST | `/api/admin/intents/{id}/success` | 成交、缺少尝试ID和旧尝试拒绝 |
| API-18 | POST | `/api/admin/intents/{id}/fail` | REQUEUE、DISCARD、单人重排与空队列 |
| API-19 | GET | `/api/images/{filename}` | 上传图片可取回，重建容器后内容一致 |

## 4. JUnit清单

路径均位于 `backend/src/test/java/com/team/shop/`。

| 测试类 | 测试数 | 主要内容 |
| --- | --- | --- |
| controller/admin/AdminProductControllerTest | 2 | 主图数量与multipart契约 |
| domain/ProductStateMachineTest | 20 | 商品状态迁移、冻结来源、可接收意向状态 |
| domain/IntentStateMachineTest | 10 | 意向修改、撤销、开始与结束约束 |
| domain/TokenGeneratorTest | 5 | 口令生成、哈希、校验 |
| dto/PhoneAndTradeRequestTest | 3 | 姓名/电话、交易尝试ID必填 |
| entity/TradeHistoryTest | 3 | 重排保留凭证/首次时间、终态清空、结果不可覆盖 |
| security/JwtUtilTest | 2 | 密钥约束与JWT验证 |
| security/TokenLookupTest | 1 | HMAC摘要稳定性 |
| service/ImageStorageServiceTest | 1 | 有效图片、伪造或类型不符拒绝 |
| service/TradeServiceImplTest | 2 | 旧尝试不能结束新交易、单买家重排 |
| exception/GlobalExceptionHandlerBugFixTest | 1 | 错误HTTP方法返回405 |
| 合计 | 50 | JUnit不等于真实MySQL或完整UI验收 |

ProductStateMachineTest中的20项、IntentStateMachineTest中的10项以本轮XML核对；结果汇总若与源码不一致应先修正计数，不能沿用旧表。

## 5. 重点边界

- 商品图支持JPG/PNG，业务上限5 MiB；代理允许multipart开销。
- 联系电话为11位数字，姓名最多20字；提交意向只收姓名、电话。备注字段争议留在缺陷库由R1确认。
- 无当前商品：`GET /api/products/current` 返回HTTP200、`data=null`；不能把旧404截图当成现行预期。
- 交易确认必须携带队列返回的 `currentTradeAttemptId`，请求字段名为 `tradeAttemptId`；缺失400，旧尝试409。
- `submittedAt`保留首次时间，重排使用独立 `queue_seq`；动态位次从1起，后台交易中意向显示0。
- 重新排队原口令有效，作废/撤销/成交/未成交等终态使相应口令失效。

## 6. 结果与待补

本轮结果、执行日期、镜像与源码对应关系见[验收核对报告](acceptance-2026-10-18.md)。历史数据库24项结果见[数据库验证](db-validation.md)。

尚未作为完成项：本次人工录屏、全部UI路径真实浏览器覆盖、压力并发测试，以及BUG-002需求确认。19接口的基本场景覆盖不等于这些项目已通过。
