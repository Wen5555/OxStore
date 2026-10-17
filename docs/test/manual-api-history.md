
# OxStore 手工 API 操作历史记录

本页保留原有手工请求与截图记录，样例参数和旧响应不作为当前自动化契约。现行步骤见[自动化执行手册](automation_runbook.md)，响应以当前接口与实测为准。

## 1. 测试概述

### 1.1 测试方式

本记录采用**手动 API 测试 + 截图记录**的方式保存历史操作，适用于：

- 无需编写和维护测试代码

- 快速验证后端 API 功能

- 直观展示测试执行过程（用于交付成果物）

### 1.2 测试工具

| 工具 | 用途 | 版本要求 |
|:---|:---|:---|
| Postman / curl / 浏览器 | 发送 HTTP 请求 | 任意 |
| 截图工具 | 记录请求和响应 | 系统自带 |
| IDE (IntelliJ IDEA) | 启动后端应用 | 2023+ |

### 1.3 测试环境

| 项目 | 配置 |
|:---|:---|
| 数据库 | MySQL（与生产环境一致）|
| 后端地址 | `http://localhost:8080` |
| 测试账号 | admin / Test@1234 |

---

## 2. 环境准备

### 2.1 启动后端服务

1. 打开 IntelliJ IDEA，加载 OxStore 项目

2. 确认 `application.yml` 中数据库配置正确

3. 运行 `ShopApplication.java`

4. 控制台显示 `Started ShopApplication in 2.6 seconds`

### 2.2 验证服务启动

浏览器访问：`http://localhost:8080/api/products/current`

**预期结果**：返回 JSON 格式响应（可能为 `{"code":0,"message":"ok","data":null}`）
**截图**：浏览器显示响应结果

---

## 3. 测试执行步骤

### 测试 1：获取当前商品（无商品）

**请求**：

```http
GET http://localhost:8080/api/products/current

```

**实际结果**：

- 状态码：200 OK

- 响应体：`{ "code": 0, "message": "ok", "data": null }`

- 说明：数据库中尚未发布任何商品，返回 data: null，符合预期

**截图**：`api_01_current_no_product.png`

---

### 测试 2：登录获取 Token

**请求**：

```http
POST http://localhost:8080/api/admin/auth/login
Content-Type: application/json

{ "username": "admin", "password": "Test@1234" }

```

**实际结果**：

- 状态码：200 OK

- 响应体：`{ "code": 0, "data": { "token": "eyJhbGciOiJIUzM4NCJ9...", "username": "admin" } }`

- 说明：卖家密码正确，登录接口成功返回 JWT Token

**截图**：`api_02_login_success.png`

---

### 测试 3：发布商品

**请求**：

```http
POST http://localhost:8080/api/admin/products
Authorization: Bearer {token}
Content-Type: multipart/form-data

name: 测试商品
description: 测试描述
price: 99.99
image: [测试图片]

```

**实际结果**：

- 状态码：200 OK

- 响应体：`{ "code": 0, "data": { "id": 1, "imagePath": "...", "status": "ONLINE" } }`

- 说明：商品发布成功，图片上传、后端入库、状态机初始化全部正常

**截图**：`api_03_product_publish_success.png`

---

### 测试 4：获取当前商品（已上线）

**请求**：

```http
GET http://localhost:8080/api/products/current

```

**实际结果**：

- 状态码：200 OK

- 响应体：`{ "code": 0, "data": { "id": 1, "status": "ONLINE", ... } }`

- 说明：买家端能正常看到卖家发布的商品，前后端数据完全互通

**截图**：`api_04_current_online.png`

---

### 测试 5：提交购买意向

**请求**：

```http
POST http://localhost:8080/api/intents
Content-Type: application/json

{
  "buyerName": "张三",
  "buyerPhone": "13800138000"
}

```

**实际结果**：

- 状态码：200 OK

- 响应体：`{ "code": 0, "data": { "lookupCode": "ctCKcaFC", "position": 1, "status": "QUEUING" } }`

- 说明：返回 8 位查询码 `ctCKcaFC`，排队位次为 1，状态为 QUEUING

**截图**：`api_05_intent_submit_success.png`

---

### 测试 6：查看意向队列（排队中）

**请求**：

```http
GET http://localhost:8080/api/admin/intents
Authorization: Bearer {token}

```

**实际结果**：

- 状态码：200 OK

- 响应体：`{ "code": 0, "data": [{ "id": 1, "buyerName": "张三", "status": "QUEUING", "position": 1 }] }`

- 说明：队列中包含张三的意向，id: 1，状态 QUEUING，排队位次 1

**截图**：`api_06_intents_queue_queuing.png`

---

### 测试 7：开始交易

**请求**：

```http
POST http://localhost:8080/api/admin/intents/1/start
Authorization: Bearer {token}

```

**实际结果**：

- 状态码：200 OK

- 响应体：`{ "code": 0, "data": null }`

- 说明：操作执行成功，商品状态变为 FROZEN

**截图**：`api_07_start_trade_success.png`

---

### 测试 8：查看意向队列（交易中）

**请求**：

```http
GET http://localhost:8080/api/admin/intents
Authorization: Bearer {token}

```

**实际结果**：

- 状态码：200 OK

- 响应体：`{ "code": 0, "data": [{ "id": 1, "status": "IN_TRANSACTION", "position": 0, "currentTradeAttemptId": 1 }] }`

- 说明：状态变为 IN_TRANSACTION，position: 0（交易中意向不参与排队），返回 currentTradeAttemptId: 1

**截图**：`api_08_intents_queue_in_transaction.png`

---

### 测试 9：确认成交

**请求**：

```http
POST http://localhost:8080/api/admin/intents/1/success
Authorization: Bearer {token}
Content-Type: application/json

{}

```

**实际结果**：

- 状态码：200 OK

- 响应体：`{ "code": 0, "data": null }`

- 说明：确认成交操作执行成功，商品状态变为 SOLD

**截图**：`api_09_confirm_success.png`

---

### 测试 10：获取当前商品（已售出）

**请求**：

```http
GET http://localhost:8080/api/products/current

```

**实际结果**：

- 状态码：200 OK

- 响应体：`{ "code": 0, "message": "ok", "data": null }`

- 说明：商品已售出，返回 data: null

**截图**：`api_10_current_sold_out_404.png`

---

### 完整业务闭环（端到端）

按顺序执行：测试 1 → 测试 2 → 测试 3 → 测试 4 → 测试 5 → 测试 6 → 测试 7 → 测试 8 → 测试 9 → 测试 10

**流程验证**：

1. 初始状态：无商品 → data: null

2. 卖家登录：获取 JWT Token

3. 发布商品：商品上线，status: ONLINE

4. 买家查看：能看到商品

5. 提交意向：生成查询码 ctCKcaFC，排队位次 1

6. 查看队列：意向状态 QUEUING

7. 开始交易：商品冻结，意向状态 IN_TRANSACTION

8. 查看队列：显示交易中，返回 tradeAttemptId

9. 确认成交：交易完成，商品售出

10. 最终状态：商品已售出，data: null

**BUG-001 验证**：交易中意向未从队列消失，卖家能获取 id 和 currentTradeAttemptId，递补和确认流程无死锁。

---

## 4. 截图整理规范

### 4.1 命名规则
api_01_current_no_product.png api_02_login_success.png api_03_product_publish_success.png api_04_current_online.png api_05_intent_submit_success.png api_06_intents_queue_queuing.png api_07_start_trade_success.png api_08_intents_queue_in_transaction.png api_09_confirm_success.png api_10_current_sold_out_404.png

### 4.2 存放位置
docs/test/screenshots/

---

## 5. 测试报告

### 5.1 报告内容

将截图按顺序插入 Word/PPT/PDF 文档，每页包含：
- 测试用例编号和名称
- 请求方法、URL、参数
- 响应状态码和结果
- 测试结论（通过/失败）

### 5.2 报告模板

| 用例编号 | 用例名称 | 请求 | 预期结果 | 实际结果 | 截图 | 结论 |
|:---|:---|:---|:---|:---|:---|:---:|
| TC-API-PROD-02 | 获取当前商品（无商品） | GET /api/products/current | 200, data: null | 200, data: null | api_01_current_no_product.png | ✅通过 |
| TC-API-AUTH-01 | 正确账号密码登录 | POST /api/admin/auth/login | 200, 返回token | 200, token=eyJhbGciOiJIUzM4NCJ9... | api_02_login_success.png | ✅通过 |
| TC-API-PROD-01 | 发布商品 | POST /api/admin/products | 200, 返回商品ID | 200, id: 1, status: ONLINE | api_03_product_publish_success.png | ✅通过 |
| TC-API-PROD-03 | 获取当前商品（已上线） | GET /api/products/current | 200, 商品详情 | 200, id: 1, status: ONLINE | api_04_current_online.png | ✅通过 |
| TC-API-INTENT-01 | 提交购买意向 | POST /api/intents | 200, 返回查询码 | 200, lookupCode: ctCKcaFC, position: 1 | api_05_intent_submit_success.png | ✅通过 |
| TC-API-INTENT-03 | 查看意向队列（排队中） | GET /api/admin/intents | 200, QUEUING | 200, id: 1, status: QUEUING, position: 1 | api_06_intents_queue_queuing.png | ✅通过 |
| TC-API-TRADE-01 | 开始交易 | POST /api/admin/intents/1/start | 200 | 200, data: null | api_07_start_trade_success.png | ✅通过 |
| TC-API-INTENT-03 | 查看意向队列（交易中） | GET /api/admin/intents | 200, IN_TRANSACTION | 200, id: 1, status: IN_TRANSACTION, currentTradeAttemptId: 1 | api_08_intents_queue_in_transaction.png | ✅通过 |
| TC-API-TRADE-02 | 确认成交 | POST /api/admin/intents/1/success | 200 | 200, data: null | api_09_confirm_success.png | ✅通过 |
| TC-API-PROD-02 | 获取当前商品（已售出） | GET /api/products/current | 200/404, data: null | 200, data: null | api_10_current_sold_out_404.png | ✅通过 |

---

## 6. 故障排查

### 6.1 无法连接后端

- 检查 IDEA 控制台，确认服务已启动
- 检查端口是否为 8080
- 检查防火墙设置

### 6.2 登录返回 401

- 确认账号密码正确（admin / Test@1234）
- 确认数据库已初始化 admin 账号
- 检查 `DataInitializer` 是否执行（控制台应有日志）

### 6.3 接口返回 403

- 确认请求头包含 `Authorization: Bearer {token}`
- 确认 token 未过期

---

## 7. 交付物清单

| 序号 | 交付物 | 形式 | 位置 |
|:---|:---|:---|:---|
| 1 | 测试用例设计及清单 | Markdown 文档 | `docs/test/test_case_design_and_inventory.md` |
| 2 | 测试执行截图 | PNG 图片（10张） | `docs/test/screenshots/` |

---

> 本文档与测试执行过程同步维护。新增功能时，请同步添加对应的 API 测试截图。
