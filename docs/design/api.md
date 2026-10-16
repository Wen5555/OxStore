# 交易与记录接口说明

本文说明当前交易确认、队列及历史记录契约。整体领域模型见[数据库设计](database.md)，其他功能接口见后端Controller及[项目Wiki](https://github.com/Wen5555/OxStore/wiki)。

## 通用约定

- 接口前缀为`/api`，JSON响应使用`{ code, message, data }`，`code=0`表示成功。
- 卖家接口除登录外需要`Authorization: Bearer <JWT>`。
- 买家凭口令只可访问本人意向；公开商品接口不返回买家信息。
- 图片通过`/api/images/{filename}`访问。发布商品使用multipart字段`name/description/price/image`，服务端生成imagePath。
- 历史列表分页从`page=0`开始，默认`size=10`。

## 队列与交易确认

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /api/admin/intents | 返回当前交易中意向及排队队列 |
| POST | /api/admin/intents/{id}/start | 开始处理队首意向 |
| POST | /api/admin/intents/{id}/success | 确认当前交易尝试成功 |
| POST | /api/admin/intents/{id}/fail | 确认失败，选择REQUEUE或DISCARD |

开始交易保持空data响应，随后刷新队列获取`currentTradeAttemptId`。确认成功时发送：

```json
{ "tradeAttemptId": 12 }
```

确认失败时发送：

```json
{ "action": "REQUEUE", "tradeAttemptId": 12 }
```

`DISCARD`将意向作废并使口令失效；`REQUEUE`将意向放到队尾，保留原口令与首次提交时间。失败后自动递补，响应data为新交易中意向，队列为空时为null。

缺少尝试ID返回400；重复或延迟提交已经结束的尝试ID返回409，调用方应刷新队列。商品成功售出后，其余排队意向为UNSOLD，全部相关口令失效。买家撤销也使本人意向口令失效。

## 后台记录

| 方法 | 路径 | 返回范围 |
| --- | --- | --- |
| GET | /api/admin/products/{id}/records | 任意业务状态商品的完整记录 |
| GET | /api/admin/products/history/{id} | 仅SOLD商品的历史详情 |

记录响应包含：

- `product`：商品及最近状态时间。
- `intents`：意向、首次提交时间和最近处理时间。
- `tradeAttempts`：每次开始/结束时间、结果及失败动作。
- `statusEvents`：按时间及ID排列的商品状态事件。
- `legacyRecordsMayBeIncomplete/historyCompleteSince`：旧库历史完整性说明。

`IntentResponse.currentTradeAttemptId`仅在后台交易中意向及自动递补响应中提供。`processedAt`是最近一次意向处理时间，历次结果由tradeAttempts保存；`submittedAt`是首次提交时间。内部`queue_seq`用于排序，动态位次从1起，交易中的后台队列位次为0。

未结束交易尝试的`finishedAt/result/failAction`均为null。一个意向可以经历多次尝试，先前的失败不会因重排或后来成交而覆盖。失败恢复在售和自动递补再次冻结在同一事务中分别保存事件。

## 验证范围

[数据库验证报告](../test/db-validation.md)记录了实际HTTP、迁移和历史保留结果。完整UI验收及所有接口的性能需另行验证；已售商品裸图片URL的买家访问范围仍需统一需求口径。
