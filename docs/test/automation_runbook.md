# OxStore 自动化测试执行手册

更新日期：2026-10-18。

## 1. 测试入口

| 入口 | 环境 | 验证内容 | 结果 |
| --- | --- | --- | --- |
| Maven/JUnit | JDK17、Maven3.9+ | 状态机、DTO、安全、服务和Controller单元测试 | Surefire XML |
| `scripts/verify_docker_release.py` | Docker Linux引擎、Compose、Python3.10+及三服务镜像 | 真实Nginx/API/MySQL、重排作废、历史与重启 | `docker-results.json`、操作日志 |
| `scripts/verify_database.py` | 已构建JAR、Java17、Docker、Python3.10+ | 五表、约束、迁移、HTTP及持久化 | 数据库结果JSON |
| `frontend/e2e/buyer-seller-flows.spec.ts` | Node20、前端依赖、Playwright浏览器 | 使用模拟API的前端交互 | Playwright报告 |

容器验证和数据库验证各自创建专用实例；不要改成连接现有业务库。原有手动请求与截图保留在[历史记录](manual-api-history.md)。

## 2. 后端单元测试

从项目根目录执行，先用 `mvn -version` 确认实际使用JDK17：

```powershell
mvn -B -ntp -f backend/pom.xml clean verify
Get-ChildItem backend/target/surefire-reports/TEST-*.xml
```

以退出码0、`BUILD SUCCESS`、XML中失败/错误/跳过均为0判定本次通过。当前源码预期50项，新增或删除测试时同步更新清单。依赖下载有问题时按构建手册排查，不用 `-DskipTests` 代替验证。

## 3. 真实容器/API验证

### 3.1 准备

按[构建手册](../build.md)构建以下镜像，或从对应离线包导入：

```powershell
docker load -i <离线包目录>/images.tar.gz
docker image inspect oxstore/backend:0.1.0-docker.1 oxstore/frontend:0.1.0-docker.1 mysql:8.0.46
```

建立独立配置目录（输出目录应尚不存在）：

```powershell
python scripts/package_docker_release.py prepare --output .work/acceptance-bundle
```

此步骤只准备Compose、schema、脚本和手册，不导出或改写已有发布包。

### 3.2 执行

```powershell
python scripts/verify_docker_release.py --bundle .work/acceptance-bundle --output .work/acceptance-results
```

脚本自动生成测试凭据、随机项目名和本机端口，启动新MySQL数据卷，执行真实请求及断言，最后清理本次项目及数据卷；正常执行不需要输入管理员密码。

执行内容包括原有D01～D21和新增D22～D26。D03分别检查三个SPA入口，因此全部通过时共28条检查记录。接口覆盖另计19个方法/路由组合。

### 3.3 判定与归档

```powershell
Get-Content .work/acceptance-results/docker-results.json
Get-Content .work/acceptance-results/compose-operations.log
```

通过条件：脚本退出码0、`result=PASS`、每项 `status=PASS`，并核对 `endpoint_count=19`。`requests`仅保存脱敏路由模板和状态码，不含口令、JWT和密码。失败时保留失败结果，修正后使用新输出目录复测，避免混合多轮记录。

28项检查覆盖真实API与容器场景，不意味着全部前端页面或并发条件均已验收。

## 4. 数据库专项验证

后端构建成功后执行：

```powershell
python scripts/verify_database.py --java <JDK17目录>/bin/java.exe
```

脚本创建独立MySQL容器和三个专用测试库，校验新库、异常写入、V2/V3迁移、排队/口令/历史及重启。入口与历史24项结果见[数据库验证报告](db-validation.md)。脚本内历史基线字段不代替本次运行的源码身份，应在归档时补记实际提交与环境。

## 5. 前端交互测试

安装锁定依赖和Playwright Chromium后执行：

```powershell
npm --prefix frontend ci --registry=https://registry.npmmirror.com --no-audit --no-fund
Push-Location frontend
npx playwright install chromium
npm run test:e2e
Pop-Location
```

这套测试使用 `page.route/route.fulfill` 模拟API，验证前端交互。真实服务与数据库结果引用第3节，不能把模拟响应记成全栈联调通过。

## 6. 人工录屏

本次由张耀文手动录制，当前待补，不自动运行录屏脚本。建议使用独立演示实例，展示商品发布、买家排队与凭码自助、冻结/解冻、交易成功、失败重排/作废和历史记录；可同时展示自动化程序执行结果。

录制结束后，将视频可访问地址补入Wiki《第1次成果验收》的运行类别。录屏完成、覆盖范围与教师意见由实际结果填写。

## 7. 配套材料

- [测试用例设计及清单](test_case_design_and_inventory.md)
- [验收核对报告](acceptance-2026-10-18.md)
- [构建手册](../build.md)、[运行手册](../runbook.md)
