# B-036 独立验收包 · 真实前后端 V01～V09 界面与主链路

> 结论（2026-11-21，SUT `develop@29c20ea`）：**12 个真实浏览器流程全部通过**，截图 14 张；
> 79 AC 汇总见 [coverage-79.json](./coverage-79.json)：**76 PASS / 3 FAIL**。
> 3 条 FAIL 是 B-031/B-032 已发现、尚未关闭的缺陷（B08-AC1、B09-AC1、B13-AC2），
> 本包不掩盖，交由 B-037 复验、B-040 收口。

## 被测栈

| 项 | 值 |
|---|---|
| SUT | `develop@29c20ea0927528a98f873f4a1a0e169a6fa12281` |
| 前端 | Vite dev server `http://127.0.0.1:5173`（代理 `/api` → `:8080`） |
| 后端 | Spring Boot `:8080`，DB `oxstore_test_b036` |
| 浏览器 | 系统 Chrome（Playwright `channel=chrome`，headless），非 Mock |
| 数据 | B-030 `prepare_fixtures.py` 创建 B030-* 商品与 b030_* 客户 |

## 结果

| 证据 | 内容 |
|---|---|
| [evidence/ui-steps.json](./evidence/ui-steps.json) | 12 步的 PASS/FAIL、耗时、关键断言 |
| [evidence/screenshots/](./evidence/screenshots/) | 01 列表、02 详情、03 购物车、04 转收藏确认、05 收藏、06 下单确认、07 下单成功、08 取消后历史、09/10 商家商品/库存、11 商家订单、12 交易完成历史、13/14 旧意向归档 |
| [coverage-79.json](./coverage-79.json) | 79 AC ↔ 证据包（B-031～B-036）↔ UI 流程 |

## 12 个真实流程

1. **V01 列表**：搜索框存在；商品卡片无「加入购物车/收藏」快捷入口（断言为 false）。
2. **V01 登录**：买家 UI 登录成功自动回首页。
3. **V01 详情**：加入购物车 1 件、收藏→按钮变「取消收藏」；无「立即购买」。
4. **V03 购物车**：两行；按数量输入框改 2 并「更新数量」提示「已更新」。
5. **V09 转收藏**：勾选 2 行 → 二次确认文案「所选 2 件商品将从购物车移除并加入收藏」→ 成功「已收藏 2 件商品」。
6. **V02 收藏**：列表 2 项；取消收藏无二次确认、立即移除。
7. **V04/V05 下单**：确认弹窗展示清单/金额 → 成功弹窗含订单号与「查看订单详情」。
8. **V05 取消**：历史行「取消订单」→ 二次确认（原因选填）→ 状态变「已取消」。
9. **V06 商家推进**：商家登录 → 确认订单 → 完成备货 → 开始发货 → 完成交易，状态逐级正确。
10. **V05 完成态**：历史显示「交易完成」；完成行**不再显示**「取消订单」；页面无「缺货/无货/超限/下单历史」。
11. **V07 库存**：`-1` 触发表单校验「库存不能为负数，请输入非负整数。」；改正 5 保存提示「商品信息已更新」；有「手动下架」入口。
12. **V10 旧意向归档**：客户/商家两页均为「旧意向归档」，客户页含「只读归档」列。

## 复现

```powershell
# 1) 后端 :8080 指向 oxstore_test_b036；前端 5173
cd docs/iterationB/B-030-本轮验收用例
$env:B030_BASE_URL="http://127.0.0.1:8080"; $env:B030_DB_NAME="oxstore_test_b036"
python scripts/prepare_fixtures.py
# 2) 真实浏览器（Node 24 + 系统 Chrome）
cd ../../../OxStore-sut/frontend
node <repo>/docs/iterationB/B-036-验收执行/scripts/b036_ui.mjs
```

## 环境事实

- `@playwright/test@1.63` 要求 Node ≥20，本机默认 Node 18；改用 DSH 自带 Node 24 运行。
- 受限 sandbox 会阻止 Chrome 启动与 Vite 的 esbuild 子进程（`spawn EPERM`），本包运行需要 full-access。
- Vite dev server 需先启动；Playwright 脚本直接连 5173，不使用仓库 e2e 的 Mock 配置。
