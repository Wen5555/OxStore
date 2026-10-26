# 迭代 2 API 说明

本文描述当前后端 API。接口前缀为 `/api`；成功响应格式为 `{ "code": 0, "message": "ok", "data": ... }`。错误响应使用统一错误码和消息，详见 `ErrorCode`。

## 身份与分页

- 顾客通过 `/api/auth/register`、`/api/auth/login` 注册/登录；卖家通过 `/api/admin/auth/login` 登录。
- 登录返回 `token`、`userId`、`role`、`username`。受保护接口使用 `Authorization: Bearer <token>`；卖家接口要求 `SELLER`，顾客个人数据和购买意向接口要求 `CUSTOMER`。
- 分页参数从 `page=1` 开始，默认 `size=10`。分页结果结构为 `{ items, page, size, total, pages }`。
- 日期时间为 `Asia/Shanghai` 本地业务时间，格式由 JSON 序列化为 ISO 日期时间字符串。

## 顾客与卖家认证

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | 公开 | 顾客注册，字段：`username`、`password`、`phone`、`location`（可选） |
| POST | `/api/auth/login` | 公开 | 顾客登录，字段：`username`、`password` |
| POST | `/api/admin/auth/login` | 公开 | 卖家登录，字段：`username`、`password` |
| PUT | `/api/admin/auth/password` | SELLER | 修改卖家密码 |

顾客注册密码长度为 8–64；用户名最长 50 字符，电话最长 20 字符，地址可选且最长 200 字符。卖家改密请求使用 `oldPassword` 与 `newPassword`。

## 分类、商品和图片

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/categories/tree` | 公开 | 获取二级分类树 |
| GET | `/api/products` | 公开 | 在售商品分页浏览；可传 `category2Id`、`q`、`page`、`size` |
| GET | `/api/products/{productId}` | 公开 | 商品详情；在线商品可购买，冻结商品只读 |
| GET | `/api/images/{filename}` | 公开 | 读取商品图片 |
| GET | `/api/admin/products` | SELLER | 卖家商品分页列表 |
| POST | `/api/admin/products` | SELLER | multipart 新建商品 |
| PATCH | `/api/admin/products/{productId}` | SELLER | 修改 `stock` 和/或 `category2Id` |
| POST | `/api/admin/products/{productId}/online` | SELLER | 手动上架 |
| POST | `/api/admin/products/{productId}/offline` | SELLER | 手动下架并作废排队意向 |

新建商品的 multipart 字段：`name`、`price`、`category2Id`、`stock`、可选 `descriptionHtml` 和 0–9 张 `images`（也接受 `images[]`）。单张图片上限 5 MiB；描述经过 HTML 白名单清理。反向代理与后端上传请求上限须允许总请求体 46 MiB。

商品详情含 `productId`、名称、价格、二级分类、库存、清洗后的 `descriptionHtml`、图片路径列表、主图、状态、`canPurchase` 及发布时间/状态更新时间。库存必须大于等于 0；库存为 0 时不能上架。补充库存不会自动上架。

## 购买意向与交易队列

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/products/{productId}/intents` | CUSTOMER | 为在售商品提交购买意向 |
| GET | `/api/admin/intents?productId=...` | SELLER | 查询指定商品的分页队列 |
| POST | `/api/admin/intents/{id}/start` | SELLER | 开始处理意向 |
| POST | `/api/admin/intents/{id}/success` | SELLER | 确认交易成功 |
| POST | `/api/admin/intents/{id}/fail` | SELLER | 确认失败 |

一个意向对应购买 1 件；重复提交同一顾客同一商品的排队意向会冲突。开始交易和成功确认不需要请求体。失败请求体：

```json
{ "action": "REQUEUE" }
```

`REQUEUE` 将意向移到该商品队尾，不自动开始下一笔；`DISCARD` 使意向终结并生成失败历史。成功确认会在事务中扣减 1 件库存并生成订单历史；库存仍大于 0 时商品回到 `ONLINE`，不会自动开始下一笔。库存归零时商品下架，剩余队列意向均作废为失败并生成历史。手动下架也会作废该商品排队意向。

商品状态为 `ONLINE`、`FROZEN`、`OFFLINE`；意向状态为 `QUEUING`、`IN_TRANSACTION`、`SUCCESS`、`FAILED`。`REQUEUE` 后继续为 `QUEUING`，不产生终态历史。新 API 不提供口令码查询/管理接口。

## 购买历史与顾客管理

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/me/order-history` | CUSTOMER | 当前顾客的成功/失败购买历史分页 |
| GET | `/api/admin/customers` | SELLER | 顾客分页列表 |
| GET | `/api/admin/customers/{customerId}/order-history` | SELLER | 指定顾客的购买历史分页 |

历史记录由终态快照提供，包含 `orderId`、`productName`、`submittedAt`、`status`、`transactedAt`。注册前旧口令码时代的顾客身份和意向不会显示在新顾客历史中。

## 数据库升级

空库按 [数据库说明](database.md#5-首次建库) 导入 `schema.sql`。旧库必须先备份并在副本演练；按 [运行手册](../runbook.md#已有数据库升级) 执行所需的 V2、V3 前置迁移及 V4 迭代 2 迁移。
