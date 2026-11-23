# B-037 独立验收包 · 固定提示 / 持久化 / 安全负例

> 结论（2026-11-21 原始执行，2026-11-23 缺陷复验）：6 个检查 / **6 通过 / 0 失败**，48 合取。
> B-031 遗留的 B08-AC1 已复判 PASS、B09-AC1 由 B-036 真实浏览器复验（D-002 关闭）；
> B-032 遗留的 **PB-B13-AC2 已由 R1 受控测试钩子复验通过（D-001 关闭）**。
>
> D-001 复验使用 `develop@ebe3f32`（PR #36 测试类），R2 在独立 MySQL `oxstore_test_d001` 执行，
> 不是只看 R1 的结论；判定依据为 B-000 §8「锁后加购串行至提交之后，新增量保留」。

## 范围

| 检查 | 内容 | 结果 |
|---|---|---|
| FIXED-PROMPTS | 26 条固定提示原文 + 废弃文案扫描 | PASS |
| B08-AC1-REVERIFY | 收藏匿名/失效/商家/跨客户隔离 | PASS |
| B09-AC1-REVERIFY | 下架收藏保留并标「已下架」，恢复在售后有效 | PASS（API） |
| B13-AC2-CONTROLLED | 锁后加购受控复验（R2 独立执行 R1 测试钩子） | PASS |
| PERSISTENCE-SETUP | 重启前写入收藏/购物车/订单并保存 token | PASS |
| PERSISTENCE-RESTART | 杀进程重启后同一 token、同一行、同一库存仍在 | PASS |

> B09-AC1 的“点击失效收藏提示已下架”属于页面行为：B-031 原判 FAIL，PR #35 修复后
> 由 B-036 在 `ebe3f32` + 真实 Chrome 复验 toast=「已下架」，见
> [B-036 d002 证据](../B-036-验收执行/evidence/d002-ui-retest.json)。

## D-001（PB-B13-AC2）受控复验

- 测试类：`ChallengeBCheckoutPublicApiConcurrencyTest`（PR #36，仅测试钩子，无生产代码改动）。
- 环境：MySQL 8.0 `oxstore_test_d001`，`schema.sql` 空库导入，`ddl-auto=none`；随机端口真实 HTTP。
- 命令：`mvn -B -Dtest=ChallengeBCheckoutPublicApiConcurrencyTest test`。
- 结果：`Tests run: 2, Failures: 0, Errors: 0, Skipped: 0`，BUILD SUCCESS。
- 观察：
  - 锁后加购：提交已持锁时加购进入服务并等待；提交 201、订单 qty=2、同商品新行 qty=1、库存 3；原键重试 40909。
  - 锁前改量：提交 409/40913「确认信息已变化，请重新确认」，车内 3 件、无订单、库存 5。
- 口径：B-000 §8 允许锁后加购在提交后保留为新行，不要求沿用旧 `cartItemId`；“余数”按同一商品最终数量判定。
- 证据：[evidence/d001/](./evidence/d001/)、[evidence/results.json](./evidence/results.json)。

## 固定提示（实测原文）

- 认证：`请先登录`、`请重新登录`、`请先登录`（后台匿名）、`角色无权访问`
- 订单：`订单已取消`、`订单已开始发货，不可取消`、`订单已完成，不可取消`、
  `订单状态已变化，请刷新后重试`、`不支持部分取消`、`订单不存在`、`无权操作该订单`
- 购物车/结算：`商品已下架`、`商品不存在`、`数量无效，请输入正整数`、`已移除`、
  `该商品已不在购物车，请刷新后查看。`、`请选择商品`、
  `库存不足：当前可售 1 件，您选购了 2 件`（confirm 返回 409，明细在 data.errors）
- 幂等：`订单已提交，请勿重复下单`、`请勿重复操作`
- 库存：`库存不能为负数，请输入非负整数。`
- 旧意向：`一口价旧购买意向已关闭，请通过购物车下单`；旧队列 GET 已无路由（405）
- 全量响应扫描：无 `缺货 / 无货 / 超限 / 下单历史`

## 持久化重启

- 重启前：token、favoriteId、cartItemId、orderId、P-ON-10 库存写入 `runs/state.json`（gitignore）。
- 重启方式：结束 `:8083` 进程 → 同 DB 重新 `java -jar` → 健康检查 200。
- 重启后：不重新登录，收藏列表含原 favoriteId、购物车含原 cartItemId、订单历史含原 orderId，
  商品库存不变。

## 复现

```powershell
# 1) 固定提示/安全/B08/B09
cd docs/iterationB/B-030-本轮验收用例
$env:B030_BASE_URL="http://127.0.0.1:8083"; $env:B030_DB_NAME="oxstore_test_b037"
python scripts/prepare_fixtures.py
cd ../B-037-验收执行
python scripts/run_checks.py --phase main
# 2) 重启后端后
python scripts/run_checks.py --phase persist
# 3) D-001 受控测试（独立库）
mvn -B -Dtest=ChallengeBCheckoutPublicApiConcurrencyTest test   # 需 MySQL URL/密码
```

## 环境事实

- 商家 token 调用客户接口实际返回 `403 角色无权访问`（不是 `无此权限`）；`无此权限` 出现在转收藏接口，按真实契约断言。
- 后台匿名访问 `/api/admin/orders` 返回 `401 请先登录`（`请先登录后台` 出现在取消等写操作），本包分别覆盖。
- 旧队列 GET 已移除（405），旧意向数据只能走 `/api/me|admin/legacy-intents` 只读归档。
- 受控测试需要 MySQL 时通过 `JAVA_TOOL_OPTIONS=-Dchallengeb.jdbc.url=...` 传参数，避免 cmd 把 URL 中的 `&` 拆开。
