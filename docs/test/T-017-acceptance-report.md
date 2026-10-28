# T-017 验收测试成果报告 · 库存扣减、零库存下架和递补

> **交付物说明**：本报告为迭代 2（Sprint 1）任务 **T-017** 的独立验收成果文档，涵盖 **JUnit 后端自动化基线验证** 与 **黑盒验收测试（页面 UI + 后端 API）** 全流程实测结果。所有截图与运行证据均采用超链接方式索引，不在正文内嵌大图，保持版面整洁易读。

---

## 一、任务元信息与总体结论

| 维度 | 详情 |
| :--- | :--- |
| **任务编号 (Task ID)** | **T-017** |
| **关联产品待办 (PB / US)** | **PB-02 / US-02** 库存与自动下架 |
| **禅道追踪编号** | 子需求 **13920**（父需求 = **13902**，所属模块：`/库存与商品状态`；项目任务 **#22222**） |
| **验收负责人** | R2 彭燕（PO / 独立验收测试） |
| **执行时间** | 2026-10-28 22:08 – 22:19（Asia/Shanghai，UTC+8） |
| **被测代码基线** | `Wen5555/OxStore` `main` 分支（Commit: `57cb5d3` / `57cb5d317d2549cdfbce4f4f1957e7a7ed662286`） |
| **验收依据** | `docs/iteration2/product-backlog.md` US-02（AC1～AC6 & How to demo）、`requirements-specification.md` §5.2.2 / §7.1 场景2 |
| **JUnit 自动化测试结果** | ✅ **PASS（23 / 23 全部通过，0 失败 / 0 错误 / 0 跳过）** · [📷 查看 JUnit 运行截图](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_00_junit_test_pass.png) |
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
| **E1** | 后端服务已启动并支持成交扣库存 |  通过 | 交易成功接口可扣减库存并触发状态流转 |
| **E2** | 前端卖家商品编辑页与买家列表可用 |  通过 | `/admin/products/{id}/edit` 与首页列表正常 |
| **E3** | 可构造库存=1 与库存≥2 的在售商品 |  通过 | 测试商品 `T017-*` 已发布 |
| **E4** | 可完成成功/失败交易闭环 |  通过 | 队首开始交易 + 确认成功/失败可用 |
| **E5** | 可手动上架已下架且库存>0 的商品 |  通过 | `POST /api/admin/products/{id}/online` 可用 |

---

## 三、JUnit 后端自动化测试结果（第一部分）

在开展页面黑盒验收前，先执行后端 Maven JUnit 自动化测试套件，验证后端接口契约与业务服务层逻辑：

- **执行命令**：`mvn -B -f backend/pom.xml test`
- **总体统计**：共运行 **10 个测试类、23 项测试方法**，**通过 23 项，失败 0 项，错误 0 项，跳过 0 项（BUILD SUCCESS）**。
- **运行截图与日志**：
  - [📷 查看截图：Maven JUnit 自动化测试全绿终端输出 (t017_00_junit_test_pass.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_00_junit_test_pass.png)
  - [📄 查看原始日志：mvn_test_clean.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2-r2-20261028/mvn_test_clean.log)
  - [📄 查看 Playwright E2E 日志：playwright_e2e_output.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2-r2-20261028/playwright_e2e_output.log)

### 3.1 JUnit 测试类与 T-017 关联核对

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

### 4.1 验收清单总表（C-017-01 ～ C-017-07）

| 用例编号 | 类别 | 用例名称 | 对应验收点 | 实测结果 | 截图证据链接（点击查看） |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **C-017-01** | 主路径 | 仅交易成功扣减库存 1 | PB-02 AC2 |  通过 | [📷 t017_01a_before_success_stock_unchanged.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_01a_before_success_stock_unchanged.png) · [📷 t017_01b_after_success_deducted.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_01b_after_success_deducted.png) |
| **C-017-02** | 主路径 | 扣减后库存>0 回在售且新队首不自动冻结 | PB-02 AC3 |  通过 | [📷 t017_02_remain_online_new_head_queuing.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_02_remain_online_new_head_queuing.png) |
| **C-017-03** | 主路径 | 扣减后库存=0 自动下架且不可见 | PB-02 AC4 |  通过 | [📷 t017_03a_list_excludes_zero_stock.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_03a_list_excludes_zero_stock.png) · [📷 t017_03b_offline_detail_blocked.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_03b_offline_detail_blocked.png) |
| **C-017-04** | 主路径 | 库存从 0 改为正数不自动上架 | PB-02 AC5 |  通过 | [📷 t017_04_restock_still_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_04_restock_still_offline.png) |
| **C-017-05** | 主路径 | 手动上架后重新在售 | PB-02 AC5 |  通过 | [📷 t017_05_manual_online_visible.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_05_manual_online_visible.png) |
| **C-017-06** | 负面/边界 | 发布库存 0 立即下架不可见 | PB-02 AC1 |  通过 | [📷 t017_06_publish_stock0_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_06_publish_stock0_offline.png) |
| **C-017-07** | 负面/边界 | 交易失败不扣库存 | PB-02 AC2 |  通过 | [📷 t017_07_fail_no_deduct.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_07_fail_no_deduct.png) |

---

## 五、逐条用例执行详情与证据核验

### 5.1 主路径用例（Happy Path）

#### C-017-01 · 仅交易成功扣减库存 1
- **对应验收点**：PB-02 AC2
- **操作步骤**：提交意向→冻结→确认成功，核验库存变化
- **期望结果**：意向/冻结不改库存；成功后减 1
- **实际结果**：实测库存链路 `2→2→1`（意向后、冻结后仍为 2，成功后为 1）。（补充：2->2->1）
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t017_01a_before_success_stock_unchanged.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_01a_before_success_stock_unchanged.png) ｜ [📷 查看截图：t017_01b_after_success_deducted.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_01b_after_success_deducted.png)

#### C-017-02 · 扣减后库存>0 回在售且新队首不自动冻结
- **对应验收点**：PB-02 AC3
- **操作步骤**：成功后库存仍>0；再有排队意向
- **期望结果**：状态 ONLINE；新队首 QUEUING，需再次手动开始交易
- **实际结果**：商品回到 ONLINE；队列页出现「开始处理队首」。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t017_02_remain_online_new_head_queuing.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_02_remain_online_new_head_queuing.png)

#### C-017-03 · 扣减后库存=0 自动下架且不可见
- **对应验收点**：PB-02 AC4
- **操作步骤**：库存 1 的商品成交成功
- **期望结果**：自动 OFFLINE；列表/详情不可见
- **实际结果**：`GET /api/products/{id}` 返回 40401；首页不含该商品；详情空态拦截。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t017_03a_list_excludes_zero_stock.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_03a_list_excludes_zero_stock.png) ｜ [📷 查看截图：t017_03b_offline_detail_blocked.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_03b_offline_detail_blocked.png)

#### C-017-04 · 库存从 0 改为正数不自动上架
- **对应验收点**：PB-02 AC5
- **操作步骤**：对已下架商品 PATCH stock=3
- **期望结果**：仍保持 OFFLINE
- **实际结果**：管理端状态仍为已下架，需手动上架。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t017_04_restock_still_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_04_restock_still_offline.png)

#### C-017-05 · 手动上架后重新在售
- **对应验收点**：PB-02 AC5
- **操作步骤**：执行手动上架
- **期望结果**：买家列表重新可见
- **实际结果**：`online` 后状态 ONLINE，首页可见。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t017_05_manual_online_visible.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_05_manual_online_visible.png)

### 5.2 负面 / 边界用例

#### C-017-06 · 发布库存 0 立即下架不可见
- **对应验收点**：PB-02 AC1
- **操作步骤**：发布 stock=0 商品
- **期望结果**：买家端不可见不可开详情
- **实际结果**：发布后买家详情 40401；管理端可见为已下架。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t017_06_publish_stock0_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_06_publish_stock0_offline.png)

#### C-017-07 · 交易失败不扣库存
- **对应验收点**：PB-02 AC2
- **操作步骤**：开始交易后确认失败作废
- **期望结果**：库存不变且回在售
- **实际结果**：失败后 stock 仍为 2，status=ONLINE。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t017_07_fail_no_deduct.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t017/t017_07_fail_no_deduct.png)

---

## 六、Sprint Review 汇报一行汇总与禅道回写

| Task | PB | 禅道子需求 | 执行日期 | 验收结果 | 通过/总数 | 发现缺陷数 | 证据位置 |
| ---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **T-017** | **PB-02** | **13920** | 2026-10-28 | ☑ **通过** | **7 / 7**（JUnit 23/23） | **0**（无阻塞或功能缺陷） | `docs/test/T-017-acceptance-report.md` 及 `screenshots/t017/` |
