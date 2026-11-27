# 挑战需求B 构建过程手册

R1／王嘉慧，2026-11-27。本手册对应第4次成果验收的“构建”部分，产出后端可执行JAR、前端静态文件与构建证据包；Docker镜像和数据库部署另按部署手册执行。

## 1. 源码与环境

- 本轮构建源码：`main@c1b8ddc6d8f33e958365df3e37bb9a9752c2d83e`，已包含PR #35前端修复、PR #36受控测试及挑战B验收材料；前后端源码树与`develop@075a3ea`相同。
- 构建交付版本：`0.1.0-iteration3-build.1`；应用POM及package.json版本仍为`0.1.0`，未为打包修改业务版本。
- 实测环境：Windows 11 amd64、PowerShell 7、Oracle JDK 21.0.10、Maven 3.9.9、Node.js 22.22.3、npm 10.9.8、Python 3.12.14；打包脚本要求Python 3.11+。
- 后端POM目标为Java 17；本次用JDK21编译release17，包内主类字节码版本核验为61。原Docker构建使用Java17／Node20，本轮不声称重新执行了Docker构建。
- 首次构建需联网下载Maven/npm依赖；本轮后端测试使用H2，无需安装MySQL或配置业务密码。打包脚本仅用Python标准库。

复现时可单独克隆源码并检出本次标签`v0.1.0-iteration3-build.1`，其中包含本手册及打包脚本；前后端源码与上述`c1b8ddc`基线一致，标签只增加构建文档、脚本和记录。执行下文前，所在目录应同时包含`backend/`、`frontend/`、`scripts/`，并检查：

```powershell
git rev-parse HEAD
java -version
mvn -version
node --version
npm --version
python --version
```

## 2. 执行构建

从源码根目录开始。每条命令失败时先排查日志，不继续打包；不要跳过后端测试。

```powershell
New-Item -ItemType Directory -Force .work/iteration3-build/logs | Out-Null
mvn -B -ntp -f backend/pom.xml clean verify *> .work/iteration3-build/logs/backend.log
if ($LASTEXITCODE -ne 0) { throw '后端构建失败，请查看backend.log' }

Push-Location frontend
try {
    npm ci --registry=https://registry.npmjs.org *> ../.work/iteration3-build/logs/npm-ci.log
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请查看npm-ci.log' }
    npm run build *> ../.work/iteration3-build/logs/frontend.log
    if ($LASTEXITCODE -ne 0) { throw '前端构建失败，请查看frontend.log' }
} finally { Pop-Location }
```

后端执行编译、JUnit和Spring Boot重新打包，产物为`backend/target/shop-0.1.0.jar`。前端通过锁文件安装依赖，执行TypeScript检查及Vite生产构建，产物为`frontend/dist/`。不要将源码开发服务器当作静态构建产物。

## 3. 整理与校验构建包

本轮提供[打包脚本](../../scripts/package_iteration3_build.py)。在含该脚本的构建交付分支／提交上运行，应用源码须与`--source-commit`一致。记录实际工具版本后执行：

```powershell
@{
    java = (java -version 2>&1 | Out-String).Trim()
    maven = (mvn -version | Out-String).Trim()
    node = (node --version | Out-String).Trim()
    npm = (npm --version | Out-String).Trim()
    python = (python --version | Out-String).Trim()
} | ConvertTo-Json | Set-Content -Encoding utf8 .work/iteration3-build/logs/tools.json

# TypeScript可能重生成这两个已跟踪文件；在干净、独立构建目录中核对差异后还原生成内容。
git diff -- frontend/tsconfig.node.tsbuildinfo frontend/vite.config.js
git restore -- frontend/tsconfig.node.tsbuildinfo frontend/vite.config.js

python scripts/package_iteration3_build.py --source-commit c1b8ddc6d8f33e958365df3e37bb9a9752c2d83e --log-dir .work/iteration3-build/logs --output-dir .work/iteration3-build/package
Get-FileHash .work/iteration3-build/package/OxStore-0.1.0-iteration3-build.1.zip -Algorithm SHA256
```

仅对本次构建生成的这两个文件执行restore，不要用该命令清除已有业务修改。打包目录必须是新的；脚本拒绝覆盖已有同名目录。第二次构建换一个输出目录。

包内包含`build/backend/`、`build/frontend/`、本手册、`evidence/logs/`、JUnit测试摘要、`manifest.json`和逐文件`SHA256SUMS.txt`。脚本检查JUnit无失败／错误／跳过、成功构建日志、JAR可读取且主类目标Java17、HTML引用的assets存在，并重新读取ZIP逐项校验SHA-256。不会打包node_modules、源码上传目录、数据库数据或运行.env。

## 4. 本轮实际结果

| 检查 | 2026-11-27实际结果 |
| --- | --- |
| 后端`clean verify` | 118项，失败0、错误0、跳过0，BUILD SUCCESS；JAR已重新生成 |
| 前端`npm ci` | 按锁文件安装165个包成功；审计提示5项依赖问题（3 moderate、2 high），本轮未自动升级依赖 |
| TypeScript与Vite | 成功，3123个模块；静态资源已生成。存在大于500kB的chunk提示，未阻断构建 |
| 产物与证据 | 见本轮包内manifest、JUnit摘要、日志及SHA256SUMS；构建结果不替代真实MySQL、页面或部署验收 |

[下载构建产物及证据](https://github.com/Wen5555/OxStore/releases/tag/v0.1.0-iteration3-build.1)。重新构建时须以当次日志及测试结果为准；时间戳和压缩结果可能不同，不要求得到字节完全相同的ZIP。
