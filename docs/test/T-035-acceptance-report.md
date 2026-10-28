# T-035 验收测试成果报告 · 商家顾客列表、历史快照和只读权限

> **交付物说明**：本报告为迭代 2（Sprint 1）任务 **T-035** 的独立验收成果文档，涵盖 **JUnit 后端自动化基线验证** 与 **黑盒验收测试（页面 UI + 后端 API）** 全流程实测结果。所有截图与运行证据均采用超链接方式索引，不在正文内嵌大图，保持版面整洁易读。

---

## 一、任务元信息与总体结论

| 维度 | 详情 |
| :--- | :--- |
| **任务编号 (Task ID)** | **T-035** |
| **关联产品待办 (PB / US)** | **PB-08 / US-08** 商家查看全部顾客与购买历史 |
| **禅道追踪编号** | 子需求 **13944**（父需求 = **13908**，所属模块：`/卖家顾客运营`；项目任务 **#22228**） |
| **验收负责人** | R2 彭燕（PO / 独立验收测试） |
| **执行时间** | 2026-10-28 22:08 – 22:19（Asia/Shanghai，UTC+8） |
| **被测代码基线** | `Wen5555/OxStore` `main` 分支（Commit: `57cb5d3` / `57cb5d317d2549cdfbce4f4f1957e7a7ed662286`） |
| **验收依据** | `docs/iteration2/product-backlog.md` US-08（AC1～AC10 & How to demo）、`requirements-specification.md` §5.2.5（用例 S-013 / S-014） |
| **JUnit 自动化测试结果** | ✅ **PASS（23 / 23 全部通过，0 失败 / 0 错误 / 0 跳过）** · [📷 查看 JUnit 运行截图](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_00_junit_test_pass.png) |
| **黑盒验收用例结果** | ✅ **PASS（8 / 8 全部通过，含 5 条主路径 + 3 条边界/负面用例）** |
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
| **E1** | 后端顾客列表与顾客历史接口可用 |  通过 | `GET /api/admin/customers` 与 `.../order-history` 正常 |
| **E2** | 前端全部顾客页可用 |  通过 | `/admin/customers` 正常渲染 |
| **E3** | 存在从未下单的注册顾客 |  通过 | `t035_never_ordered` 出现在顾客列表 |
| **E4** | 存在有成功/失败终态的顾客 |  通过 | 可从列表进入购买历史 |
| **E5** | 未登录卖家访问被拦截 |  通过 | 访问 `/admin/customers` 跳转 `/admin/login` |

---

## 三、JUnit 后端自动化测试结果（第一部分）

在开展页面黑盒验收前，先执行后端 Maven JUnit 自动化测试套件，验证后端接口契约与业务服务层逻辑：

- **执行命令**：`mvn -B -f backend/pom.xml test`
- **总体统计**：共运行 **10 个测试类、23 项测试方法**，**通过 23 项，失败 0 项，错误 0 项，跳过 0 项（BUILD SUCCESS）**。
- **运行截图与日志**：
  - [📷 查看截图：Maven JUnit 自动化测试全绿终端输出 (t035_00_junit_test_pass.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_00_junit_test_pass.png)
  - [📄 查看原始日志：mvn_test_clean.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2-r2-20261028/mvn_test_clean.log)
  - [📄 查看 Playwright E2E 日志：playwright_e2e_output.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2-r2-20261028/playwright_e2e_output.log)

### 3.1 JUnit 测试类与 T-035 关联核对

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

### 4.1 验收清单总表（C-035-01 ～ C-035-08）

| 用例编号 | 类别 | 用例名称 | 对应验收点 | 实测结果 | 截图证据链接（点击查看） |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **C-035-01** | 主路径 | 顾客列表含从未下单注册用户 | PB-08 AC1 |  通过 | [📷 t035_01_all_customers_include_never_ordered.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_01_all_customers_include_never_ordered.png) |
| **C-035-02** | 主路径 | 列表含用户名/电话/地点/注册时间 | PB-08 AC2 |  通过 | [📷 t035_02_customer_list_fields.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_02_customer_list_fields.png) |
| **C-035-03** | 主路径 | 地点未填显示「未设置」 | PB-08 AC3 |  通过 | [📷 t035_03_location_unset.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_03_location_unset.png) |
| **C-035-04** | 主路径 | 按注册时间倒序并支持分页 | PB-08 AC4 |  通过 | [📷 t035_04_customers_desc_pagination.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_04_customers_desc_pagination.png) |
| **C-035-05** | 主路径 | 顾客购买历史仅终态且只读 | PB-08 AC6/AC10 |  通过 | [📷 t035_05_customer_history_readonly.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_05_customer_history_readonly.png) |
| **C-035-06** | 负面/边界 | 历史含快照商品名与时间结果字段 | PB-08 AC7 |  通过 | [📷 t035_06_history_snapshot_fields.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_06_history_snapshot_fields.png) |
| **C-035-07** | 负面/边界 | 历史页无可交易操作（只读） | PB-08 AC10 |  通过 | [📷 t035_07_history_no_trade_actions.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_07_history_no_trade_actions.png) |
| **C-035-08** | 负面/边界 | 未登录卖家不可查看顾客列表 | PB-08 权限 |  通过 | [📷 t035_08_seller_auth_required.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_08_seller_auth_required.png) |

---

## 五、逐条用例执行详情与证据核验

### 5.1 主路径用例（Happy Path）

#### C-035-01 · 顾客列表含从未下单注册用户
- **对应验收点**：PB-08 AC1
- **操作步骤**：打开全部顾客
- **期望结果**：含 `t035_never_ordered`
- **实际结果**：列表包含从未下单账号。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t035_01_all_customers_include_never_ordered.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_01_all_customers_include_never_ordered.png)

#### C-035-02 · 列表含用户名/电话/地点/注册时间
- **对应验收点**：PB-08 AC2
- **操作步骤**：检查表头与 API
- **期望结果**：四字段齐全
- **实际结果**：表格列与 API 字段齐全。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t035_02_customer_list_fields.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_02_customer_list_fields.png)

#### C-035-03 · 地点未填显示「未设置」
- **对应验收点**：PB-08 AC3
- **操作步骤**：检查地点列
- **期望结果**：显示未设置
- **实际结果**：页面出现「未设置」。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t035_03_location_unset.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_03_location_unset.png)

#### C-035-04 · 按注册时间倒序并支持分页
- **对应验收点**：PB-08 AC4
- **操作步骤**：核验顺序与分页
- **期望结果**：倒序；可分页
- **实际结果**：`registeredAt` 倒序；有 Pagination。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t035_04_customers_desc_pagination.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_04_customers_desc_pagination.png)

#### C-035-05 · 顾客购买历史仅终态且只读
- **对应验收点**：PB-08 AC6/AC10
- **操作步骤**：进入某顾客购买历史
- **期望结果**：仅 SUCCESS/FAILED；无交易按钮
- **实际结果**：历史项均为终态。（补充：count=20）
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t035_05_customer_history_readonly.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_05_customer_history_readonly.png)

### 5.2 负面 / 边界用例

#### C-035-06 · 历史含快照商品名与时间结果字段
- **对应验收点**：PB-08 AC7
- **操作步骤**：检查历史字段
- **期望结果**：四字段齐全
- **实际结果**：含商品名快照、下单/交易时间、结果。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t035_06_history_snapshot_fields.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_06_history_snapshot_fields.png)

#### C-035-07 · 历史页无可交易操作（只读）
- **对应验收点**：PB-08 AC10
- **操作步骤**：巡检历史页按钮
- **期望结果**：无确认成功/开始处理队首等
- **实际结果**：页面无交易操作按钮。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t035_07_history_no_trade_actions.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_07_history_no_trade_actions.png)

#### C-035-08 · 未登录卖家不可查看顾客列表
- **对应验收点**：PB-08 权限
- **操作步骤**：清除 token 访问 `/admin/customers`
- **期望结果**：跳转卖家登录
- **实际结果**：跳转 `/admin/login`。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t035_08_seller_auth_required.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t035/t035_08_seller_auth_required.png)

---

## 六、Sprint Review 汇报一行汇总与禅道回写

| Task | PB | 禅道子需求 | 执行日期 | 验收结果 | 通过/总数 | 发现缺陷数 | 证据位置 |
| ---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **T-035** | **PB-08** | **13944** | 2026-10-28 | ☑ **通过** | **8 / 8**（JUnit 23/23） | **0**（无阻塞或功能缺陷） | `docs/test/T-035-acceptance-report.md` 及 `screenshots/t035/` |
