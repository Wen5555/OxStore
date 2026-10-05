# OxStore 测试计划与报告 (v1.0)

## 1. 测试范围（基于需求表 REQ-001 至 REQ-040）
- **核心业务闭环（MVP核心）**：免注册商品浏览（REQ-025）、提交购买意向（REQ-024）、卖家登录后台（REQ-003）、单商品发布（REQ-006）、卖家冻结商品（REQ-027）、卖家确认成交（REQ-028）、确认失败并解冻（REQ-016）、售出后发布下一件（REQ-039）。
- **状态与并发（非功能/数据）**：商品状态机流转约束（REQ-029）、单商品售卖与并发唯一性（REQ-004）、系统异常处理与状态一致性（REQ-017）、重复意向提交拦截（REQ-020）。
- **边界与安全**：商品字段与价格边界校验（REQ-012）、图片上传与校验（REQ-009）、买家联系信息校验（REQ-019）、后台权限与会话隔离（REQ-031）。

## 2. 测试策略与工具链
| 测试类型 | 工具 | 关联需求 | 触发时机 |
| :--- | :--- | :--- | :--- |
| 后端单元测试 | JUnit 5 + Mockito | REQ-004, 012, 029 | 每次 Push / PR |
| 前端构建校验 | Node.js + npm | 全局 | 每次 Push / PR |
| 部署配置校验 | Docker Compose | DEL-04 | 每次 Push / PR |
| API 接口测试 | Postman / REST Assured | REQ-025, 024, 003, 006 | 联调阶段 |
| 状态机与并发测试 | JUnit + JMeter | REQ-004, 017, 029 | 版本发布前 |
| UI 界面测试 | Selenium | REQ-023, 036 | 联调阶段 |

## 3. 待澄清事项对测试的影响（Q01-Q12）
根据需求表，部分边界值尚未确认（如价格上限、冻结时长、图片大小等）。测试用例将暂按“建议值”编写（如价格0.01-999999.99，图片2MB），待 Q05/Q06 确认后修改断言。

## 4. 第一阶段测试进度
- **第1周**：搭建 CI 框架，跑通本地单测（47个用例）。
- **第2-3周**：补充基于 REQ-012（字段边界）、REQ-029（状态机）的 API 与并发测试用例。

## 5. 当前测试报告 (v0.1.0 - 2026-10-03)

### 5.1 基础设施与 CI
- **本地后端单测**：`mvn test` 执行成功，47个测试用例全部通过。
  ![本地mvn test成功](screenshots/local_mvn_test.png)
- **云端 CI 流水线**：PR #1 中 6 checks passed，后端、前端、Docker 校验全绿，已合并 main。
  ![CI全绿](screenshots/ci_green.png)
  ![PR合并成功](screenshots/pr_merged.png)

### 5.2 核心业务闭环测试（快乐路径）
本次测试在本地环境真实执行了核心接口，完成了从发布到售出的完整业务闭环，全部通过。

| 测试步骤 | 接口 | 方法 | 真实结果 | 状态 | 关联需求 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | /api/products/current | GET | 200 OK，{code:0, data:null} | ✅ 通过 | REQ-025 |
| 2 | /api/admin/auth/login | POST | 200 OK，成功获取 Token | ✅ 通过 | REQ-003 |
| 3 | /api/admin/products | POST | 200 OK，{id:1, status:ONLINE, imagePath:...} | ✅ 通过 | REQ-006, REQ-009 |
| 4 | /api/products/current | GET | 200 OK，成功获取商品详情 | ✅ 通过 | REQ-025 |
| 5 | /api/intents | POST | 200 OK，{code:"ctCKcaFC", position:1} | ✅ 通过 | REQ-024 |
| 6 | /api/admin/intents | GET | 200 OK，队列包含 QUEUING 状态的张三 | ✅ 通过 | REQ-028 |
| 7 | /api/admin/intents/1/start | POST | 200 OK，商品状态变为 FROZEN | ✅ 通过 | REQ-027 |
| 8 | /api/admin/intents | GET | 200 OK，包含 IN_TRANSACTION 状态及 currentTradeAttemptId | ✅ 通过 | REQ-028, REQ-029 |
| 9 | /api/admin/intents/1/success | POST | 200 OK，交易成功完成 | ✅ 通过 | REQ-028 |
| 10 | /api/products/current | GET | 404 Not Found，友好提示“当前没有在售商品” | ✅ 通过 | REQ-023, REQ-025 |

![发布商品成功](screenshots/api_03_product_publish_success.png)
![提交意向成功](screenshots/api_05_intent_submit_success.png)
![确认成交成功](screenshots/api_09_confirm_success.png)
![售出后查询404](screenshots/api_10_current_sold_out_404.png)

### 5.3 API 异常流与边界值测试 (2026-10-03)
针对输入非法数据、未授权访问等场景进行破坏性测试，验证系统的健壮性。

| 测试场景 | 请求 | 真实结果 | 状态 | 关联需求 | 截图 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 未登录访问后台 | GET /api/admin/intents | 401 Unauthorized, "未登录或登录已过期" | ✅ 通过 | REQ-031 | api_error_401_no_token.png |
| 手机号不足11位 | POST /api/intents | 400 Bad Request, "buyerPhone 联系电话须为 11 位数字" | ✅ 通过 | REQ-019 | api_error_phone_short.png |
| 手机号含字母 | POST /api/intents | 400 Bad Request, "buyerPhone 联系电话须为 11 位数字" | ✅ 通过 | REQ-019 | api_error_phone_letters.png |
| 姓名为空 | POST /api/intents | 400 Bad Request, "buyerName 姓名不能为空" | ✅ 通过 | REQ-019 | api_error_name_empty.png |
| 姓名仅空格 | POST /api/intents | 400 Bad Request, "buyerName 姓名不能为空" | ✅ 通过 | REQ-019 | api_error_name_blank.png |
| 姓名超长（几十字） | POST /api/intents | 200 OK，未拦截，成功创建意向 | ❌ **失败（BUG-006）** | REQ-019 | api_error_name_long_bug.png |
| 无在售商品时提交意向 | POST /api/intents | 404 Not Found, "当前没有在售商品" | ✅ 通过 | REQ-024 | api_error_no_product_submit.png |
| 错误 HTTP 方法（GET 打 POST） | GET /api/admin/products | 500 Internal Server Error | ❌ **失败（BUG-005）** | REQ-034 | api_error_method_not_allowed_500.png |

### 5.4 状态机非法流转测试 (2026-10-03)
验证核心状态机的约束条件，确保业务逻辑不会因非法跳转而崩溃。

| 测试场景 | 请求 | 真实结果 | 状态 | 关联需求 | 截图 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 操作不存在的意向 | POST /api/admin/intents/1/success | 404 Not Found, "意向不存在" | ✅ 通过 | REQ-029 | api_state_error_intent_not_found.png |
| 重复发布第二件商品 | POST /api/admin/products | 409 Conflict, "已存在在售或冻结中的商品" | ✅ 通过 | REQ-004, REQ-029 | api_state_error_publish_duplicate.png |
| 未冻结直接成交 | POST /api/admin/intents/1/success | 409 Conflict (意向不在交易中) | ✅ 通过 | REQ-029 | api_state_error_success_without_freeze.png |

## 6. 前后端联调测试约定（API 测试基线）
根据与 R2、R3 的沟通，后续 API 与 UI 测试将严格执行以下断言标准：
1. **统一响应格式**：所有接口响应必须为 `{code, message, data}`。断言 `code=0` 为成功；`code=401` 时，前端拦截器必须能清 token 并跳转登录页。
2. **发布商品接口（Multipart）**：参数必须包含 `name`, `description`, `price`, `image`（文件字段名必须为 `image`，`imagePath` 由后端生成，前端不传）。
3. **历史列表分页**：断言 `page` 从 `0` 开始，默认 `size=10`。
4. **图片访问**：前端直接通过 `<img src={imagePath}>` 渲染，断言后端生成的 `imagePath` 路径（如 `/api/images/xxx.png`）可直接访问。
5. **接口全覆盖**：R2 声称 15 个接口全部实测可用，R4 将逐一核对 `api/*.ts` 定义，确保一一对应后开始写页面测试。

## 7. 缺陷登记与架构缺口（汇总）
在评审和测试中发现以下问题，目前测试无法覆盖完整流程，已在缺陷库登记（详见 `docs/test/defects.md`）：
- **BUG-001（高危，已修复验证）**：`GET /api/admin/intents` 只返回 `QUEUING` 意向，递补流程死锁。R4 复测已可返回 `IN_TRANSACTION` 状态及 `currentTradeAttemptId`，问题解决。
- **BUG-002（中危，待讨论）**：基线需求（REQ-019、REQ-024）要求提交意向包含“备注”字段，但当前设计砍掉了备注。待 R1 确认是有意为之还是遗漏。
- **BUG-005（中危，待修复）**：错误 HTTP 方法（如用 GET 访问只支持 POST 的接口）导致后端返回 500 而非 405。
- **BUG-006（中危，待修复）**：提交意向接口未校验姓名字段长度，超长文本可以成功创建意向。

## 8. 数据库与环境状态确认（联调前置）
- 本地 `shop` 库已通过 `backend/src/main/resources/db/schema.sql` 建好，三表结构与脚本一致，未发生改动。
- 本地演示数据包含历史乱码记录，测试前需执行清表操作重置数据。
- 数据源密码已改为 `DB_PASSWORD` 环境变量可覆盖（默认值不变）。
- 未登录访问后台已由 Spring 默认错误格式改为统一 `{code:401, message}` JSON，需回归测试其安全性。