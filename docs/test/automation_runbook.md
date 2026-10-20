# OxStore 自动化测试执行手册

更新日期：2026-10-20。项目测试用例盘点见[测试用例设计及清单](test_case_design_and_inventory.md)。运行真实容器或会写入业务数据的测试时，必须使用脚本创建的专用环境，不得连接现有业务库。

## 1. 测试入口

| 入口 | 环境 | 验证内容 | 结果证据 |
| --- | --- | --- | --- |
| Maven/JUnit | JDK 17、Maven 3.9+ | 后端状态机、DTO、安全、服务及 Controller 单元测试 | `backend/target/surefire-reports/` |
| `scripts/verify_docker_release.py` | Docker Linux 引擎、Compose、Python 3.10+及所需服务镜像 | 真实 Nginx/API/MySQL、交易流程、历史及重启行为 | 指定输出目录中的 `docker-results.json`、操作日志 |
| `scripts/verify_database.py` | 已构建 JAR、Java 17、Docker、Python 3.10+ | 表结构、约束、迁移、HTTP、交易数据及持久化 | 数据库验证报告/JSON |
| `frontend/e2e/buyer-seller-flows.spec.ts` | Node 20、前端依赖、Playwright 浏览器 | 使用模拟 API 的前端交互 | Playwright 报告 |
| `tests/ui-smoke/` | JDK 17、Maven 3.9+、Chrome、运行中的 OxStore 前后端及隔离 MySQL | Selenium 真实浏览器 UI-001 主流程 | Surefire XML；失败时截图和浏览器日志 |
| `tests/performance/` | JMeter 5.6.3、运行中的后端及专用测试数据库 | API 负载、响应时间与并发队列不变量 | JTL、HTML 报告及 SQL 检查结果 |

容器验证和数据库验证各自创建专用实例；不要改为连接现有业务库。原有手动请求和截图记录见[手动 API 历史记录](manual-api-history.md)。

## 2. 后端单元测试

从项目根目录执行，先确认实际使用 JDK 17：

```powershell
mvn -version
mvn -B -ntp -f backend/pom.xml clean verify
Get-ChildItem backend/target/surefire-reports/TEST-*.xml
```

判定条件：命令退出码为 0、Maven 输出 `BUILD SUCCESS`，且 Surefire XML 中失败、错误、跳过均为 0。当前源码清单为 50 个测试方法；测试增删后应同步更新[用例清单](test_case_design_and_inventory.md)。依赖下载失败时按[构建手册](../build.md)排查，不用 `-DskipTests` 替代验证。

## 3. 真实容器/API 验证

### 3.1 准备

按[构建手册](../build.md)构建所需镜像，或从对应离线包导入：

```powershell
docker load -i <离线包目录>/images.tar.gz
docker image inspect oxstore/backend:0.1.0-docker.1 oxstore/frontend:0.1.0-docker.1 mysql:8.0.46
```

建立独立配置目录，输出目录应尚不存在：

```powershell
python scripts/package_docker_release.py prepare --output .work/acceptance-bundle
```

### 3.2 执行

```powershell
python scripts/verify_docker_release.py --bundle .work/acceptance-bundle --output .work/acceptance-results
```

脚本使用本次运行生成的测试凭据、随机项目名和端口，启动专用 MySQL 数据卷，执行真实请求及断言，并清理本次创建的项目与数据卷。具体场景数量以脚本输出为准。

### 3.3 判定与归档

```powershell
Get-Content .work/acceptance-results/docker-results.json
Get-Content .work/acceptance-results/compose-operations.log
```

通过条件：脚本退出码为 0、结果为 `PASS`、每项状态均为 `PASS`，并核对接口覆盖计数。失败时保留本轮结果；修正后使用新的输出目录重测，避免混淆不同轮次。容器/API 覆盖不代表所有 UI 页面或并发条件均已验收。

## 4. 数据库专项验证

后端构建成功后，从项目根目录执行：

```powershell
python scripts/verify_database.py --java <JDK17目录>/bin/java.exe
```

脚本会创建专用 MySQL 实例及测试库，验证新库、异常写入、数据库迁移、排队/口令/历史与重启持久化。历史结果和限制见[数据库验证报告](db-validation.md)；归档时应记录本次实际源码版本与环境。

## 5. 前端模拟 API 交互测试

安装锁定依赖及 Playwright Chromium 后执行：

```powershell
npm --prefix frontend ci --registry=https://registry.npmmirror.com --no-audit --no-fund
Push-Location frontend
npx playwright install chromium
npm run test:e2e
Pop-Location
```

该 suite 使用模拟 API，验证前端交互；它不能替代真实后端/API 或 Selenium 真实浏览器验收。

## 6. Selenium UI 冒烟测试

### 6.1 覆盖范围与已知结果

独立工程位于 `tests/ui-smoke/`，使用 Java 17、Selenium、JUnit 5 和真实 Chrome 浏览器访问运行中的 OxStore 前端及后端，不模拟 API。用例 UI-001 `buyerCanSubmitIntentAndSellerCanCompleteTheTrade` 覆盖：

1. 错误密码登录被拒绝，卖家保持在登录页。
2. 正确卖家凭据登录后台。
3. 发布唯一命名的测试商品。
4. 买家提交购买意向并取得查询口令。
5. 使用口令查询意向，验证买家信息和“排队中”状态。
6. 卖家处理队首并确认成交。
7. 验证队列清空，买家端不再显示售出的商品。

已报告的运行结果为 **1 个测试通过、0 失败、0 错误，Maven `BUILD SUCCESS`**。这只证明 UI-001 主流程在该次本机环境中通过，不代表完整 UI 失败路径或所有页面已经覆盖。

### 6.2 环境、安全与执行

需要 JDK 17、Maven 3.9+、Chrome/Chromium、本机 MySQL 8，以及正在运行的 OxStore 前端和后端。本机方式不要求 Docker。

**必须使用全新的一次性隔离测试数据库。**该测试会创建商品、意向和成交记录，不会自动清理；禁止连接生产库或日常开发库。若运行中断且已经写入数据，不要在同一测试库直接重跑。

完整的建库及 schema 初始化、后端/前端启动、环境变量配置、Docker 方式及故障排查见 [Selenium UI 测试说明](../../tests/ui-smoke/README.md)。启动服务后，在同一 PowerShell 会话设置 `UI_SMOKE_BASE_URL`、`UI_SMOKE_ADMIN_USERNAME`、`UI_SMOKE_ADMIN_PASSWORD` 和 `UI_SMOKE_ALLOW_MUTATIONS=true`，然后执行：

```powershell
cd tests\ui-smoke
mvn test
```

仅在一次性隔离测试库上设置 `UI_SMOKE_ALLOW_MUTATIONS=true`。默认无头运行；设置 `UI_SMOKE_HEADLESS=false` 可观察浏览器。首次运行时 Selenium Manager 需要下载与 Chrome 版本匹配的 ChromeDriver，也可使用 `CHROME_DRIVER_PATH` 指定兼容驱动。

### 6.3 证据与覆盖限制

- JUnit/Surefire 报告：`tests/ui-smoke/target/surefire-reports/`
- 失败截图及浏览器日志：`tests/ui-smoke/target/ui-smoke-artifacts/`
- 成功运行不会自动录制视频；如需录屏，设置 `UI_SMOKE_HEADLESS=false` 后使用屏幕录制工具。
- Selenium/Chrome 出现 CDP 版本警告时，以测试结果和 Maven 退出码判定是否通过。
- 后续待补：独立的错误密码登录测试、未登录访问后台、表单校验错误及其他页面/异常操作覆盖。UI-001 已含错误密码检查，但这不等同于独立失败路径套件。

## 7. JMeter 性能与并发测试

JMeter 测试计划为 `tests/performance/oxstore-api-load.jmx`。它直接请求后端 API，并会写入购买意向；只可针对隔离测试数据库运行。完整准备步骤、SLA 阈值、命令和并发 SQL 检查见[性能测试说明](../../tests/performance/README.md)。

示例命令（从项目根目录运行；`outputs` 中的目标文件/目录应不存在）：

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$results = "outputs\jmeter-$stamp.jtl"
$report = "outputs\jmeter-report-$stamp"
& "C:\tools\apache-jmeter-5.6.3\bin\jmeter.bat" `
  -n -t "tests\performance\oxstore-api-load.jmx" `
  -Jthreads=5 -Jramp=10 -Jloops=5 `
  -l $results -e -o $report
if ($LASTEXITCODE -ne 0) { throw "JMeter failed: $LASTEXITCODE" }
```

只有 JMeter 退出码为 0 且报告中的样本错误率、各接口 p95 均满足约定阈值，才能判为性能 SLA 通过。并发数据一致性需另运行 `tests/performance/concurrency-invariants.sql`；固定数量断言必须针对专用空测试库执行，不能对已积累意向的库重复套用。

## 8. 人工录屏

人工录屏独立于自动化测试。录制时使用专用演示/测试环境，不在生产或日常业务库操作。建议展示商品发布、买家提交及凭码查询、冻结/解冻、交易成功、失败重排/作废和历史记录；如果要展示 Selenium 流程，应设置 `UI_SMOKE_HEADLESS=false` 并使用屏幕录制工具。

录制完成后，将可访问的视频地址、实际覆盖内容和验收意见补入对应交付记录。不得用截图、JSON、旧视频或自动化测试报告替代本次录屏证据。

## 9. 旧手动 API 记录与配套资料

旧的手动请求和截图说明仅供历史参考，部分示例凭据、响应和截图可能已过时；以当前 API 文档、自动化脚本和最新测试结果为准：

- [手动 API 历史记录](manual-api-history.md)
- [测试用例设计及清单](test_case_design_and_inventory.md)
- [验收核对报告](acceptance-2026-10-18.md)
- [构建手册](../build.md)
- [项目运行手册](../runbook.md)
