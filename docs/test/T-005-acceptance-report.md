# T-005 验收测试成果报告 · 账户注册/登录与未登录拦截

> **交付物说明**：本报告为迭代 2（Sprint 1）任务 **T-005** 的独立验收成果文档，涵盖 **JUnit 后端自动化基线验证** 与 **黑盒验收测试（页面 UI + 后端 API + 数据库查表）** 全流程实测结果。所有截图与运行证据均采用超链接方式索引，不在正文内嵌大图，保持版面整洁易读。

---

## 一、任务元信息与总体结论

| 维度 | 详情 |
| :--- | :--- |
| **任务编号 (Task ID)** | **T-005** |
| **关联产品待办 (PB / US)** | **PB-04 / US-04** 顾客注册与登录 |
| **禅道追踪编号** | 子需求 **13928**（父需求 PB-04 = **13904**，所属模块：`/用户认证与权限`） |
| **验收负责人** | R2 彭燕（PO / 独立验收测试） |
| **执行时间** | 2026-10-27 12:02 – 12:08（Asia/Shanghai，UTC+8） |
| **被测代码基线** | `Wen5555/OxStore` `main` 分支（Commit: `fdd9b6a`） |
| **验收依据** | `docs/iteration2/product-backlog.md` US-04（AC1～AC5 & How to demo）、`requirements-specification.md` §5.1.1 / §6.2 / §7.1 场景4（用例 B-001 / B-002 / B-009） |
| **JUnit 自动化测试结果** | ✅ **PASS（21 / 21 全部通过，0 失败 / 0 错误 / 0 跳过）** · [📷 查看 JUnit 运行截图](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_00_junit_test_pass.png) |
| **黑盒验收用例结果** | ✅ **PASS（11 / 11 全部通过，含 5 条主路径 + 6 条边界/负面用例）** |
| **综合验收结论** | ✅ **通过（PASS）—— 满足 Sprint 1 Definition of Done (DoD) 全部验收标准，可进入 Sprint Review 演示** |

---

## 二、测试环境与前置核验

### 2.1 运行环境配置

| 组件 | 实测版本 / 配置 | 状态 |
| :--- | :--- | :---: |
| **JDK / Maven** | Eclipse Temurin OpenJDK `17.0.21` / Apache Maven `3.9.9` | ☑ 已就绪 |
| **后端服务** | Spring Boot `3.2.5`（监听 `http://127.0.0.1:8080`，启用 Spring Security + JWT 过滤器） | ☑ 已启动 |
| **前端服务** | React `18.3.1` + Vite `5.2.13` + Ant Design `5.17.0`（监听 `http://127.0.0.1:5173`，代理 `/api`） | ☑ 已启动 |
| **数据库引擎** | MySQL 兼容模式持久化库（包含迭代 2 `customer`、`product`、`purchase_intent` 等完整表结构） | ☑ 已就绪 |
| **浏览器引擎** | Google Chrome / Playwright Chromium `153.0`（视口 `1280×800 @2x`） | ☑ 已就绪 |

### 2.2 测前环境检查单（E1～E5）

| 编号 | 检查项 | 结果 | 核验说明 |
| :---: | :--- | :---: | :--- |
| **E1** | 后端服务已启动并响应健康请求 | ☑ 通过 | `http://127.0.0.1:8080/api/categories/tree` 返回 `HTTP 200 (code=0)` |
| **E2** | 前端开发服务已启动并代理 `/api` | ☑ 通过 | `http://127.0.0.1:5173/` 页面渲染正常，接口代理无跨域异常 |
| **E3** | 数据库含 `customer` 表且支持客户端查表 | ☑ 通过 | 支持 SQL 直接查询 `customer` 表核验 `password_hash`、`location` 字段 |
| **E4** | 已准备至少 1 件 `ONLINE` 在售商品供拦截对照 | ☑ 通过 | 在售商品 `蓝牙耳机A`（`productId=1`，状态 `ONLINE`，价格 `¥199.00`，库存 `5`） |
| **E5** | 卖家后台（`admin`）可正常登录并准备测试商品 | ☑ 通过 | 预置卖家 `admin` 登录成功并完成测试商品上架 |

### 2.3 测试数据集设计

| 数据角色 | 用户名 / 标识 | 输入参数 | 覆盖用例 |
| :--- | :--- | :--- | :--- |
| **新注册买家 A（主路径）** | `acc_t005_a` | 密码 `Passw0rd!`（9 位 ≥ 8 位），手机号 `13800000001`，默认交易地点**留空** | C-005-01、03、04、05、07、09 |
| **新注册买家 B（选填地点）** | `acc_t005_b` | 密码 `Passw0rd!`，手机号 `13800000002`，默认交易地点填 `一食堂门口` | C-005-02、04 |
| **短密码负面样例** | `acc_t005_short` | 密码 `short7`（前端 6 位）/ `short77`（API 7 位 < 8 位），手机号 `13800000003` | C-005-06 |
| **缺必填负面样例** | `acc_t005_nophone` | 分别置空手机号、用户名、密码 | C-005-08 |
| **错误登录负面样例** | `acc_t005_a` / `non_existent_user_999` | 错误密码 `WrongPass123!` / 不存在的用户名 / 用手机号 `13800000001` 当用户名 | C-005-03、09 |
| **在售对照商品** | `蓝牙耳机A` (`id=1`) | 状态 `ONLINE`，二级类目 `数码电器 / 手机数码`，价格 `¥199.00`，库存 `5` | C-005-05、10、11 |

---

## 三、JUnit 后端自动化测试结果（第一部分）

在开展页面黑盒验收前，先执行后端 Maven JUnit 自动化测试套件，验证后端接口契约与业务服务层逻辑：

- **执行命令**：`mvn -B -f backend/pom.xml test`
- **总体统计**：共运行 **10 个测试类、21 项测试方法**，耗时 `6.154 s`，**通过 21 项，失败 0 项，错误 0 项，跳过 0 项（BUILD SUCCESS）**。
- **运行截图与日志**：
  - [📷 查看截图：Maven JUnit 自动化测试全绿终端输出 (t005_00_junit_test_pass.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_00_junit_test_pass.png)
  - [📄 查看原始日志：mvn_test_clean.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2/mvn_test_clean.log)

### 3.1 JUnit 测试类与 T-005 关联明细

| 测试类 | 用例数 | 耗时 | 与 T-005 (PB-04) 的关联验证内容 | 结果 |
| :--- | :---: | :---: | :--- | :---: |
| `Iteration2ApiIntegrationTest` | 1 | 3.774 s | 自动验证 `POST /api/auth/register`（HTTP 201 分配 `customerId`）、`POST /api/auth/login`（签发顾客 JWT）、未登录访问需鉴权接口返回 `HTTP 401`、已登录携带 Bearer Token 成功提交购买意向 `POST /api/products/{id}/intents` | ✅ PASS |
| `JwtUtilTest` | 2 | 0.003 s | 验证 JWT Token 生成、签名校验与角色身份（`CUSTOMER` / `SELLER`）解析 | ✅ PASS |
| `PhoneAndTradeRequestTest` | 2 | 0.225 s | 验证手机号与请求 DTO 字段格式校验约束 | ✅ PASS |
| `GlobalExceptionHandlerBugFixTest` | 1 | 0.013 s | 验证全局异常处理器对参数校验失败（40001）与鉴权异常的标准 JSON 封装 | ✅ PASS |
| `AdminProductControllerTest` | 3 | 0.815 s | 验证卖家后台商品管理控制器与权限隔离 | ✅ PASS |
| `IntentStateMachineTest` | 1 | 0.001 s | 验证购买意向状态机流转合法性 | ✅ PASS |
| `ProductStateMachineTest` | 3 | 0.001 s | 验证商品状态机（`ONLINE` / `FROZEN` / `OFFLINE`）流转 | ✅ PASS |
| `TradeServiceImplTest` | 4 | 0.113 s | 验证交易服务队列处理与并发锁保护 | ✅ PASS |
| `ImageStorageServiceTest` | 1 | 0.053 s | 验证商品图片格式、魔数与大小校验 | ✅ PASS |
| `TradeHistoryTest` | 3 | 0.002 s | 验证交易历史记录快照与终态约束 | ✅ PASS |

> **说明**：此外前端仓库自带的 4 项 Playwright E2E 回归测试（含 `匿名买家可浏览商品，但提交意向时必须登录且没有口令入口`）亦全部通过（`4 passed in 4.9s`，详见 [📄 playwright_e2e_output.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2/playwright_e2e_output.log)）。

---

## 四、黑盒验收测试结果总览（第二部分：UI + API + DB）

### 4.1 验收清单总表（C-005-01 ～ C-005-11）

| 用例编号 | 类别 | 用例名称 | 对应验收点 | 实测结果 | 截图证据链接（点击查看） |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **C-005-01** | 主路径 | 注册成功（必填齐、密码≥8、地点空） | PB-04 AC1/AC2/AC3；SRS B-001 | ☑ **通过** | [📷 注册表单填写](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_01a_register_form.png) · [📷 注册成功跳转](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_01b_register_success.png) |
| **C-005-02** | 主路径 | 注册成功（地点选填有值） | PB-04 AC1（地点选填） | ☑ **通过** | [📷 含选填地点注册](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_02_register_with_location.png) |
| **C-005-03** | 主路径 | 用户名 + 密码登录成功（禁手机号当账号） | PB-04 AC3；SRS B-002 | ☑ **通过** | [📷 登录页表单](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_03a_login_form.png) · [📷 登录成功前台态](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_03b_login_success.png) |
| **C-005-04** | 主路径 | 密码哈希入库（BCrypt 非明文） | PB-04 AC5；SRS §6.2 | ☑ **通过** | [📷 数据库 customer 表哈希核验](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_04_db_password_hash.png) |
| **C-005-05** | 主路径 | 登录后可对在售商品提交意向（拦截解除） | PB-04 AC4 正向；SRS B-009 | ☑ **通过** | [📷 登录后成功提交购买意向](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_05_logged_in_submit_intent.png) |
| **C-005-06** | 负面/边界 | 密码长度 `< 8` 拒绝注册 | PB-04 AC2 | ☑ **通过** | [📷 短密码拦截提示](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_06_short_password_rejected.png) |
| **C-005-07** | 负面/边界 | 重复用户名拒绝注册 | PB-04 AC2 | ☑ **通过** | [📷 重复用户名拒绝提示](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_07_duplicate_username_rejected.png) |
| **C-005-08** | 负面/边界 | 缺必填字段拒绝（用户名 / 密码 / 电话） | PB-04 AC1 | ☑ **通过** | [📷 缺必填项红字校验提示](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_08_missing_required_fields.png) |
| **C-005-09** | 负面/边界 | 错误密码 / 不存在用户登录失败 | PB-04 AC3 | ☑ **通过** | [📷 错误凭据登录失败提示](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_09_login_wrong_credentials.png) |
| **C-005-10** | 负面/边界 | 未登录可浏览，但无法提交购买意向 | PB-04 AC4；SRS §5.1.1 | ☑ **通过** | [📷 未登录详情提示](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_10a_unauth_detail_prompt.png) · [📷 点提交跳转登录页](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_10b_unauth_redirect_login.png) |
| **C-005-11** | 负面/边界 | 界面无口令码入口（注册/登录/详情页） | PB-04 AC4；DoD 无口令码 | ☑ **通过** | [📷 详情页无口令码全貌](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_11_no_passphrase_ui.png) |

---

## 五、逐条用例执行详情与证据核验

### 5.1 主路径用例（Happy Path）

#### C-005-01 · 注册成功（必填齐、密码 ≥ 8、地点空）
- **操作步骤**：
  1. 浏览器访问 `/register`，确认表单包含「用户名」「密码」「手机号」「默认交易地点（选填）」四个字段，**无验证码输入框**。
  2. 填写用户名 `acc_t005_a`、密码 `Passw0rd!`（9 位）、手机号 `13800000001`，默认交易地点留空，点击「注册」。
- **期望结果**：注册成功，弹出成功提示并跳转至 `/login`；无验证码要求。
- **实际结果**：后端 `POST /api/auth/register` 返回 `HTTP 201 Created`（`code=0, customerId=1`），前端弹出全局提示 `注册成功，请登录` 并自动路由跳转至 `/login`。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：顾客注册表单填写态 (t005_01a_register_form.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_01a_register_form.png) ｜ [📷 查看截图：注册成功提示并跳转登录页 (t005_01b_register_success.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_01b_register_success.png)

#### C-005-02 · 注册成功（地点选填有值）
- **操作步骤**：访问 `/register`，填写用户名 `acc_t005_b`、密码 `Passw0rd!`、手机号 `13800000002`、默认交易地点 `一食堂门口`，点击「注册」。
- **期望结果**：注册成功并入库保存默认交易地点。
- **实际结果**：返回 `HTTP 201 Created`（`customerId=2`），跳转 `/login`；查库确认 `location` 字段存为 `一食堂门口`（买家 A 未填则为 `NULL`，商家端展示为 `未设置`）。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：含选填默认交易地点注册 (t005_02_register_with_location.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_02_register_with_location.png)

#### C-005-03 · 用户名 + 密码登录成功
- **操作步骤**：
  1. 访问 `/login`，检查登录表单字段，输入 `acc_t005_a` 与 `Passw0rd!` 点击「登录」。
  2. 对照测试：尝试将手机号 `13800000001` 作为用户名调用登录接口 `POST /api/auth/login`。
- **期望结果**：使用用户名+密码登录成功并建立会话；手机号不可作为登录账号。
- **实际结果**：登录页仅提供「用户名」与「密码」输入框；`acc_t005_a` 登录返回 `HTTP 200` 并写入 `localStorage.customer_token`，跳回首页后右上角出现「我的购买历史」与「退出登录」按钮；使用手机号 `13800000001` 作为用户名登录返回 `HTTP 401 (code=40102, 用户名或密码错误)`。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：顾客登录页表单 (t005_03a_login_form.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_03a_login_form.png) ｜ [📷 查看截图：登录成功后首页会话态 (t005_03b_login_success.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_03b_login_success.png)

#### C-005-04 · 密码哈希入库（非明文）
- **操作步骤**：连接数据库执行查询：
  ```sql
  SELECT id, username, phone, COALESCE(location, '<NULL>') AS location, registered_at, password_hash
  FROM customer ORDER BY id;
  ```
- **期望结果**：`password_hash` 存储为加密哈希值（BCrypt `$2a$`/`$2b$` 前缀），绝不存储明文密码。
- **实际结果**：
  - `acc_t005_a` (`id=1`)：`password_hash = $2a$10$IZ98a6vbb0jNeHXoBEKq8.frXIinKXHqdjnDCcrHpMVaHzAV3gse6`（60 位标准 BCrypt 哈希）
  - `acc_t005_b` (`id=2`)：`password_hash = $2a$10$9klWx1VRC3bOExHADhIR5OQaK.GqqI5zm2csLDk03Xw2jcOys9WQO`（60 位标准 BCrypt 哈希）
  - 库表无任何明文密码。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：数据库 customer 表 BCrypt 密码哈希查询结果 (t005_04_db_password_hash.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_04_db_password_hash.png)

#### C-005-05 · 登录后可对在售商品提交意向（对照：拦截已解除）
- **操作步骤**：保持 `acc_t005_a` 已登录状态，打开在售商品 `蓝牙耳机A`（`/products/1`），点击「提交购买意向」。
- **期望结果**：提交成功（数量固定为 1），界面无口令码输入或展示。
- **实际结果**：前端携带 `Authorization: Bearer <customer_token>` 调用 `POST /api/products/1/intents`，返回 `HTTP 200 OK`（`status="QUEUING"`），页面顶部弹出绿色成功提示 `购买意向已提交`，全程无口令码、无数量输入框。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：已登录买家成功提交购买意向 (t005_05_logged_in_submit_intent.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_05_logged_in_submit_intent.png)

---

### 5.2 负面与边界用例（Negative & Boundary）

#### C-005-06 · 密码长度 `< 8` 拒绝注册
- **操作步骤**：在 `/register` 填写合法用户名 `acc_t005_short`、手机号 `13800000003`，输入 6 位密码 `short7` 点击「注册」；同时绕过前端向 `POST /api/auth/register` 直传 7 位密码 `short77`。
- **期望结果**：前后端双重拦截拒绝注册，库中不新增记录。
- **实际结果**：前端表单立即红字提示 `密码不少于 8 位`；后端接口直调返回 `HTTP 400 Bad Request`（`code=40001, message="请检查必填字段和输入格式"`）；查库确认未新增 `acc_t005_short`。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：短密码 (<8位) 注册拦截提示 (t005_06_short_password_rejected.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_06_short_password_rejected.png)

#### C-005-07 · 重复用户名拒绝注册
- **操作步骤**：在 `/register` 使用已注册的用户名 `acc_t005_a` 再次提交注册。
- **期望结果**：拒绝注册并提示用户名已存在。
- **实际结果**：后端返回 `HTTP 409 Conflict`（`code=40901, message="用户名已存在"`），前端弹出错误提示 `用户名已存在，请更换用户名。`。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：重复用户名注册被拒提示 (t005_07_duplicate_username_rejected.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_07_duplicate_username_rejected.png)

#### C-005-08 · 缺必填字段拒绝（用户名 / 密码 / 电话）
- **操作步骤**：在 `/register` 分别留空手机号、用户名、密码点击「注册」，并直调后端接口传入空手机号 `phone=""`。
- **期望结果**：每次均被拒绝并给出必填提示。
- **实际结果**：前端表单分别显示 `请输入用户名`、`请输入密码`、`请输入手机号` 红字校验错误；直调后端接口返回 `HTTP 400 Bad Request`（`code=40001`）。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：缺少必填字段（用户名/密码/手机号）拦截提示 (t005_08_missing_required_fields.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_08_missing_required_fields.png)

#### C-005-09 · 错误密码 / 不存在用户登录失败
- **操作步骤**：在 `/login` 分别使用 `acc_t005_a` + 错误密码 `WrongPass123!`、不存在的用户名 `non_existent_user_999` + `Passw0rd!` 尝试登录。
- **期望结果**：登录失败，不建立会话，统一返回安全提示而不泄露具体哪个字段错误。
- **实际结果**：两次请求均返回 `HTTP 401 Unauthorized`（`code=40102`），页面弹出 `用户名或密码错误。`，`localStorage` 中未生成 `customer_token`。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：错误密码/不存在用户登录失败提示 (t005_09_login_wrong_credentials.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_09_login_wrong_credentials.png)

#### C-005-10 · 未登录可浏览，但无法提交购买意向
- **操作步骤**：
  1. 清除 `customer_token`（未登录匿名态），访问首页 `/` 与商品详情页 `/products/1`。
  2. 点击详情页上的「提交购买意向」按钮。
  3. 绕过前端，不带 `Authorization` 请求头直接调用 `POST /api/products/1/intents`。
- **期望结果**：匿名可正常浏览列表与详情；点提交意向被前端引导至登录页，且后端接口返回 `401` 拒绝未授权请求。
- **实际结果**：未登录打开 `/products/1` 时按钮下方明确显示 `提交意向前需要登录。`；点击「提交购买意向」后页面立即跳转至 `/login`（携带回跳路由状态 `state.from="/products/1"`）；直调后端接口返回 `HTTP 401 Unauthorized`（`code=40101, message="未登录或登录已过期"`）。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：未登录浏览详情页提示 (t005_10a_unauth_detail_prompt.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_10a_unauth_detail_prompt.png) ｜ [📷 查看截图：未登录点提交跳转登录页及接口 401 验证 (t005_10b_unauth_redirect_login.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_10b_unauth_redirect_login.png)

#### C-005-11 · 界面无口令码入口（注册/登录/详情相关页）
- **操作步骤**：全面巡检 `/register`、`/login`、`/`、`/products/1` 页面 UI 与 DOM 节点。
- **期望结果**：全站移除迭代 1 的口令码输入框、查询口令弹窗及凭口令提交入口。
- **实际结果**：四个页面的 DOM 中匹配 `/口令/` 的文本与输入框数量均为 `0`，意向提交完全基于顾客登录会话（Bearer JWT），符合迭代 2 DoD 要求。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：商品详情页无口令码全貌 (t005_11_no_passphrase_ui.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_11_no_passphrase_ui.png)

---

## 六、证据文件汇总索引

| 序号 | 证据类型 | 关联用例 | 文件链接（点击打开） |
| :---: | :--- | :---: | :--- |
| 1 | 后端 JUnit 测试终端截图 | JUnit 基线 | [t005_00_junit_test_pass.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_00_junit_test_pass.png) |
| 2 | 注册页填写态截图 | C-005-01 | [t005_01a_register_form.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_01a_register_form.png) |
| 3 | 注册成功跳转登录页截图 | C-005-01 | [t005_01b_register_success.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_01b_register_success.png) |
| 4 | 含选填交易地点注册截图 | C-005-02 | [t005_02_register_with_location.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_02_register_with_location.png) |
| 5 | 登录页表单截图 | C-005-03 | [t005_03a_login_form.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_03a_login_form.png) |
| 6 | 登录成功后首页会话态截图 | C-005-03 | [t005_03b_login_success.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_03b_login_success.png) |
| 7 | 数据库 `customer` 表 BCrypt 哈希核验截图 | C-005-04 | [t005_04_db_password_hash.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_04_db_password_hash.png) |
| 8 | 登录后成功提交购买意向截图 | C-005-05 | [t005_05_logged_in_submit_intent.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_05_logged_in_submit_intent.png) |
| 9 | 密码长度 `< 8` 拦截提示截图 | C-005-06 | [t005_06_short_password_rejected.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_06_short_password_rejected.png) |
| 10 | 重复用户名拒绝注册截图 | C-005-07 | [t005_07_duplicate_username_rejected.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_07_duplicate_username_rejected.png) |
| 11 | 缺必填字段校验提示截图 | C-005-08 | [t005_08_missing_required_fields.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_08_missing_required_fields.png) |
| 12 | 错误密码/不存在用户登录失败截图 | C-005-09 | [t005_09_login_wrong_credentials.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_09_login_wrong_credentials.png) |
| 13 | 未登录浏览商品详情提示截图 | C-005-10 | [t005_10a_unauth_detail_prompt.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_10a_unauth_detail_prompt.png) |
| 14 | 未登录点提交意向跳转登录页截图 | C-005-10 | [t005_10b_unauth_redirect_login.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_10b_unauth_redirect_login.png) |
| 15 | 详情页无口令码入口全貌截图 | C-005-11 | [t005_11_no_passphrase_ui.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t005/t005_11_no_passphrase_ui.png) |
| 16 | 结构化测试执行数据 JSON | 全部用例 | [t005-t009-acceptance-results.json](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/t005-t009-acceptance-results.json) |

---

## 七、Sprint Review 汇报一行汇总与禅道回写

| Task | PB | 禅道子需求 | 执行日期 | 验收结果 | 通过/总数 | 发现缺陷数 | 证据位置 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **T-005** | **PB-04** | **13928** | 2026-10-27 | ☑ **通过** | **11 / 11**（JUnit 21/21） | **0**（无阻塞或功能缺陷） | `docs/test/T-005-acceptance-report.md` 及 `screenshots/t005/` |
