# B-037 独立验收包 · 固定提示 / 持久化 / 安全负例

> 结论（2026-11-21，SUT `develop@29c20ea`）：6 个检查 / **5 通过 / 1 失败**，42 合取。
> B-031 遗留的 B08-AC1、B09-AC1 已复验通过；B-032 遗留的 **PB-B13-AC2（结算余数）仍失败**，
> 记为开放缺陷，交 B-011，B-040 不得把它算作通过。

## 范围

| 检查 | 内容 | 结果 |
|---|---|---|
| FIXED-PROMPTS | 26 条固定提示原文 + 废弃文案扫描 + 零副作用 | PASS |
| B08-AC1-REVERIFY | 收藏匿名/失效/商家/跨客户隔离 | PASS |
| B09-AC1-REVERIFY | 下架收藏保留并标「已下架」，恢复在售后有效 | PASS |
| B13-AC2-REVERIFY | 公开 API 复现「锁后加购保留余数」 | **FAIL（开放缺陷）** |
| PERSISTENCE-SETUP | 重启前写入收藏/购物车/订单并保存 token | PASS |
| PERSISTENCE-RESTART | 杀进程重启后同一 token、同一行、同一库存仍在 | PASS |

## 固定提示（实测原文）

- 认证：`请先登录`、`请重新登录`、`请先登录`（后台匿名）、`角色无权访问`
- 订单：`订单已取消`、`订单已开始发货，不可取消`、`订单已完成，不可取消`、
  `订单状态已变化，请刷新后重试`、`不支持部分取消`、`订单不存在`、`无权操作该订单`
- 购物车/结算：`商品已下架`、`商品不存在`、`数量无效，请输入正整数`、`已移除`、
  `该商品已不在购物车，请刷新页面后查看。`、`请选择商品`、
  `库存不足：当前可售 1 件，您选购了 2 件`（confirm 返回 409，明细在 data.errors）
- 幂等：`订单已提交，请勿重复下单`、`请勿重复操作`
- 库存：`库存不能为负数，请输入非负整数。`
- 旧意向：`一口价旧购买意向已关闭，请通过购物车下单`；旧队列 GET 已无路由（405）
- 全量响应扫描：无 `缺货 / 无货 / 超限 / 下单历史`

## B13-AC2 开放缺陷

- 复现：购物车 2 件 → 确认 → 改为 3 件 → 提交；提交返回 409（要求重新确认），
  因此没有「订单 2 件 + 购物车余 1 件」的公开可观察结果。
- 与 B-032（`remainder_gt0_via_public_api` FAIL）一致，两轮都无法用公开 API 证明「锁定后加购保留余数」。
- 影响：PB-B13-AC2 不能判通过；建议 B-011 提供受控延迟/测试钩子或在契约中明确可观察窗口。
- 证据：[evidence/results.json](./evidence/results.json)、`evidence/results-main.json`。

## 持久化重启

- 重启前：token、favoriteId、cartItemId、orderId、P-ON-10 库存写入 `runs/state.json`（gitignore）。
- 重启方式：结束 `:8083` 进程 → 同 DB 重新 `java -jar` → 健康检查 200。
- 重启后：不重新登录，收藏列表含原 favoriteId、购物车含原 cartItemId、订单历史含原 orderId，
  商品库存不变。

## 复现

```powershell
cd docs/iterationB/B-030-本轮验收用例
$env:B030_BASE_URL="http://127.0.0.1:8083"; $env:B030_DB_NAME="oxstore_test_b037"
python scripts/prepare_fixtures.py
cd ../B-037-验收执行
python scripts/run_checks.py --phase main
# 结束 :8083 后端并以同一 DB 重启
python scripts/run_checks.py --phase persist
```

## 环境事实

- 商家 token 调用客户接口实际返回 `403 角色无权访问`（不是 `无此权限`）；用 `无此权限` 的是转收藏接口，按真实契约断言。
- 后台匿名访问 `/api/admin/orders` 返回 `401 请先登录`（`请先登录后台` 出现在取消等写操作），本包分别覆盖。
- 旧队列 GET 已移除（405），旧意向数据只能走 `/api/me|admin/legacy-intents` 只读归档。
