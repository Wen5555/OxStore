# T-013 验收测试成果报告 · 多商品独立队列、队首冻结和购买意向

> **交付物说明**：本报告为迭代 2（Sprint 1）任务 **T-013** 的独立验收成果文档，涵盖 **JUnit 后端自动化基线验证** 与 **黑盒验收测试（页面 UI + 后端 API）** 全流程实测结果。所有截图与运行证据均采用超链接方式索引，不在正文内嵌大图，保持版面整洁易读。

---

## 一、任务元信息与总体结论

| 维度 | 详情 |
| :--- | :--- |
| **任务编号 (Task ID)** | **T-013** |
| **关联产品待办 (PB / US)** | **PB-01 / US-01** 多商品上架与按商品队列 |
| **禅道追踪编号** | 子需求 **13912**（父需求 = **13901**，所属模块：`/购买意向与队列`；项目任务 **#22216**） |
| **验收负责人** | R2 彭燕（PO / 独立验收测试） |
| **执行时间** | 2026-10-28 22:08 – 22:19（Asia/Shanghai，UTC+8） |
| **被测代码基线** | `Wen5555/OxStore` `main` 分支（Commit: `57cb5d3` / `57cb5d317d2549cdfbce4f4f1957e7a7ed662286`） |
| **验收依据** | `docs/iteration2/product-backlog.md` US-01（AC1～AC7 & How to demo）、`requirements-specification.md` §5.2.3 / §7.1 场景1（用例 B-009 / S-008 / S-009） |
| **JUnit 自动化测试结果** | ✅ **PASS（23 / 23 全部通过，0 失败 / 0 错误 / 0 跳过）** · [📷 查看 JUnit 运行截图](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_00_junit_test_pass.png) |
| **黑盒验收用例结果** | ✅ **PASS（9 / 9 全部通过，含 6 条主路径 + 3 条边界/负面用例）** |
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
| **E1** | 后端服务已启动（`http://127.0.0.1:8080`） |  通过 | Spring Boot `3.2.5` 正常运行，类目/商品/意向接口正常响应 |
| **E2** | 前端服务已启动（`http://127.0.0.1:5173/`） |  通过 | Vite + React 前端渲染正常，`/api` 代理转发正常 |
| **E3** | 卖家后台可登录并发布多件商品、查看按商品意向队列 |  通过 | 预置卖家 `admin` 登录成功，可打开 `/admin/products/{id}/intents` |
| **E4** | 顾客注册/登录可用；提交意向无口令码入口 |  通过 | 测试买家 `r2_buyer_1/2/3` 注册登录成功，全站无口令码入口 |
| **E5** | 可对队首执行「开始处理队首」使商品进入 `FROZEN` |  通过 | `POST /api/admin/intents/{id}/start` 与 UI「开始处理队首」均可用 |

---

## 三、JUnit 后端自动化测试结果（第一部分）

在开展页面黑盒验收前，先执行后端 Maven JUnit 自动化测试套件，验证后端接口契约与业务服务层逻辑：

- **执行命令**：`mvn -B -f backend/pom.xml test`
- **总体统计**：共运行 **10 个测试类、23 项测试方法**，**通过 23 项，失败 0 项，错误 0 项，跳过 0 项（BUILD SUCCESS）**。
- **运行截图与日志**：
  - [📷 查看截图：Maven JUnit 自动化测试全绿终端输出 (t013_00_junit_test_pass.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_00_junit_test_pass.png)
  - [📄 查看原始日志：mvn_test_clean.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2-r2-20261028/mvn_test_clean.log)
  - [📄 查看 Playwright E2E 日志：playwright_e2e_output.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2-r2-20261028/playwright_e2e_output.log)

### 3.1 JUnit 测试类与 T-013 关联核对

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

### 4.1 验收清单总表（C-013-01 ～ C-013-09）

| 用例编号 | 类别 | 用例名称 | 对应验收点 | 实测结果 | 截图证据链接（点击查看） |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **C-013-01** | 主路径 | 同时多件在售（无在售数量上限） | PB-01 AC1 |  通过 | [📷 t013_01_multi_online_list.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_01_multi_online_list.png) |
| **C-013-02** | 主路径 | 登录后提交意向；数量固定为 1；无口令码 | PB-01 AC4/AC5 |  通过 | [📷 t013_02a_detail_before_intent.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_02a_detail_before_intent.png) · [📷 t013_02b_intent_submitted.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_02b_intent_submitted.png) |
| **C-013-03** | 主路径 | 每件商品独立意向队列 | PB-01 AC2 |  通过 | [📷 t013_03a_queue_product_a.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_03a_queue_product_a.png) · [📷 t013_03b_queue_product_b.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_03b_queue_product_b.png) |
| **C-013-04** | 主路径 | 对队首发起交易才冻结；新队首不自动冻结 | PB-01 AC6/AC7 |  通过 | [📷 t013_04_start_trade_frozen.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_04_start_trade_frozen.png) |
| **C-013-05** | 主路径 | 冻结 A 不影响 B 的浏览与提交意向 | PB-01 AC2 |  通过 | [📷 t013_05a_list_excludes_frozen_a.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_05a_list_excludes_frozen_a.png) · [📷 t013_05b_submit_intent_on_b.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_05b_submit_intent_on_b.png) |
| **C-013-06** | 主路径 | 仅当前无交易中意向时才可对队首发起交易 | PB-01 AC7 |  通过 | [📷 t013_06_no_second_trade.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_06_no_second_trade.png) |
| **C-013-07** | 负面/边界 | 未登录无法提交意向（回归） | PB-01 AC4 |  通过 | [📷 t013_07a_unauth_detail.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_07a_unauth_detail.png) · [📷 t013_07b_unauth_redirect_login.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_07b_unauth_redirect_login.png) |
| **C-013-08** | 负面/边界 | 冻结商品详情直链只读、不可再提交意向 | PB-01 + PB-03 AC7 |  通过 | [📷 t013_08_frozen_readonly.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_08_frozen_readonly.png) |
| **C-013-09** | 负面/边界 | 发布必填字段（名称、价格、二级类目、库存） | PB-01 AC3 |  通过 | [📷 t013_09_publish_require_fields.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_09_publish_require_fields.png) |

---

## 五、逐条用例执行详情与证据核验

### 5.1 主路径用例（Happy Path）

#### C-013-01 · 同时多件在售（无在售数量上限）
- **对应验收点**：PB-01 AC1
- **操作步骤**：卖家发布至少两件库存>0 商品；买家打开列表
- **期望结果**：两件均 ONLINE 且同时出现在买家列表
- **实际结果**：发布 `T013-A-*` 与 `T013-B-*` 后匿名首页同时可见两件在售商品，无「只能一件在售」限制。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t013_01_multi_online_list.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_01_multi_online_list.png)

#### C-013-02 · 登录后提交意向；数量固定为 1；无口令码
- **对应验收点**：PB-01 AC4/AC5
- **操作步骤**：顾客登录后对商品 A 提交购买意向；巡检无口令码入口
- **期望结果**：提交成功；无数量选择；全站无口令码
- **实际结果**：已登录买家详情页仅「提交购买意向」按钮，DOM 匹配「口令」为 0；提交成功入队。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t013_02a_detail_before_intent.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_02a_detail_before_intent.png) ｜ [📷 查看截图：t013_02b_intent_submitted.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_02b_intent_submitted.png)

#### C-013-03 · 每件商品独立意向队列
- **对应验收点**：PB-01 AC2
- **操作步骤**：Buyer-1 对 A、Buyer-2 对 B 分别提交意向；卖家分别打开两商品队列
- **期望结果**：A 队列仅含对 A 的意向；B 队列仅含对 B 的意向
- **实际结果**：`/admin/products/{A}/intents` 与 `/admin/products/{B}/intents` 队列互不混入。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t013_03a_queue_product_a.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_03a_queue_product_a.png) ｜ [📷 查看截图：t013_03b_queue_product_b.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_03b_queue_product_b.png)

#### C-013-04 · 对队首发起交易才冻结；新队首不自动冻结
- **对应验收点**：PB-01 AC6/AC7
- **操作步骤**：对 A 队首点击「开始处理队首」
- **期望结果**：队首→IN_TRANSACTION；A→FROZEN；新队首保持 QUEUING
- **实际结果**：UI 显示交易中；`GET /api/products/{A}` 返回 `status=FROZEN`。（补充：status=FROZEN）
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t013_04_start_trade_frozen.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_04_start_trade_frozen.png)

#### C-013-05 · 冻结 A 不影响 B 的浏览与提交意向
- **对应验收点**：PB-01 AC2
- **操作步骤**：保持 A 为 FROZEN；检查列表与对 B 提交意向
- **期望结果**：列表不含 A、含 B；B 可提交意向
- **实际结果**：列表 API 排除 A 的 productId；B 仍可提交意向（HTTP <400）。（补充：aHidden=true bVisible=true intent=200）
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t013_05a_list_excludes_frozen_a.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_05a_list_excludes_frozen_a.png) ｜ [📷 查看截图：t013_05b_submit_intent_on_b.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_05b_submit_intent_on_b.png)

#### C-013-06 · 仅当前无交易中意向时才可对队首发起交易
- **对应验收点**：PB-01 AC7
- **操作步骤**：A 已有 IN_TRANSACTION 时再次发起交易
- **期望结果**：被拒绝（409）
- **实际结果**：再次 `start` 返回冲突，UI 仍仅一条交易中意向。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t013_06_no_second_trade.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_06_no_second_trade.png)

### 5.2 负面 / 边界用例

#### C-013-07 · 未登录无法提交意向（回归）
- **对应验收点**：PB-01 AC4
- **操作步骤**：退出登录，对 B 点提交意向
- **期望结果**：引导登录或不入队
- **实际结果**：点击后跳转 `/login`；后端无 Authorization 返回 401。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t013_07a_unauth_detail.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_07a_unauth_detail.png) ｜ [📷 查看截图：t013_07b_unauth_redirect_login.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_07b_unauth_redirect_login.png)

#### C-013-08 · 冻结商品详情直链只读、不可再提交意向
- **对应验收点**：PB-01 + PB-03 AC7
- **操作步骤**：打开 FROZEN 的 A 详情直链
- **期望结果**：可只读查看；不可提交
- **实际结果**：详情 `canPurchase=false`，无有效购买提交入口。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t013_08_frozen_readonly.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_08_frozen_readonly.png)

#### C-013-09 · 发布必填字段（名称、价格、二级类目、库存）
- **对应验收点**：PB-01 AC3
- **操作步骤**：卖家发布页缺省必填项尝试发布
- **期望结果**：缺必填拒绝
- **实际结果**：直接点「发布商品」触发表单红字校验，未产生新商品。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t013_09_publish_require_fields.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t013/t013_09_publish_require_fields.png)

---

## 六、Sprint Review 汇报一行汇总与禅道回写

| Task | PB | 禅道子需求 | 执行日期 | 验收结果 | 通过/总数 | 发现缺陷数 | 证据位置 |
| ---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **T-013** | **PB-01** | **13912** | 2026-10-28 | ☑ **通过** | **9 / 9**（JUnit 23/23） | **0**（无阻塞或功能缺陷） | `docs/test/T-013-acceptance-report.md` 及 `screenshots/t013/` |
