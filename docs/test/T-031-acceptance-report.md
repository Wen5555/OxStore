# T-031 验收测试成果报告 · 多图、富文本、文件校验和搜索去标签

> **交付物说明**：本报告为迭代 2（Sprint 1）任务 **T-031** 的独立验收成果文档，涵盖 **JUnit 后端自动化基线验证** 与 **黑盒验收测试（页面 UI + 后端 API）** 全流程实测结果。所有截图与运行证据均采用超链接方式索引，不在正文内嵌大图，保持版面整洁易读。

---

## 一、任务元信息与总体结论

| 维度 | 详情 |
| :--- | :--- |
| **任务编号 (Task ID)** | **T-031** |
| **关联产品待办 (PB / US)** | **PB-07 / US-07** 多图展示与富文本描述 |
| **禅道追踪编号** | 子需求 **13940**（父需求 = **13907**，所属模块：`/商品内容与展示`；项目任务 **#22225**） |
| **验收负责人** | R2 彭燕（PO / 独立验收测试） |
| **执行时间** | 2026-10-28 22:08 – 22:19（Asia/Shanghai，UTC+8） |
| **被测代码基线** | `Wen5555/OxStore` `main` 分支（Commit: `57cb5d3` / `57cb5d317d2549cdfbce4f4f1957e7a7ed662286`） |
| **验收依据** | `docs/iteration2/product-backlog.md` US-07（AC1～AC12 & How to demo）、`requirements-specification.md` §5.1.3 / §5.2.1 |
| **JUnit 自动化测试结果** | ✅ **PASS（23 / 23 全部通过，0 失败 / 0 错误 / 0 跳过）** · [📷 查看 JUnit 运行截图](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_00_junit_test_pass.png) |
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
| **E1** | 后端图片存储与富文本清洗可用 |  通过 | `ImageStorageService` 校验 JPG/PNG/≤5MB；危险富文本返回 42201 |
| **E2** | 前端发布页支持多图上传与富文本编辑 |  通过 | `/admin/products/publish` 可用 |
| **E3** | 买家详情页可展示多图与富文本 |  通过 | `/products/{id}` 正常渲染 |
| **E4** | 搜索支持剥标签纯文本匹配 |  通过 | `GET /api/products?q=` 可命中富文本纯文本关键词 |
| **E5** | 已准备合规/不合规图片样例 |  通过 | JPG/PNG 合规图、GIF、>5MB 超限图 |

---

## 三、JUnit 后端自动化测试结果（第一部分）

在开展页面黑盒验收前，先执行后端 Maven JUnit 自动化测试套件，验证后端接口契约与业务服务层逻辑：

- **执行命令**：`mvn -B -f backend/pom.xml test`
- **总体统计**：共运行 **10 个测试类、23 项测试方法**，**通过 23 项，失败 0 项，错误 0 项，跳过 0 项（BUILD SUCCESS）**。
- **运行截图与日志**：
  - [📷 查看截图：Maven JUnit 自动化测试全绿终端输出 (t031_00_junit_test_pass.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_00_junit_test_pass.png)
  - [📄 查看原始日志：mvn_test_clean.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2-r2-20261028/mvn_test_clean.log)
  - [📄 查看 Playwright E2E 日志：playwright_e2e_output.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2-r2-20261028/playwright_e2e_output.log)

### 3.1 JUnit 测试类与 T-031 关联核对

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

### 4.1 验收清单总表（C-031-01 ～ C-031-08）

| 用例编号 | 类别 | 用例名称 | 对应验收点 | 实测结果 | 截图证据链接（点击查看） |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **C-031-01** | 主路径 | 详情可按序查看多张商品图与富文本 | PB-07 AC2/AC7 |  通过 | [📷 t031_01_detail_multi_images_richtext.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_01_detail_multi_images_richtext.png) |
| **C-031-02** | 主路径 | 主图为第一张商品图 | PB-07 AC3 |  通过 | [📷 t031_02_list_main_image.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_02_list_main_image.png) |
| **C-031-03** | 主路径 | 无商品图时统一占位图 | PB-07 AC3 |  通过 | [📷 t031_03_placeholder_no_product_image.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_03_placeholder_no_product_image.png) |
| **C-031-04** | 主路径 | 图片格式/大小校验拒绝不合规文件 | PB-07 AC1 |  通过 | [📷 t031_04_publish_image_validation_ui.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_04_publish_image_validation_ui.png) |
| **C-031-05** | 主路径 | 搜索先剥标签匹配名称+描述纯文本 | PB-07 AC11 |  通过 | [📷 t031_05a_search_stripped_richtext.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_05a_search_stripped_richtext.png) · [📷 t031_05b_search_category_name.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_05b_search_category_name.png) |
| **C-031-06** | 负面/边界 | 空描述不展示描述区 | PB-07 AC8 |  通过 | [📷 t031_06_empty_description_hidden.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_06_empty_description_hidden.png) |
| **C-031-07** | 负面/边界 | 富文本禁止脚本/危险内容 | PB-07 AC7 |  通过 | [📷 t031_07_unsafe_richtext_rejected.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_07_unsafe_richtext_rejected.png) |
| **C-031-08** | 负面/边界 | 商品图最多 9 张 | PB-07 AC1 |  通过 | [📷 t031_08_nine_images_ok.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_08_nine_images_ok.png) |

---

## 五、逐条用例执行详情与证据核验

### 5.1 主路径用例（Happy Path）

#### C-031-01 · 详情可按序查看多张商品图与富文本
- **对应验收点**：PB-07 AC2/AC7
- **操作步骤**：发布 3 图+富文本，打开详情
- **期望结果**：images=3；富文本可见
- **实际结果**：详情返回 3 张图片并渲染加粗/列表富文本。（补充：images=3）
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t031_01_detail_multi_images_richtext.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_01_detail_multi_images_richtext.png)

#### C-031-02 · 主图为第一张商品图
- **对应验收点**：PB-07 AC3
- **操作步骤**：检查列表主图与详情 mainImagePath
- **期望结果**：主图=第一张
- **实际结果**：`mainImagePath` 非空且对应首图。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t031_02_list_main_image.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_02_list_main_image.png)

#### C-031-03 · 无商品图时统一占位图
- **对应验收点**：PB-07 AC3
- **操作步骤**：发布无图商品
- **期望结果**：列表/详情占位图
- **实际结果**：无图商品卡片正常展示占位图，不把描述插图当主图。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t031_03_placeholder_no_product_image.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_03_placeholder_no_product_image.png)

#### C-031-04 · 图片格式/大小校验拒绝不合规文件
- **对应验收点**：PB-07 AC1
- **操作步骤**：上传 GIF 与 >5MB 图片
- **期望结果**：拒绝
- **实际结果**：GIF→415/41501；超限→413/41301。（补充：gif=415/41501 big=413/41301）
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t031_04_publish_image_validation_ui.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_04_publish_image_validation_ui.png)

#### C-031-05 · 搜索先剥标签匹配名称+描述纯文本
- **对应验收点**：PB-07 AC11
- **操作步骤**：搜索富文本关键词 `RichSearchTag`
- **期望结果**：命中该商品
- **实际结果**：`q=RichSearchTag` 命中目标商品。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t031_05a_search_stripped_richtext.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_05a_search_stripped_richtext.png) ｜ [📷 查看截图：t031_05b_search_category_name.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_05b_search_category_name.png)

### 5.2 负面 / 边界用例

#### C-031-06 · 空描述不展示描述区
- **对应验收点**：PB-07 AC8
- **操作步骤**：打开空描述商品详情
- **期望结果**：不展示描述区
- **实际结果**：空/空白标签描述不渲染描述区块。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t031_06_empty_description_hidden.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_06_empty_description_hidden.png)

#### C-031-07 · 富文本禁止脚本/危险内容
- **对应验收点**：PB-07 AC7
- **操作步骤**：发布含 `<script>` 描述
- **期望结果**：拒绝
- **实际结果**：返回 422/42201。（补充：422/42201）
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t031_07_unsafe_richtext_rejected.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_07_unsafe_richtext_rejected.png)

#### C-031-08 · 商品图最多 9 张
- **对应验收点**：PB-07 AC1
- **操作步骤**：发布 9 张成功；10 张失败
- **期望结果**：九张成功，第十张拒绝
- **实际结果**：9 张发布成功；10 张返回 HTTP 400。（补充：nine=9 tenStatus=400）
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：t031_08_nine_images_ok.png](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t031/t031_08_nine_images_ok.png)

---

## 六、Sprint Review 汇报一行汇总与禅道回写

| Task | PB | 禅道子需求 | 执行日期 | 验收结果 | 通过/总数 | 发现缺陷数 | 证据位置 |
| ---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **T-031** | **PB-07** | **13940** | 2026-10-28 | ☑ **通过** | **8 / 8**（JUnit 23/23） | **0**（无阻塞或功能缺陷） | `docs/test/T-031-acceptance-report.md` 及 `screenshots/t031/` |
