# T-027 验收测试成果报告 · 手动上下架、可编辑范围和队列清理

> **交付物说明**：本报告为迭代 2（Sprint 1）任务 **T-027** 的独立验收成果文档，涵盖 **JUnit 后端自动化基线验证** 与 **黑盒验收测试（页面 UI + 后端 API）** 全流程实测结果。所有截图与运行证据均采用超链接方式索引，不在正文内嵌大图，保持版面整洁易读。

---

## 一、任务元信息与总体结论

| 维度 | 详情 |
| :--- | :--- |
| **任务编号 (Task ID)** | **T-027** |
| **关联产品待办 (PB / US)** | **PB-06 / US-06** 手动下架与发布后字段编辑范围 |
| **禅道追踪编号** | 子需求 **13936**（父需求 = **13906**，所属模块：`/卖家商品管理`；项目任务 **#22227**） |
| **验收负责人** | R2 彭燕（PO / 独立验收测试） |
| **执行时间** | 2026-10-28 22:08 – 22:19（Asia/Shanghai，UTC+8） |
| **被测代码基线** | `Wen5555/OxStore` `main` 分支（Commit: `57cb5d3` / `57cb5d317d2549cdfbce4f4f1957e7a7ed662286`） |
| **验收依据** | `docs/iteration2/product-backlog.md` US-06（AC1～AC9 & How to demo）、`requirements-specification.md` §5.2.4 |
| **JUnit 自动化测试结果** | ✅ **PASS（23 / 23 全部通过，0 失败 / 0 错误 / 0 跳过）** · [📷 查看 JUnit 运行截图](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_00_junit_test_pass.png) |
| **黑盒验收用例结果** | ✅ **PASS（7 / 7 全部通过，含 5 条主路径 + 2 条边界/负面用例）** |
| **综合验收结论** | ✅ **通过（PASS）—— 满足 Sprint 1 Definition of Done (DoD) 全部验收标准，可进入 Sprint Review 演示** |

---

## 二、测试环境与前置核验

### 2.1 运行环境配置

| 组件 | 实测版本 / 配置 | 状态 |
| :--- | :--- | :---: |
| **JDK / Maven** | Eclipse Temurin OpenJDK `17.0.21` / Apache Maven `3.9.9` | 通过 |
| **后端服务** | Spring Boot `3.2.5`（监听 `http://127.0.0.1:8080`，H2 文件库兼容模式 + JWT） | 通过 |
| **前端服务** | React `18` + Vite `5.4.21` + Ant Design `5`（监听 `http://127.0.0.1:5173`，代理 `/api`） | 通过 |
| **数据库引擎** | H2 文件库 `MODE=MySQL`（覆盖迭代 2 完整表结构，与 T-005/T-009 验收库模式一致） | 通过 |
| **浏览器引擎** | Google Chrome / Playwright Chromium（视口 `1280×800 @2x`） | 通过 |

### 2.2 测前环境检查单（E1～E5）

| 编号 | 检查项 | 结果 | 核验说明 |
| :---: | :--- | :---: | :--- |
| **E1** | 后端上下架与受限编辑接口可用 |  通过 | `offline`/`online`/`PATCH` 库存类目接口正常 |
| **E2** | 前端商品维护页可用 |  通过 | `/admin/products/{id}/edit` 展示「只能修改库存和二级类目」 |
| **E3** | 可构造在售且无交易中的商品 |  通过 | 测试商品可手动下架 |
| **E4** | 可构造交易中商品验证禁止下架 |  通过 | 队首进入 `IN_TRANSACTION` 后下架返回 40901 |
| **E5** | 买家端可验证下架后不可见 |  通过 | 列表与详情均拒绝已下架商品 |

---

## 三、JUnit 后端自动化测试结果（第一部分）

在开展页面黑盒验收前，先执行后端 Maven JUnit 自动化测试套件，验证后端接口契约与业务服务层逻辑：

- **执行命令**：`mvn -B -f backend/pom.xml test`
- **总体统计**：共运行 **10 个测试类、23 项测试方法**，**通过 23 项，失败 0 项，错误 0 项，跳过 0 项（BUILD SUCCESS）**。
- **运行截图与日志**：
  - [📷 查看截图：Maven JUnit 自动化测试全绿终端输出 (t027_00_junit_test_pass.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_00_junit_test_pass.png)
  - [📄 查看原始日志：mvn_test_clean.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2-r2-20261028/mvn_test_clean.log)
  - [📄 查看 Playwright E2E 日志：playwright_e2e_output.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2-r2-20261028/playwright_e2e_output.log)

### 3.1 JUnit 测试类与 T-027 关联核对

| 测试类 | 用例数 | 与本任务的关联验证内容 | 结果 |
| :--- | :---: | :--- | :---: |
| `Iteration2ApiIntegrationTest` | 3 | 覆盖注册登录、类目/搜索、独立队列、库存扣减、历史终态、图片/富文本等主流程 | ✅ PASS |
| `TradeServiceImplTest` | 4 | 交易成功/失败、库存与队列状态机 | ✅ PASS |
| `IntentStateMachineTest` / `ProductStateMachineTest` | 1+3 | 意向与商品状态流转合法性 | ✅ PASS |
| `ImageStorageServiceTest` | 1 | 图片格式/内容/大小校验 | ✅ PASS |
| `TradeHistoryTest` | 3 | 终态历史快照约束 | ✅ PASS |
| 其他（Jwt/DTO/Exception/Admin） | 8 | 鉴权、参数校验与权限隔离 | ✅ PASS |

> **说明**：前端仓库自带的 5 项 Playwright E2E 回归测试亦全部通过（`5 passed`）。

---

## 四、黑盒验收测试结果总览（第二部分：UI + API）

### 4.1 验收清单总表（C-027-01 ～ C-027-07）

| 用例编号 | 类别 | 用例名称 | 对应验收点 | 实测结果 | 截图证据链接（点击查看） |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **C-027-01** | 主路径 | 在售且无交易中可手动下架 | PB-06 AC1 |  通过 | [📷 t027_01a_edit_page_before_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_01a_edit_page_before_offline.png) · [📷 t027_01b_admin_shows_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_01b_admin_shows_offline.png) |
| **C-027-02** | 主路径 | 手动下架后买家不可见不可开详情 | PB-06 AC2 |  通过 | [📷 t027_02a_list_hides_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_02a_list_hides_offline.png) · [📷 t027_02b_detail_blocked.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_02b_detail_blocked.png) |
| **C-027-03** | 主路径 | 库存>0 可手动上架回在售 | PB-06 AC3 |  通过 | [📷 t027_03_manual_online.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_03_manual_online.png) |
| **C-027-04** | 主路径 | 发布后仅可编辑库存与二级类目 | PB-06 AC4/AC5 |  通过 | [📷 t027_04_edit_scope_stock_category_only.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_04_edit_scope_stock_category_only.png) |
| **C-027-05** | 主路径 | 库存 0 改正数仍保持下架 | PB-06 AC8 |  通过 | [📷 t027_05_restock_keeps_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_05_restock_keeps_offline.png) |
| **C-027-06** | 负面/边界 | 手动下架队内未成交意向置 FAILED | PB-06 AC9 |  通过 | [📷 t027_06_offline_queue_failed.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_06_offline_queue_failed.png) |
| **C-027-07** | 负面/边界 | 交易中不可手动下架 | PB-06 AC1 |  通过 | [📷 t027_07_cannot_offline_in_transaction.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_07_cannot_offline_in_transaction.png) |

---

## 五、逐条用例执行详情与证据核验

### 5.1 主路径用例（Happy Path）

#### C-027-01 · 在售且无交易中可手动下架
- **对应验收点**：PB-06 AC1
- **操作步骤**：在维护页点击「手动下架」并确认
- **期望结果**：转为 OFFLINE
- **实际结果**：买家详情 40401；管理端状态 OFFLINE。（补充：buyer=404 admin=OFFLINE）
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t027_01a_edit_page_before_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_01a_edit_page_before_offline.png) ｜ [📷 查看截图：t027_01b_admin_shows_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_01b_admin_shows_offline.png)

#### C-027-02 · 手动下架后买家不可见不可开详情
- **对应验收点**：PB-06 AC2
- **操作步骤**：检查列表与详情直链
- **期望结果**：列表不含；详情不可查看
- **实际结果**：列表 API 不含该 productId；详情被拦截。（补充：hidden=true）
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t027_02a_list_hides_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_02a_list_hides_offline.png) ｜ [📷 查看截图：t027_02b_detail_blocked.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_02b_detail_blocked.png)

#### C-027-03 · 库存>0 可手动上架回在售
- **对应验收点**：PB-06 AC3
- **操作步骤**：执行手动上架
- **期望结果**：不必重新发布即可在售
- **实际结果**：上架后首页重新可见。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t027_03_manual_online.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_03_manual_online.png)

#### C-027-04 · 发布后仅可编辑库存与二级类目
- **对应验收点**：PB-06 AC4/AC5
- **操作步骤**：打开维护页
- **期望结果**：明确提示名称/价格/描述/图片不可改
- **实际结果**：页面文案「只能修改库存和二级类目…不可原地修改」。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t027_04_edit_scope_stock_category_only.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_04_edit_scope_stock_category_only.png)

#### C-027-05 · 库存 0 改正数仍保持下架
- **对应验收点**：PB-06 AC8
- **操作步骤**：OFFLINE 下 stock 0→5
- **期望结果**：仍 OFFLINE
- **实际结果**：管理端状态保持已下架。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t027_05_restock_keeps_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_05_restock_keeps_offline.png)

### 5.2 负面 / 边界用例

#### C-027-06 · 手动下架队内未成交意向置 FAILED
- **对应验收点**：PB-06 AC9
- **操作步骤**：有排队意向时手动下架
- **期望结果**：意向进入失败历史
- **实际结果**：买家历史出现该商品 FAILED 记录。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t027_06_offline_queue_failed.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_06_offline_queue_failed.png)

#### C-027-07 · 交易中不可手动下架
- **对应验收点**：PB-06 AC1
- **操作步骤**：IN_TRANSACTION 时尝试下架
- **期望结果**：返回 409
- **实际结果**：HTTP 409 / code=40901。（补充：status=409 code=40901）
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t027_07_cannot_offline_in_transaction.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t027/t027_07_cannot_offline_in_transaction.png)

---

## 六、Sprint Review 汇报一行汇总与禅道回写

| Task | PB | 禅道子需求 | 执行日期 | 验收结果 | 通过/总数 | 发现缺陷数 | 证据位置 |
| ---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **T-027** | **PB-06** | **13936** | 2026-10-28 | ☑ **通过** | **7 / 7**（JUnit 23/23） | **0**（无阻塞或功能缺陷） | `docs/test/T-027-acceptance-report.md` 及 `screenshots/t027/` |
