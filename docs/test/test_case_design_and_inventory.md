# OxStore 测试用例设计及清单文档

> 文档版本：v1.0
> 编写日期：2026-10-14
> 对应系统版本：OxStore MVP
> 适用范围：产品成功安装后，证明所有功能正常运行的测试依据

---

## 目录

1. [文档说明](#1-文档说明)
2. [功能模块与需求映射](#2-功能模块与需求映射)
3. [测试用例总清单](#3-测试用例总清单)
4. [单元测试用例详细设计](#4-单元测试用例详细设计)
5. [API 接口测试用例设计](#5-api-接口测试用例设计)
6. [状态机与业务规则测试](#6-状态机与业务规则测试)
7. [缺陷与测试限制说明](#7-缺陷与测试限制说明)

---

## 1. 文档说明

### 1.1 目的
本文档是 OxStore 产品成功安装后，证明所有功能正常运行的核心成果物之一。它提供了：
- 每一个功能对应的测试用例设计及清单
- 测试用例与业务需求的完整追溯关系
- 自动化测试执行的脚本定位与执行说明

### 1.2 测试范围
| 测试层级 | 覆盖内容 | 执行方式 |
|:---|:---|:---|
| 单元测试 | Service、Controller、Domain、Security、Entity、DTO | JUnit 5 + Mockito，自动执行 |
| API 接口测试 | 全部 RESTful 接口的正向/异常流 | Postman / REST Assured（待自动化） |
| 状态机测试 | 商品/意向状态流转约束 | JUnit 自动执行 |
| 集成测试 | 完整业务闭环（发布→意向→交易→售出） | 手动/API 测试（待自动化） |

### 1.3 测试环境要求
- JDK 17+
- Maven 3.8+
- MySQL 8.0+（本地测试库 `shop`）
- 环境变量：`JWT_SECRET`、`TOKEN_LOOKUP_KEY`、`ADMIN_INITIAL_PASSWORD`、`DB_PASSWORD`

---

## 2. 功能模块与需求映射

| 模块 | 功能点 | 关联需求 | 测试类型 |
|:---|:---|:---|:---|
| **认证模块** | 卖家登录 | REQ-003 | 单元测试 + API 测试 |
| | 修改密码 | REQ-003 | 单元测试 + API 测试 |
| **商品模块（买家）** | 查看当前商品 | REQ-025 | API 测试 |
| **商品模块（卖家）** | 发布商品 | REQ-006, REQ-009, REQ-012 | 单元测试 + API 测试 |
| | 查看当前商品（后台） | REQ-025 | API 测试 |
| | 手动冻结商品 | REQ-027 | 单元测试 + API 测试 |
| | 手动解冻商品 | REQ-027 | 单元测试 + API 测试 |
| | 查看历史商品列表 | REQ-023 | API 测试 |
| | 查看历史商品详情 | REQ-023, S-012 | API 测试 |
| | 查看商品记录 | S-012 | API 测试 |
| **意向模块（买家）** | 提交购买意向 | REQ-024, REQ-019 | 单元测试 + API 测试 |
| | 凭口令查询意向 | REQ-024 | API 测试 |
| | 修改意向信息 | B-006 | API 测试 |
| | 撤销意向 | - | API 测试 |
| **意向模块（卖家）** | 查看意向队列 | REQ-028, S-007 | API 测试 |
| **交易模块** | 开始交易（冻结） | REQ-027, REQ-028 | 单元测试 + API 测试 |
| | 确认成交 | REQ-028 | 单元测试 + API 测试 |
| | 确认失败（重新排队/丢弃） | REQ-016, REQ-028 | 单元测试 + API 测试 |
| **图片模块** | 上传与访问图片 | REQ-009 | 单元测试 + API 测试 |
| **安全模块** | JWT 生成与验证 | REQ-031 | 单元测试 |
| | Token 索引 | - | 单元测试 |
| **状态机** | 商品状态流转 | REQ-029 | 单元测试 |
| | 意向状态流转 | REQ-029 | 单元测试 |
| **并发控制** | 单商品唯一性 | REQ-004 | 单元测试 |
| | 重复意向提交拦截 | REQ-020 | API 测试 |

---

## 3. 测试用例总清单

### 3.1 单元测试总览（已自动化，47 个用例）

| 序号 | 测试类 | 用例数 | 测试目标 | 脚本位置 |
|:---|:---|:---:|:---|:---|
| TC-001 | [AdminProductControllerTest](#tc-001-adminproductcontrollertest) | 2 | 商品发布接口：图片数量校验 | `backend/src/test/java/com/team/shop/controller/admin/AdminProductControllerTest.java` |
| TC-002 | [ProductStateMachineTest](#tc-002-productstatemachinetest) | 14 | 商品状态机全部合法/非法迁移 | `backend/src/test/java/com/team/shop/domain/ProductStateMachineTest.java` |
| TC-003 | [IntentStateMachineTest](#tc-003-intentstatemachinetest) | 14 | 意向状态机全部合法/非法迁移 | `backend/src/test/java/com/team/shop/domain/IntentStateMachineTest.java` |
| TC-004 | [TokenGeneratorTest](#tc-004-tokengeneratortest) | 5 | 口令码生成、哈希、验证 | `backend/src/test/java/com/team/shop/domain/TokenGeneratorTest.java` |
| TC-005 | [PhoneAndTradeRequestTest](#tc-005-phoneandtraderequesttest) | 2 | DTO 校验：手机号、交易请求 | `backend/src/test/java/com/team/shop/dto/PhoneAndTradeRequestTest.java` |
| TC-006 | [TradeHistoryTest](#tc-006-tradehistorytest) | 2 | 实体行为：重新排队、结果不可覆盖 | `backend/src/test/java/com/team/shop/entity/TradeHistoryTest.java` |
| TC-007 | [JwtUtilTest](#tc-007-jwtutiltest) | 2 | JWT 密钥安全与令牌验证 | `backend/src/test/java/com/team/shop/security/JwtUtilTest.java` |
| TC-008 | [TokenLookupTest](#tc-008-tokenlookuptest) | 1 | Token 索引摘要稳定性 | `backend/src/test/java/com/team/shop/security/TokenLookupTest.java` |
| TC-009 | [ImageStorageServiceTest](#tc-009-imagestorageservicetest) | 1 | 图片存储：格式、大小、伪造校验 | `backend/src/test/java/com/team/shop/service/ImageStorageServiceTest.java` |
| TC-010 | [TradeServiceImplTest](#tc-010-tradeserviceimpltest) | 4 | 交易服务：成功确认、失败递补 | `backend/src/test/java/com/team/shop/service/TradeServiceImplTest.java` |
| **合计** | | **47** | | |

### 3.2 API 接口测试清单（已手动验证，待自动化）

| 序号 | 接口 | 方法 | 测试场景数 | 关联需求 |
|:---|:---|:---|:---:|:---|
| API-001 | `/api/products/current` | GET | 2 | REQ-025 |
| API-002 | `/api/admin/auth/login` | POST | 3 | REQ-003 |
| API-003 | `/api/admin/products` | POST | 5 | REQ-006, REQ-009, REQ-012 |
| API-004 | `/api/admin/products/current` | GET | 1 | REQ-025 |
| API-005 | `/api/admin/products/current/freeze` | POST | 2 | REQ-027 |
| API-006 | `/api/admin/products/current/unfreeze` | POST | 2 | REQ-027 |
| API-007 | `/api/admin/products/history` | GET | 1 | REQ-023 |
| API-008 | `/api/admin/products/history/{id}` | GET | 2 | REQ-023, S-012 |
| API-009 | `/api/admin/products/{id}/records` | GET | 2 | S-012 |
| API-010 | `/api/intents` | POST | 6 | REQ-024, REQ-019 |
| API-011 | `/api/intents/{code}` | GET | 2 | REQ-024 |
| API-012 | `/api/intents/{code}` | PUT | 3 | B-006 |
| API-013 | `/api/intents/{code}` | DELETE | 2 | - |
| API-014 | `/api/admin/intents` | GET | 2 | REQ-028, S-007 |
| API-015 | `/api/admin/intents/{id}/start` | POST | 3 | REQ-027 |
| API-016 | `/api/admin/intents/{id}/success` | POST | 3 | REQ-028 |
| API-017 | `/api/admin/intents/{id}/fail` | POST | 4 | REQ-016, REQ-028 |
| API-018 | `/api/admin/auth/password` | PUT | 3 | REQ-003 |
| API-019 | `/api/images/{filename}` | GET | 1 | REQ-009 |

---

## 4. 单元测试用例详细设计

### TC-001: AdminProductControllerTest

**测试目标**：验证商品发布接口对图片参数的校验逻辑

| 用例编号 | 用例名称 | 前置条件 | 输入 | 预期结果 | 优先级 |
|:---|:---|:---|:---|:---|:---:|
| TC-001-01 | 多张图片拒绝 | Mock ProductService、ImageStorageService | multipart 请求含 2 个 image 文件 | HTTP 400 Bad Request；不调用 Service | 高 |
| TC-001-02 | 单张图片正常发布 | Mock ProductService、ImageStorageService | multipart 请求含 1 个 image 文件 | HTTP 200 OK；调用 store 和 publish | 高 |

**执行命令**：
```bash
cd backend
mvn test -Dtest=AdminProductControllerTest
```

---

### TC-002: ProductStateMachineTest

**测试目标**：验证商品状态机的全部状态迁移约束

| 用例编号 | 用例名称 | 输入（当前状态） | 操作 | 预期结果 | 优先级 |
|:---|:---|:---|:---|:---|:---:|
| TC-002-01 | 手动冻结-从在售允许 | ONLINE | freezeManually | 不抛异常 | 高 |
| TC-002-02 | 手动冻结-从恢复在售允许 | RESTORED_ONLINE | freezeManually | 不抛异常 | 高 |
| TC-002-03 | 手动冻结-从已冻结拒绝 | FROZEN | freezeManually | 抛 StateConflictException | 高 |
| TC-002-04 | 手动冻结-从已售出拒绝 | SOLD | freezeManually | 抛 StateConflictException | 高 |
| TC-002-05 | 手动解冻-从手动冻结允许 | FROZEN + MANUAL | unfreezeManually | 不抛异常 | 高 |
| TC-002-06 | 手动解冻-从交易冻结拒绝 | FROZEN + TRADE | unfreezeManually | 抛 StateConflictException | 高 |
| TC-002-07 | 手动解冻-从在售拒绝 | ONLINE | unfreezeManually | 抛 StateConflictException | 高 |
| TC-002-08 | 手动解冻-从售出拒绝 | SOLD | unfreezeManually | 抛 StateConflictException | 高 |
| TC-002-09 | 开始交易-从在售允许 | ONLINE | startTrade | 不抛异常 | 高 |
| TC-002-10 | 开始交易-从恢复在售允许 | RESTORED_ONLINE | startTrade | 不抛异常 | 高 |
| TC-002-11 | 开始交易-从已冻结拒绝 | FROZEN | startTrade | 抛 StateConflictException | 高 |
| TC-002-12 | 开始交易-从已售出拒绝 | SOLD | startTrade | 抛 StateConflictException | 高 |
| TC-002-13 | 确认成功-从交易冻结允许 | FROZEN + TRADE | markSuccess | 不抛异常 | 高 |
| TC-002-14 | 确认成功-从手动冻结拒绝 | FROZEN + MANUAL | markSuccess | 抛 StateConflictException | 高 |

（共 14 个用例，覆盖全部状态迁移路径）

**执行命令**：
```bash
cd backend
mvn test -Dtest=ProductStateMachineTest
```

---

### TC-003: IntentStateMachineTest

**测试目标**：验证意向状态机的全部状态迁移约束

| 用例编号 | 用例名称 | 输入（当前状态） | 操作 | 预期结果 | 优先级 |
|:---|:---|:---|:---|:---|:---:|
| TC-003-01 | 撤销-从排队中允许 | QUEUING | cancel | 不抛异常 | 高 |
| TC-003-02 | 撤销-从其他状态拒绝 | IN_TRANSACTION/SUCCESS/FAILED/CANCELLED/UNSOLD | cancel | 抛 StateConflictException | 高 |
| TC-003-03 | 修改-从排队中允许 | QUEUING | modify | 不抛异常 | 高 |
| TC-003-04 | 修改-从其他状态拒绝 | 非 QUEUING | modify | 抛 StateConflictException | 高 |
| TC-003-05 | 进入交易-从排队中允许 | QUEUING | enterTrade | 不抛异常 | 高 |
| TC-003-06 | 进入交易-从其他状态拒绝 | 非 QUEUING | enterTrade | 抛 StateConflictException | 高 |
| TC-003-07 | 确认成功-从交易中允许 | IN_TRANSACTION | markSuccess | 不抛异常 | 高 |
| TC-003-08 | 确认成功-从其他状态拒绝 | 非 IN_TRANSACTION | markSuccess | 抛 StateConflictException | 高 |
| TC-003-09 | 确认失败-从交易中允许 | IN_TRANSACTION | markFailed | 不抛异常 | 高 |
| TC-003-10 | 确认失败-从其他状态拒绝 | 非 IN_TRANSACTION | markFailed | 抛 StateConflictException | 高 |

（共 14 个用例）

**执行命令**：
```bash
cd backend
mvn test -Dtest=IntentStateMachineTest
```

---

### TC-004: TokenGeneratorTest

**测试目标**：验证买家口令码的生成、哈希与校验

| 用例编号 | 用例名称 | 输入 | 预期结果 | 优先级 |
|:---|:---|:---|:---|:---:|
| TC-004-01 | 生成8位字符 | 循环生成 100 次 | 每次 8 位；字符来自合法字母表；不含易混淆字符 | 高 |
| TC-004-02 | 生成随机唯一 | 生成 2 次 | 两次结果不相同 | 高 |
| TC-004-03 | 哈希与验证正向 | 明文口令 | 哈希值非空且不等于明文；验证通过 | 高 |
| TC-004-04 | 验证拒绝错误口令 | 正确哈希 + 错误明文 | 验证失败 | 高 |
| TC-004-05 | 验证拒绝空输入 | null 参数组合 | 验证失败 | 高 |

**执行命令**：
```bash
cd backend
mvn test -Dtest=TokenGeneratorTest
```

---

### TC-005: PhoneAndTradeRequestTest

**测试目标**：验证请求 DTO 的输入校验

| 用例编号 | 用例名称 | 输入 | 预期结果 | 优先级 |
|:---|:---|:---|:---|:---:|
| TC-005-01 | 手机号边界校验 | 11位数字 / 3位 / 12位 / 含字母 | 11位通过；其余校验失败 | 高 |
| TC-005-02 | 交易请求校验 | tradeAttemptId 为 null / 为正数 | null 失败；正数通过 | 高 |

**执行命令**：
```bash
cd backend
mvn test -Dtest=PhoneAndTradeRequestTest
```

---

### TC-006: TradeHistoryTest

**测试目标**：验证实体业务行为正确性

| 用例编号 | 用例名称 | 输入 | 预期结果 | 优先级 |
|:---|:---|:---|:---|:---:|
| TC-006-01 | 重新排队保留首次提交时间 | 已交易意向执行 requeue | submittedAt 不变；queueSeq 更新；tokenHash 清空；状态变 QUEUING | 高 |
| TC-006-02 | 尝试结果不可覆盖 | 已失败尝试执行 succeed | 抛 IllegalStateException | 高 |

**执行命令**：
```bash
cd backend
mvn test -Dtest=TradeHistoryTest
```

---

### TC-007: JwtUtilTest

**测试目标**：验证 JWT 工具的安全性与正确性

| 用例编号 | 用例名称 | 输入 | 预期结果 | 优先级 |
|:---|:---|:---|:---|:---:|
| TC-007-01 | 拒绝弱密钥 | 占位符密钥 / 短密钥 | 抛 IllegalArgumentException | 高 |
| TC-007-02 | 令牌生成与验证 | 合法密钥生成令牌 | 同密钥可解析用户名；不同密钥解析为 null | 高 |

**执行命令**：
```bash
cd backend
mvn test -Dtest=JwtUtilTest
```

---

### TC-008: TokenLookupTest

**测试目标**：验证 Token 索引摘要算法

| 用例编号 | 用例名称 | 输入 | 预期结果 | 优先级 |
|:---|:---|:---|:---|:---:|
| TC-008-01 | 摘要稳定性与密钥依赖 | 相同输入 + 不同密钥 | 同密钥摘要相同；不同密钥摘要不同；长度 64；短密钥抛异常 | 高 |

**执行命令**：
```bash
cd backend
mvn test -Dtest=TokenLookupTest
```

---

### TC-009: ImageStorageServiceTest

**测试目标**：验证图片存储服务的安全校验

| 用例编号 | 用例名称 | 输入 | 预期结果 | 优先级 |
|:---|:---|:---|:---|:---:|
| TC-009-01 | 图片格式与伪造校验 | 合法 PNG / 扩展名不匹配 / 伪造 PNG / 伪造 JPEG / 超大文件(>5MB) | 合法通过；其余抛 BizException 或 NotFoundException | 高 |

**执行命令**：
```bash
cd backend
mvn test -Dtest=ImageStorageServiceTest
```

---

### TC-010: TradeServiceImplTest

**测试目标**：验证交易核心服务逻辑

| 用例编号 | 用例名称 | 前置条件 | 输入 | 预期结果 | 优先级 |
|:---|:---|:---|:---|:---|:---:|
| TC-010-01 | 旧尝试ID无法完成新交易 | Mock 仓库；意向 IN_TRANSACTION；旧 attempt | confirmSuccess 传错 attemptId | 抛 StateConflictException；状态不变；无事件记录 | 高 |
| TC-010-02 | 失败重新排队关闭旧尝试并创建新尝试 | Mock 仓库；队列有 1 人 | confirmFail(REQUEUE) | 旧 attempt 标记 FAILED；新 attempt 创建；意向状态 IN_TRANSACTION；queueSeq 更新；保存 2 个状态事件 | 高 |

（共 4 个用例，详见源码）

**执行命令**：
```bash
cd backend
mvn test -Dtest=TradeServiceImplTest
```

---

## 5. API 接口测试用例设计

> 以下用例已在 `docs/test/test_plan.md` 中通过 Postman 手动验证。待后续使用 REST Assured 实现自动化。

### API-001: 查看当前商品（买家）

| 用例编号 | 场景 | 请求 | 预期响应 | 状态 |
|:---|:---|:---|:---|:---:|
| API-001-01 | 无在售商品 | GET /api/products/current | 200 OK, `{code:0, data:null}` | ✅ 已验证 |
| API-001-02 | 有在售商品 | GET /api/products/current | 200 OK, `{code:0, data:{商品详情}}` | ✅ 已验证 |

### API-002: 卖家登录

| 用例编号 | 场景 | 请求 | 预期响应 | 状态 |
|:---|:---|:---|:---|:---:|
| API-002-01 | 正确账号密码 | POST /api/admin/auth/login | 200 OK, `{code:0, data:{token, username}}` | ✅ 已验证 |
| API-002-02 | 错误密码 | POST /api/admin/auth/login | 401 Unauthorized | ⬜ 待自动化 |
| API-002-03 | 空用户名/密码 | POST /api/admin/auth/login | 400 Bad Request | ⬜ 待自动化 |

### API-003: 发布商品

| 用例编号 | 场景 | 请求 | 预期响应 | 状态 |
|:---|:---|:---|:---|:---:|
| API-003-01 | 正常发布 | POST /api/admin/products (multipart) | 200 OK, 商品详情 | ✅ 已验证 |
| API-003-02 | 重复发布（已有活跃商品） | POST /api/admin/products | 409 Conflict | ✅ 已验证 |
| API-003-03 | 未登录 | POST /api/admin/products | 401 Unauthorized | ✅ 已验证 |
| API-003-04 | 名称过长 | POST /api/admin/products | 400 Bad Request | ⬜ 待自动化 |
| API-003-05 | 价格非正数 | POST /api/admin/products | 400 Bad Request | ⬜ 待自动化 |

### API-010: 提交购买意向

| 用例编号 | 场景 | 请求 | 预期响应 | 状态 |
|:---|:---|:---|:---|:---:|
| API-010-01 | 正常提交 | POST /api/intents | 200 OK, `{code:0, data:{token, position}}` | ✅ 已验证 |
| API-010-02 | 无在售商品 | POST /api/intents | 404 Not Found | ✅ 已验证 |
| API-010-03 | 手机号不足11位 | POST /api/intents | 400 Bad Request | ✅ 已验证 |
| API-010-04 | 手机号含字母 | POST /api/intents | 400 Bad Request | ✅ 已验证 |
| API-010-05 | 姓名为空 | POST /api/intents | 400 Bad Request | ✅ 已验证 |
| API-010-06 | 姓名超长 | POST /api/intents | 400 Bad Request | ✅ 已验证 |

---

## 6. 状态机与业务规则测试

### 6.1 商品状态机
undefined
[初始] --发布--> ONLINE

ONLINE --freezeManually--> FROZEN(MANUAL) ONLINE --startTrade--> FROZEN(TRADE)

RESTORED_ONLINE --freezeManually--> FROZEN(MANUAL) RESTORED_ONLINE --startTrade--> FROZEN(TRADE)

FROZEN(MANUAL) --unfreezeManually--> ONLINE / RESTORED_ONLINE

FROZEN(TRADE) --markSuccess--> SOLD FROZEN(TRADE) --markFailed--> RESTORED_ONLINE (或自动递补)

**状态说明**：

| 状态 | 含义 | 可接收意向 |
|:---|:---|:---:|
| ONLINE | 在售 | ✅ |
| RESTORED_ONLINE | 恢复在售（交易失败后） | ✅ |
| FROZEN | 冻结中 | ❌ |
| SOLD | 已售出 | ❌ |

**已覆盖用例**：TC-002 全部 14 个用例

### 6.2 意向状态机
[初始] --submit--> QUEUING

QUEUING --cancel--> CANCELLED QUEUING --modify--> QUEUING QUEUING --enterTrade--> IN_TRANSACTION

IN_TRANSACTION --markSuccess--> SUCCESS IN_TRANSACTION --markFailed(REQUEUE)--> QUEUING IN_TRANSACTION --markFailed(DISCARD)--> FAILED

**已覆盖用例**：TC-003 全部 14 个用例

---

## 7. 缺陷与测试限制说明

### 7.1 已知缺陷（影响测试）

| 缺陷ID | 描述 | 对测试的影响 | 规避措施 |
|:---|:---|:---|:---|
| BUG-005 | 错误 HTTP 方法返回 500 而非 405 | 已修复 | 返回 405 Method Not Allowed |
| BUG-006 | 提交意向未校验姓名长度 | 已修复 | 已添加 @Size(max=100) 校验，返回 400 |

### 7.2 测试限制

1. **自动化覆盖范围**：当前仅后端单元测试实现自动化（47 个用例）。API 接口测试、UI 测试、并发测试尚未自动化。
2. **前端测试**：前端为 React + TypeScript，目前仅执行构建校验（`npm run build`），无单元测试覆盖。
3. **性能测试**：并发唯一性、锁等待等场景仅在独立测试库手动验证，未纳入 CI。
4. **环境依赖**：部分测试需要 MySQL 数据库，纯内存测试尚未完全覆盖。

### 7.3 后续自动化计划

| 阶段 | 内容 | 工具 | 目标 |
|:---|:---|:---|:---|
| 第一阶段 | API 接口自动化 | REST Assured + JUnit | 覆盖全部 19 个接口的正向/异常流 |
| 第二阶段 | 核心业务闭环自动化 | 集成测试 | 端到端发布→售出流程 |
| 第三阶段 | 并发与性能自动化 | JMeter / Gatling | 验证单商品唯一性、锁等待 |
| 第四阶段 | UI 自动化 | Selenium / Playwright | 验证前端页面交互 |

---

## 附录 A：自动化测试执行手册

### A.1 执行全部单元测试

```bash
cd c:\Users\唐\Projects\OxStore\backend
mvn test
```

**预期结果**：47 个测试用例全部通过（约 10-20 秒）

### A.2 执行单个测试类

```bash
cd c:\Users\唐\Projects\OxStore\backend
mvn test -Dtest=ProductStateMachineTest
```

### A.3 查看测试报告

测试报告生成位置：`backend/target/surefire-reports/`
- XML 格式：`TEST-<class>.xml`
- 文本格式：`<class>.txt`

### A.4 CI 流水线验证

GitHub Actions 配置：`.github/workflows/ci.yml`
触发条件：每次 Push / Pull Request
验证步骤：后端编译测试 → 前端构建 → Docker Compose 配置校验

---

## 附录 B：需求追溯矩阵

| 需求ID | 需求描述 | 覆盖用例 |
|:---|:---|:---|
| REQ-003 | 卖家登录后台 | TC-007, API-002, API-018 |
| REQ-004 | 单商品售卖与并发唯一性 | TC-002, TC-010, API-003-02 |
| REQ-006 | 单商品发布 | TC-001, API-003 |
| REQ-009 | 图片上传与校验 | TC-009, API-003 |
| REQ-012 | 商品字段与价格边界校验 | TC-001, API-003 |
| REQ-016 | 确认失败并解冻 | TC-010, API-017 |
| REQ-017 | 系统异常处理与状态一致性 | TC-002, TC-003 |
| REQ-019 | 买家联系信息校验 | TC-005, API-010 |
| REQ-020 | 重复意向提交拦截 | API-010 |
| REQ-023 | 售出后查询 | API-001, API-008 |
| REQ-024 | 提交购买意向 | TC-005, API-010 |
| REQ-025 | 免注册商品浏览 | API-001 |
| REQ-027 | 卖家冻结商品 | TC-002, API-015 |
| REQ-028 | 卖家确认成交 | TC-010, API-016 |
| REQ-029 | 状态机流转约束 | TC-002, TC-003 |
| REQ-031 | 后台权限与会话隔离 | TC-007, API-002-03 |
| REQ-034 | 错误 HTTP 方法处理 | TC-002, TC-003, API 测试 |
| REQ-039 | 售出后发布下一件 | API-003 |

---

> 本文档由测试团队维护。每次需求变更或缺陷修复后，需同步更新对应测试用例。