# T-021 验收测试成果报告 · 买家历史终态、快照和权限

> **交付物说明**：本报告为迭代 2（Sprint 1）任务 **T-021** 的独立验收成果文档，涵盖 **JUnit 后端自动化基线验证** 与 **黑盒验收测试（页面 UI + 后端 API）** 全流程实测结果。所有截图与运行证据均采用超链接方式索引，不在正文内嵌大图，保持版面整洁易读。

---

## 一、任务元信息与总体结论

| 维度 | 详情 |
| :--- | :--- |
| **任务编号 (Task ID)** | **T-021** |
| **关联产品待办 (PB / US)** | **PB-05 / US-05** 历史订单（终态） |
| **禅道追踪编号** | 子需求 **13932**（父需求 = **13905**，所属模块：`/买家购买历史`；项目任务 **#22223**） |
| **验收负责人** | R2 彭燕（PO / 独立验收测试） |
| **执行时间** | 2026-10-28 22:08 – 22:19（Asia/Shanghai，UTC+8） |
| **被测代码基线** | `Wen5555/OxStore` `main` 分支（Commit: `57cb5d3` / `57cb5d317d2549cdfbce4f4f1957e7a7ed662286`） |
| **验收依据** | `docs/iteration2/product-backlog.md` US-05（AC1～AC7 & How to demo）、`requirements-specification.md` §5.1.4（用例 B-010 / B-011） |
| **JUnit 自动化测试结果** | ✅ **PASS（23 / 23 全部通过，0 失败 / 0 错误 / 0 跳过）** · [📷 查看 JUnit 运行截图](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_00_junit_test_pass.png) |
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
| **E1** | 后端服务已启动，历史接口可用 |  通过 | `GET /api/me/order-history` 需顾客 JWT |
| **E2** | 前端买家历史页与账户页可用 |  通过 | `/me/order-history`、`/me/account` 路由正常 |
| **E3** | 已准备成功与失败终态交易数据 |  通过 | 买家 `r2_buyer_1` 具备 SUCCESS/FAILED 记录 |
| **E4** | 路由守卫可拦截未登录访问历史 |  通过 | 未登录访问跳转 `/login` |
| **E5** | 可验证商品下架后快照名称保留 |  通过 | 下架后历史仍展示下单时商品名 |

---

## 三、JUnit 后端自动化测试结果（第一部分）

在开展页面黑盒验收前，先执行后端 Maven JUnit 自动化测试套件，验证后端接口契约与业务服务层逻辑：

- **执行命令**：`mvn -B -f backend/pom.xml test`
- **总体统计**：共运行 **10 个测试类、23 项测试方法**，**通过 23 项，失败 0 项，错误 0 项，跳过 0 项（BUILD SUCCESS）**。
- **运行截图与日志**：
  - [📷 查看截图：Maven JUnit 自动化测试全绿终端输出 (t021_00_junit_test_pass.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_00_junit_test_pass.png)
  - [📄 查看原始日志：mvn_test_clean.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2-r2-20261028/mvn_test_clean.log)
  - [📄 查看 Playwright E2E 日志：playwright_e2e_output.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2-r2-20261028/playwright_e2e_output.log)

### 3.1 JUnit 测试类与 T-021 关联核对

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

### 4.1 验收清单总表（C-021-01 ～ C-021-07）

| 用例编号 | 类别 | 用例名称 | 对应验收点 | 实测结果 | 截图证据链接（点击查看） |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **C-021-01** | 主路径 | 未登录访问历史引导登录 | PB-05 AC1 |  通过 | [📷 t021_01_unauth_redirect_login.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_01_unauth_redirect_login.png) |
| **C-021-02** | 主路径 | 仅展示本人成功/失败终态 | PB-05 AC2 |  通过 | [📷 t021_02_history_success_fail_only.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_02_history_success_fail_only.png) |
| **C-021-03** | 主路径 | 含商品快照名/下单时间/结果/交易时间 | PB-05 AC3 |  通过 | [📷 t021_03_history_fields.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_03_history_fields.png) |
| **C-021-04** | 主路径 | 按时间倒序支持分页 | PB-05 AC4 |  通过 | [📷 t021_04_history_desc_order.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_04_history_desc_order.png) |
| **C-021-05** | 主路径 | 商品下架后历史快照名仍保留 | PB-05 AC5 |  通过 | [📷 t021_05_snapshot_after_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_05_snapshot_after_offline.png) |
| **C-021-06** | 负面/边界 | 历史仅本人可见（权限隔离） | PB-05 AC2 |  通过 | [📷 t021_06_other_user_isolation.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_06_other_user_isolation.png) |
| **C-021-07** | 负面/边界 | 账户页可进入购买历史 | PB-05 入口 |  通过 | [📷 t021_07_account_entry.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_07_account_entry.png) |

---

## 五、逐条用例执行详情与证据核验

### 5.1 主路径用例（Happy Path）

#### C-021-01 · 未登录访问历史引导登录
- **对应验收点**：PB-05 AC1
- **操作步骤**：匿名访问 `/me/order-history`
- **期望结果**：跳转登录
- **实际结果**：实际跳转 `/login`。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t021_01_unauth_redirect_login.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_01_unauth_redirect_login.png)

#### C-021-02 · 仅展示本人成功/失败终态
- **对应验收点**：PB-05 AC2
- **操作步骤**：登录后打开历史页
- **期望结果**：仅 SUCCESS/FAILED，无排队中/交易中
- **实际结果**：历史项状态全部为成功或失败，且同时包含两类。（补充：count=20）
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t021_02_history_success_fail_only.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_02_history_success_fail_only.png)

#### C-021-03 · 含商品快照名/下单时间/结果/交易时间
- **对应验收点**：PB-05 AC3
- **操作步骤**：检查历史表格字段
- **期望结果**：四字段齐全
- **实际结果**：表格列含商品、下单时间、结果、交易时间；API 字段齐全。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t021_03_history_fields.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_03_history_fields.png)

#### C-021-04 · 按时间倒序支持分页
- **对应验收点**：PB-05 AC4
- **操作步骤**：核验交易时间顺序与分页控件
- **期望结果**：倒序；有分页
- **实际结果**：`transactedAt` 倒序；页面含 Pagination。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t021_04_history_desc_order.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_04_history_desc_order.png)

#### C-021-05 · 商品下架后历史快照名仍保留
- **对应验收点**：PB-05 AC5
- **操作步骤**：下架商品后刷新历史
- **期望结果**：仍显示下单时商品名
- **实际结果**：下架后历史仍显示「T021-历史快照商品原名」。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t021_05_snapshot_after_offline.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_05_snapshot_after_offline.png)

### 5.2 负面 / 边界用例

#### C-021-06 · 历史仅本人可见（权限隔离）
- **对应验收点**：PB-05 AC2
- **操作步骤**：用另一买家打开历史
- **期望结果**：看不到他人 SUCCESS 记录
- **实际结果**：`r2_buyer_2` 历史不含该商品终态记录。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t021_06_other_user_isolation.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_06_other_user_isolation.png)

#### C-021-07 · 账户页可进入购买历史
- **对应验收点**：PB-05 入口
- **操作步骤**：打开 `/me/account`
- **期望结果**：可进入历史
- **实际结果**：账户概览页可用并提供历史入口。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t021_07_account_entry.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t021/t021_07_account_entry.png)

---

## 六、Sprint Review 汇报一行汇总与禅道回写

| Task | PB | 禅道子需求 | 执行日期 | 验收结果 | 通过/总数 | 发现缺陷数 | 证据位置 |
| ---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **T-021** | **PB-05** | **13932** | 2026-10-28 | ☑ **通过** | **7 / 7**（JUnit 23/23） | **0**（无阻塞或功能缺陷） | `docs/test/T-021-acceptance-report.md` 及 `screenshots/t021/` |
