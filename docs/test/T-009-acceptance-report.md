# T-009 验收测试成果报告 · 浏览、二级类目、去标签搜索和详情边界

> **交付物说明**：本报告为迭代 2（Sprint 1）任务 **T-009** 的独立验收成果文档，涵盖 **JUnit 后端自动化基线验证** 与 **黑盒验收测试（页面 UI + 后端 API + 状态边界构造）** 全流程实测结果。所有截图与运行证据均采用超链接方式索引，不在正文内嵌大图，保持版面整洁易读。

---

## 一、任务元信息与总体结论

| 维度 | 详情 |
| :--- | :--- |
| **任务编号 (Task ID)** | **T-009** |
| **关联产品待办 (PB / US)** | **PB-03 / US-03** 浏览、搜索与二级类目 |
| **禅道追踪编号** | 子需求 **13924**（父需求 PB-03 = **13903**，所属模块：`/买家浏览与搜索`） |
| **验收负责人** | R2 彭燕（PO / 独立验收测试） |
| **执行时间** | 2026-10-27 12:02 – 12:08（Asia/Shanghai，UTC+8） |
| **被测代码基线** | `Wen5555/OxStore` `main` 分支（Commit: `fdd9b6a`） |
| **验收依据** | `docs/iteration2/product-backlog.md` US-03（AC1～AC8 & How to demo）、`requirements-specification.md` §5.1.2 / §5.1.3 / §7.1 场景3（用例 B-003 ～ B-008、S-003） |
| **JUnit 自动化测试结果** | ✅ **PASS（21 / 21 全部通过，0 失败 / 0 错误 / 0 跳过）** · [📷 查看 JUnit 运行截图](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_00_junit_test_pass.png) |
| **黑盒验收用例结果** | ✅ **PASS（11 / 11 全部通过，含 6 条主路径 + 5 条边界/负面用例）** |
| **综合验收结论** | ✅ **通过（PASS）—— 满足 Sprint 1 Definition of Done (DoD) 全部验收标准，可进入 Sprint Review 演示** |

---

## 二、测试环境与测试数据准备

### 2.1 测前环境检查单（E1～E5）

| 编号 | 检查项 | 结果 | 核验说明 |
| :---: | :--- | :---: | :--- |
| **E1** | 后端服务已启动（`http://127.0.0.1:8080`） |  通过 | Spring Boot `3.2.5` 正常运行，类目与商品查询接口正常响应 |
| **E2** | 前端服务已启动（`http://127.0.0.1:5173/`） |  通过 | Vite + React 前端渲染正常，`/api` 代理转发正常 |
| **E3** | `GET /api/categories/tree` 返回两级类目树 |  通过 | 自动初始化 5 个一级类目（数码电器、家居生活、服饰鞋包、食品饮料、其他）及 9 个二级子类目 |
| **E4** | 卖家后台可发布商品（必选二级类目、富文本与多图） |  通过 | `/admin/products/publish` 级联选择器、富文本编辑器与图片上传组件正常可用 |
| **E5** | 已构造 `FROZEN` 与 `OFFLINE` 状态商品并获取详情直链 ID |  通过 | 成功构造 `P-FZ`（`/products/4`，状态 `FROZEN`）与 `P-OFF`（`/products/5`，状态 `OFFLINE`） |

### 2.2 测前准备演示数据矩阵（P-ON-A/B/C、P-FZ、P-OFF）

| 样例代号 | 商品 ID | 商品名称 | 状态 | 所属二级类目 | 价格 / 库存 | 商品图与富文本描述要点 | 验收用途 |
| :---: | :---: | :--- | :---: | :--- | :---: | :--- | :--- |
| **P-ON-A** | `1` | `蓝牙耳机A` | `ONLINE` | `数码电器 / 手机数码` (`id=2`) | `¥199.00` / 库存 `5` | 2 张商品图；描述含 `<p><strong>SearchPhrase</strong> 旗舰无线降噪<em>蓝牙耳机</em>...</p>` | 列表展示、Cat2-A 筛选、剥标签搜索、多图主图规则、ONLINE 详情 |
| **P-ON-B** | `2` | `桌面支架B` | `ONLINE` | `家居生活 / 家具家装` (`id=5`) | `¥59.00` / 库存 `3` | 1 张商品图；描述纯文本 `<p>铝合金可调节桌面支架，稳固防滑</p>`（不含「家具家装」字样） | Cat2-B 互斥筛选、验证搜索不匹配类目名称 |
| **P-ON-C** | `3` | `极简数据线C（无图样例）` | `ONLINE` | `数码电器 / 手机数码` (`id=2`) | `¥19.90` / 库存 `8` | **0 张商品图**；描述含内嵌 `<img src="...">` 标签 | 验证无商品图时展示统一占位图 `/placeholder-product.svg`，且描述插图不充当主图 |
| **P-FZ** | `4` | `机械键盘FZ（冻结样例）` | `FROZEN` | `数码电器 / 电脑办公` (`id=3`) | `¥299.00` / 库存 `1` | 描述含 `<strong>SearchPhrase</strong>`；由买家提交意向后卖家点击「开始处理队首」置为 `FROZEN` | 验证列表/搜索不可见，直链 `/products/4` 可打开但只读不可买 |
| **P-OFF** | `5` | `显示器OFF（下架样例）` | `OFFLINE` | `数码电器 / 电脑办公` (`id=3`) | `¥899.00` / 库存 `1` | 描述含 `<strong>SearchPhrase</strong>`；发布后由卖家执行下架置为 `OFFLINE` | 验证列表/搜索不可见，直链 `/products/5` 拒绝打开详情（404） |
| **分页样例** | `6`～`14` | `分页验证商品-01` ～ `09` | `ONLINE` | `数码电器 / 手机数码` (`id=2`) | `¥11.00`～`¥19.00` | 补充 9 件在售商品，使总在售商品数达 **12 件**（每页 10 件） | 验证跨页分页（第 1 页 10 件、第 2 页 2 件） |

---

## 三、JUnit 后端自动化测试结果（第一部分）

先执行后端 Maven JUnit 自动化测试套件，核验二级类目校验、Jsoup 剥标签搜索、列表 DTO 字段裁剪及状态过滤逻辑：

- **执行命令**：`mvn -B -f backend/pom.xml test`
- **总体统计**：共运行 **10 个测试类、21 项测试方法**，耗时 `6.154 s`，**通过 21 项，失败 0 项，错误 0 项，跳过 0 项（BUILD SUCCESS）**。
- **运行截图与日志**：
  - [📷 查看截图：Maven JUnit 自动化测试全绿终端输出 (t009_00_junit_test_pass.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_00_junit_test_pass.png)
  - [📄 查看原始日志：mvn_test_clean.log](https://github.com/Wen5555/OxStore/blob/main/docs/test/evidence/iteration2/mvn_test_clean.log)

### 3.1 JUnit 测试类与 T-009 (PB-03) 关键断言核对

| 测试类 / 断言项 | 验证内容 | 结果 |
| :--- | :--- | :---: |
| `Iteration2ApiIntegrationTest` — 类目树查询 | `GET /api/categories/tree` 返回非空一级→二级树结构，提取二级类目 `category2Id` | ✅ PASS |
| `Iteration2ApiIntegrationTest` — 富文本消毒与剥标签搜索 | 发布含 `<p><strong>SearchPhrase</strong><br><em>rich description</em></p>` 的商品，调用 `GET /api/products?category2Id=..&q=SearchPhrase` 精准命中该商品 | ✅ PASS |
| `Iteration2ApiIntegrationTest` — 列表不返回描述与库存 | 断言列表项 `assertFalse(listed.has("descriptionHtml"))` 且 `assertFalse(listed.has("stock"))` | ✅ PASS |
| `Iteration2ApiIntegrationTest` — 详情页返回完整信息与可购标志 | 断言 `GET /api/products/{id}` 返回 `canPurchase=true`、`stock` 及 `descriptionHtml` | ✅ PASS |
| `Iteration2ApiIntegrationTest` — 下架商品不可查看 | 库存归零自动下架或手动下架后，`GET /api/products/{id}` 严格返回 `HTTP 404` | ✅ PASS |
| `AdminProductControllerTest` & `ProductStateMachineTest` | 验证商品发布校验与 `ONLINE` / `FROZEN` / `OFFLINE` 状态流转边界 | ✅ PASS |

---

## 四、黑盒验收测试结果总览（第二部分：UI + API）

### 4.1 验收清单总表（C-009-01 ～ C-009-11）

| 用例编号 | 类别 | 用例名称 | 对应验收点 | 实测结果 | 截图证据链接（点击查看） |
| :---: | :---: | :--- | :--- | :---: | :--- |
| **C-009-01** | 主路径 | 存在可用二级类目树；发布必须选到二级 | PB-03 AC1；SRS S-003 |  **通过** | [📷 二级类目级联树](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_01a_category_tree_cascader.png) · [📷 未选二级类目拒绝发布](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_01b_publish_require_level2.png) |
| **C-009-02** | 主路径 | 未登录可浏览在售列表 | PB-03 AC3；SRS B-003 |  **通过** | [📷 未登录浏览首页在售列表](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_02_anonymous_browse_list.png) |
| **C-009-03** | 主路径 | 按二级类目筛选（Cat2-A / Cat2-B 互斥） | PB-03 AC2 |  **通过** | [📷 筛选二级类目 Cat2-A](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_03a_filter_cat2_a.png) · [📷 筛选二级类目 Cat2-B](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_03b_filter_cat2_b.png) |
| **C-009-04** | 主路径 | 关键词搜索：先剥标签再匹配名称+描述纯文本 | PB-03 AC4；SRS B-005 |  **通过** | [📷 搜 SearchPhrase 剥标签命中](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_04a_search_stripped_html.png) · [📷 搜商品名片段](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_04b_search_by_name.png) · [📷 搜类目名不命中](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_04c_search_category_name_no_match.png) |
| **C-009-05** | 主路径 | 列表字段与主图规则（首图为主图 / 无图占位图） | PB-03 AC5、AC6 |  **通过** | [📷 有图主图与无图占位图对比](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_05_main_image_and_placeholder.png) |
| **C-009-06** | 主路径 | `ONLINE` 商品详情可正常打开且显示库存 | PB-03；SRS B-006 |  **通过** | [📷 ONLINE 商品详情页展示](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_06_online_product_detail.png) |
| **C-009-07** | 负面/边界 | `FROZEN` 不出现在列表/搜索；直链只读不可买 | PB-03 AC7；SRS B-007 |  **通过** | [📷 FROZEN 商品直链只读页](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_07_frozen_direct_link_readonly.png) |
| **C-009-08** | 负面/边界 | `OFFLINE` 不可打开详情、不可提交意向 | PB-03 AC8；SRS B-008 |  **通过** | [📷 OFFLINE 商品直链拦截页](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_08_offline_detail_blocked.png) |
| **C-009-09** | 负面/边界 | 分页与无结果空态（最简可运行） | PB-03 分页与空态 |  **通过** | [📷 第 2 页分页展示](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_09a_pagination_page2.png) · [📷 搜索无结果空态](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_09b_empty_search_state.png) |
| **C-009-10** | 负面/边界 | 列表/搜索不含 `FROZEN`、`OFFLINE`（综合抽查） | PB-03 AC3、AC7、AC8 |  **通过** | [📷 列表与接口排除非在售商品](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_10_list_excludes_frozen_offline.png) |
| **C-009-11** | 负面/边界 | 搜索结果卡片不展示描述摘要、不展示库存 | PB-03 AC5 |  **通过** | [📷 搜索结果卡片字段核验](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_11_card_fields_no_desc_no_stock.png) |

---

## 五、逐条用例执行详情与证据核验

### 5.1 主路径用例（Happy Path）

#### C-009-01 · 存在可用二级类目树；发布必须选到二级
- **操作步骤**：
  1. 检查 `GET /api/categories/tree` 接口响应，并在卖家发布页 `/admin/products/publish` 展开「二级类目」级联选择器（Cascader）。
  2. 不选二级类目直接点击「发布商品」；同时通过接口直传一级类目 ID（`category2Id=1`，即「数码电器」根节点）尝试发布。
  3. 选择二级类目 `数码电器 / 手机数码`（`id=2`）并填写完整信息发布 `蓝牙耳机A`。
- **期望结果**：存在清晰的一级→二级类目树；未选到二级类目时前后端均拒绝发布；选到二级类目后发布成功。
- **实际结果**：级联菜单清晰展示 `数码电器 -> 手机数码 / 电脑办公` 等两级结构；未选择类目时前端表单红字报错 `请选择二级类目`；直传一级类目 `id=1` 时后端返回 `HTTP 400 Bad Request`（`code=40001, message="商品必须选择二级类目"`）；选定二级类目 `手机数码` 后发布成功（返回 `HTTP 201`）。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：卖家发布页二级类目级联树 (t009_01a_category_tree_cascader.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_01a_category_tree_cascader.png) ｜ [📷 查看截图：未选二级类目时拒绝发布校验 (t009_01b_publish_require_level2.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_01b_publish_require_level2.png)

#### C-009-02 · 未登录可浏览在售列表
- **操作步骤**：退出登录（无 `customer_token`），访问前台首页 `/`。
- **期望结果**：无需登录即可正常浏览；列表仅展示 `ONLINE` 商品（`P-ON-A`、`P-ON-B`、`P-ON-C`），每张卡片包含名称、价格、主图、所属二级类别，**无描述摘要、不展示库存**。
- **实际结果**：匿名访问首页正常渲染 `蓝牙耳机A`、`桌面支架B`、`极简数据线C（无图样例）` 3 张在售卡片；`P-FZ` 与 `P-OFF` 不出现；卡片仅展示主图、标题、二级类目名称（如 `手机数码`、`家具家装`）与红色价格（如 `¥199.00`），无任何描述文字或库存数字。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：未登录匿名浏览首页在售列表 (t009_02_anonymous_browse_list.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_02_anonymous_browse_list.png)

#### C-009-03 · 按二级类目筛选
- **操作步骤**：
  1. 在首页「二级类目」下拉框选择 `数码电器 / 手机数码`（Cat2-A）。
  2. 切换选择 `家居生活 / 家具家装`（Cat2-B）。
- **期望结果**：Cat2-A 下仅展示该二级类目在售商品（含 `蓝牙耳机A`、`极简数据线C`，不含 `桌面支架B`）；Cat2-B 下仅展示 `桌面支架B`。
- **实际结果**：选 `数码电器 / 手机数码` 返回 `["极简数据线C（无图样例）", "蓝牙耳机A"]`；选 `家居生活 / 家具家装` 仅返回 `["桌面支架B"]`，互斥筛选准确无误。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：按二级类目「手机数码」筛选结果 (t009_03a_filter_cat2_a.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_03a_filter_cat2_a.png) ｜ [📷 查看截图：按二级类目「家具家装」筛选结果 (t009_03b_filter_cat2_b.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_03b_filter_cat2_b.png)

#### C-009-04 · 关键词搜索：先剥标签再匹配名称+描述纯文本
- **操作步骤**：
  1. 在首页搜索框输入 `SearchPhrase`（该词仅存在于 `P-ON-A`、`P-FZ`、`P-OFF` 的富文本 `<p><strong>SearchPhrase</strong>...</p>` 描述中）；同时验证搜索 HTML 标签名 `strong`（`GET /api/products?q=strong`）。
  2. 输入商品名称片段 `蓝牙`。
  3. 输入二级类目名称 `家具家装`（`P-ON-B` 属于该类目，但其名称和描述纯文本中不含「家具家装」四字）。
- **期望结果**：
  1. 搜 `SearchPhrase` 剥离 HTML 标签后命中 `蓝牙耳机A`（且自动排除非 `ONLINE` 的 `P-FZ`/`P-OFF`）；搜标签名 `strong` 不应命中。
  2. 搜 `蓝牙` 按名称命中 `蓝牙耳机A`。
  3. 搜类目名 `家具家装` 返回空结果（证明搜索范围严格限定为名称+去标签描述纯文本，不匹配类目名）。
- **实际结果**：
  - 搜 `SearchPhrase` 唯一命中 `蓝牙耳机A`（`total=1`）；搜 HTML 标签 `strong` 返回 `total=0`（后端使用 `Jsoup.parse(product.getDescription()).text()` 先剥离全部 HTML 标签再匹配纯文本）。
  - 搜 `蓝牙` 命中 `蓝牙耳机A`。
  - 搜 `家具家装` 返回 `total=0`，页面展示 `暂无在售商品`。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：搜索 SearchPhrase 剥标签命中 (t009_04a_search_stripped_html.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_04a_search_stripped_html.png) ｜ [📷 查看截图：按商品名片段「蓝牙」搜索命中 (t009_04b_search_by_name.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_04b_search_by_name.png) ｜ [📷 查看截图：搜索类目名「家具家装」不命中 (t009_04c_search_category_name_no_match.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_04c_search_category_name_no_match.png)

#### C-009-05 · 列表字段与主图规则
- **操作步骤**：对比列表中有商品图的 `蓝牙耳机A`（上传了 2 张图）与无商品图但描述含 `<img src="...">` 的 `极简数据线C（无图样例）`。
- **期望结果**：有商品图时主图取第一张商品图（`sort_order=0`）；无商品图时统一显示占位图 `/placeholder-product.svg`，富文本描述内的插图不得充当主图。
- **实际结果**：`蓝牙耳机A` 列表卡片 `img.src` 为第一张商品图 `/api/images/<uuid>.png`；`极简数据线C（无图样例）` 的 `mainImagePath=null`，列表卡片 `img.src` 为 `/placeholder-product.svg`，描述中的 `<img>` 未被当作主图。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：有图商品首图与无图商品统一占位图对比 (t009_05_main_image_and_placeholder.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_05_main_image_and_placeholder.png)

#### C-009-06 · `ONLINE` 详情可打开
- **操作步骤**：从首页列表点击 `蓝牙耳机A` 进入 `/products/1`。
- **期望结果**：详情页正常打开，展示完整商品信息（含主图与缩略图、名称、价格、二级类目、**库存数量**、富文本描述及「提交购买意向」按钮）。
- **实际结果**：`/products/1` 正常渲染，清晰展示类目 `手机数码`、库存 `5`、富文本加粗/斜体描述及多图预览。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：ONLINE 商品详情页完整展示（含库存=5） (t009_06_online_product_detail.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_06_online_product_detail.png)

---

### 5.2 负面与边界用例（Negative & Boundary）

#### C-009-07 · `FROZEN` 不出现在列表/搜索；直链只读
- **操作步骤**：
  1. 卖家对 `机械键盘FZ（冻结样例）`（`id=4`）的队首意向点击「开始处理队首」，使商品进入 `FROZEN` 状态。
  2. 检查首页列表与 `SearchPhrase` 搜索结果。
  3. 直接访问详情直链 `/products/4`，并尝试调用 `POST /api/products/4/intents`。
- **期望结果**：列表与搜索均不展示 `P-FZ`；直链 `/products/4` 可打开但处于只读状态，不可提交购买意向。
- **实际结果**：首页列表与搜索结果均不含 `机械键盘FZ（冻结样例）`；直链 `/products/4` 打开后顶部显示黄色警告横幅 `商品交易处理中，当前仅可查看，不能提交购买意向。`，按钮位置替换为灰色只读文字 `当前不可提交购买意向`（无提交按钮）；携带买家 Token 直调 `POST /api/products/4/intents` 被后端拒绝，返回 `HTTP 409 Conflict`（`code=40901`）。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：FROZEN 商品直链只读展示与警告横幅 (t009_07_frozen_direct_link_readonly.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_07_frozen_direct_link_readonly.png)

#### C-009-08 · `OFFLINE` 不可打开详情、不可提交意向
- **操作步骤**：
  1. 将 `显示器OFF（下架样例）`（`id=5`）置为 `OFFLINE` 下架状态，确认其不在列表与搜索结果中。
  2. 浏览器访问其详情直链 `/products/5`，并直调 `GET /api/products/5` 与 `POST /api/products/5/intents`。
- **期望结果**：买家端不可打开详情（返回 404 / 不可查看提示），不可提交购买意向。
- **实际结果**：`GET /api/products/5` 返回 `HTTP 404 Not Found`（`code=40401, message="商品已下架"`）；前端页面展示 `商品当前不可查看` 空态卡片与 `返回商品列表` 链接，不泄露任何下架商品信息，无提交按钮；直调 `POST /api/products/5/intents` 返回 `HTTP 409/404` 拒绝。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：OFFLINE 商品直链拒绝访问空态页 (t009_08_offline_detail_blocked.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_08_offline_detail_blocked.png)

#### C-009-09 · 分页与空态（最简可运行）
- **操作步骤**：
  1. 在售商品总数达到 12 件（每页默认 `PAGE_SIZE=10`），点击首页底部分页器切换到第 `2` 页。
  2. 在搜索框输入必无匹配结果的关键词 `NoSuchProductKeyword999`。
- **期望结果**：分页切换正常展示第 2 页剩余商品；搜索无结果时展示清晰空态提示，页面不崩溃。
- **实际结果**：第 1 页显示前 10 件商品，点击页码 `2` 后正常展示剩余 2 件在售商品；输入 `NoSuchProductKeyword999` 后页面平稳展示 `暂无在售商品` 空态组件。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：在售列表第 2 页分页展示 (t009_09a_pagination_page2.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_09a_pagination_page2.png) ｜ [📷 查看截图：搜索无匹配结果空态展示 (t009_09b_empty_search_state.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_09b_empty_search_state.png)

#### C-009-10 · 列表/搜索不含 `FROZEN`、`OFFLINE`（综合抽查）
- **操作步骤**：综合核对首页列表、搜索结果及 `GET /api/products?page=1&size=100` 响应 JSON。
- **期望结果**：所有返回项均为 `ONLINE` 在售商品，`P-FZ`（`id=4`）与 `P-OFF`（`id=5`）绝不混入。
- **实际结果**：接口与页面返回的商品 ID 集合严格排除 `4`（`FROZEN`）与 `5`（`OFFLINE`），后端 `ProductServiceImpl.browse()` 强制按 `ProductStatus.ONLINE` 过滤。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：列表与接口综合抽查排除 FROZEN/OFFLINE (t009_10_list_excludes_frozen_offline.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_10_list_excludes_frozen_offline.png)

#### C-009-11 · 搜索结果卡片不展示描述摘要、不展示库存
- **操作步骤**：搜索 `SearchPhrase` 命中富文本商品 `蓝牙耳机A`，检查结果卡片 DOM 与 `GET /api/products?q=SearchPhrase` 返回的 JSON 结构。
- **期望结果**：卡片不展示描述摘要、不展示库存，库存仅在详情页可见。
- **实际结果**：`ProductSummaryResponse` JSON 字段严格为 `["productId", "name", "price", "mainImagePath", "category2Id", "category2Name"]`，不含 `descriptionHtml` 与 `stock`；前端卡片 DOM 仅渲染图片、名称、类目名和价格。
- **结论**：☑ **通过（PASS）**
- **证据链接**：[📷 查看截图：搜索结果卡片字段核验（无描述摘要/无库存） (t009_11_card_fields_no_desc_no_stock.png)](https://github.com/Wen5555/OxStore/blob/main/docs/test/screenshots/t009/t009_11_card_fields_no_desc_no_stock.png)

---

## 六、Sprint Review 汇报一行汇总与禅道回写

| Task | PB | 禅道子需求 | 执行日期 | 验收结果 | 通过/总数 | 发现缺陷数 | 证据位置 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **T-009** | **PB-03** | **13924** | 2026-10-27 | ☑ **通过** | **11 / 11**（JUnit 21/21） | **0**（无阻塞或功能缺陷） | `docs/test/T-009-acceptance-report.md` 及 `screenshots/t009/` |
