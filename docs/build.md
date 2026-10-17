# OxStore 构建手册

更新日期：2026-10-18。

本手册说明如何从项目源码生成后端 JAR、前端静态文件和 Docker 镜像，以及如何打包构建产物。推荐使用 Docker 构建，构建工具由 Dockerfile 提供；需要单独生成 JAR 或前端静态文件时，也可使用本机工具构建。

## 1. 构建准备

进入同时包含 `backend/`、`frontend/`、`scripts/` 的项目根目录。下文各节均从该目录开始，命令使用 PowerShell 7；未使用 PowerShell 专用语法的 Docker 命令也可在 Linux shell 中执行。

后端应用版本由 `backend/pom.xml` 定义，前端应用版本由 `frontend/package.json` 定义，当前均为 `0.1.0`。下文镜像标签采用打包脚本中配置的 `0.1.0-docker.1`，目标平台为 `linux/amd64`。调整版本时，应同步更新构建命令、打包脚本的 `VERSION` 和部署配置中的 `OXSTORE_VERSION`。

## 2. 工具与安装要求

| 路线 | 工具与要求 | 获取方式 |
| --- | --- | --- |
| Docker 构建（推荐） | Windows 使用 Docker Desktop 的 Linux 容器模式；Linux 使用 Docker Engine；构建器须支持 Dockerfile 的 BuildKit 缓存挂载 | [Docker 官方安装说明](https://docs.docker.com/engine/install/)；Windows 可用 [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) |
| 本机后端构建 | JDK 17、Maven 3.9+；把 JDK 配到 `JAVA_HOME`，把 Maven `bin` 加入 `PATH` | [Eclipse Temurin 17](https://adoptium.net/temurin/releases/?version=17)、[Apache Maven](https://maven.apache.org/download.cgi) |
| 本机前端构建 | Node.js 20 及其配套 npm；Dockerfile 使用 Node.js 20 | [Node.js 官方下载](https://nodejs.org/en/download) |
| 离线打包 | Python 3.11+，仅标准库；脚本使用 `hashlib.file_digest` | [Python 官方下载](https://www.python.org/downloads/) |
| 安装运行与回归 | Docker Compose；离线包启动需支持 `up --wait`；容器验证脚本单独要求 Python 3.10+ | [Compose 安装说明](https://docs.docker.com/compose/install/) |

后端构建阶段使用 `maven:3.9-eclipse-temurin-17`，前端使用 `node:20-alpine`。Docker 构建不要求宿主机另装 Java、Maven、Node.js 或 MySQL；首次构建需要联网获取基础镜像及依赖。本机编译和现有单元测试不要求运行 MySQL，启动应用及数据库集成验证另有要求。

按所选路线检查环境：

```powershell
# Docker 路线：必须能看到服务端信息
docker version
docker compose version
docker buildx version
```

```powershell
# 本机路线：确认 mvn 输出中实际使用 Java 17
java -version
mvn -version
node --version
npm --version
```

如果本机默认 Java 或 Node 版本不同，使用 Docker 路线可以沿用项目的构建环境。离线安装已有镜像包只需 Docker，不需要重新构建。

## 3. 构建配置与目录

| 文件 | 作用 |
| --- | --- |
| `backend/pom.xml` | Java 17、Spring Boot 3.2.5、依赖及 Spring Boot 可执行 JAR 打包配置 |
| `backend/Dockerfile` | Maven 构建、JUnit 测试、健康检查程序编译和 JRE 运行镜像 |
| `backend/docker/HealthCheck.java` | 在运行镜像中执行后端就绪检查 |
| `frontend/package.json` | `build` 脚本执行 `tsc -b && vite build` |
| `frontend/package-lock.json` | 锁定前端依赖；使用 `npm ci` 安装 |
| `frontend/Dockerfile` | Node 构建、Nginx 静态资源运行镜像 |
| `frontend/nginx.conf` | 前端路由回退和 `/api` 代理配置 |
| `docker-compose.yml` | 源码开发用编排，含前后端 `build` 配置，默认宿主机端口 80、3306 |
| `deploy/docker/compose.yml` | 离线包运行编排，使用已构建镜像，默认仅绑定 `127.0.0.1:8088` |
| `scripts/package_docker_release.py` | 提取镜像内产物、导出三服务镜像、生成清单和 ZIP |

源码构建与离线包运行的 Compose 文件用途不同。离线包不含源码构建上下文，启动时使用 `--no-build --pull never`。

## 4. Docker 镜像构建

### 4.1 构建前后端

在源码根目录逐条执行，上一条失败时先排查，不继续导出：

```powershell
docker build --platform linux/amd64 --progress plain -t oxstore/backend:0.1.0-docker.1 backend
docker build --platform linux/amd64 --progress plain -t oxstore/frontend:0.1.0-docker.1 frontend
docker pull --platform linux/amd64 mysql:8.0.46
```

后端 Dockerfile 先执行 `mvn -B -ntp clean verify`，通过后编译健康检查程序，再把 JAR 与健康检查类复制到 Java 17 JRE 镜像。运行入口为 `java -jar /app/app.jar`，运行用户为 `10001:10001`。

前端 Dockerfile 先执行 `npm ci`，再执行 TypeScript 检查与 Vite 生产构建，把 `dist/` 复制到 Nginx 的 `/usr/share/nginx/html`。MySQL 使用现成的官方镜像，随交付包一起导出。

前端默认依赖源为 `https://registry.npmmirror.com`。如该源无法访问或不满足版本要求，可通过构建参数切换，例如：

```powershell
docker build --platform linux/amd64 --progress plain --build-arg NPM_REGISTRY=https://registry.npmjs.org -t oxstore/frontend:0.1.0-docker.1 frontend
```

基础镜像标签可能更新，重新构建得到的镜像 ID 可能不同。打包生成的 `manifest.json` 用于记录实际镜像身份与构建环境。

### 4.2 检查构建结果

```powershell
docker image inspect --format '{{.RepoTags}} {{.Os}}/{{.Architecture}} {{.Id}}' oxstore/backend:0.1.0-docker.1 oxstore/frontend:0.1.0-docker.1 mysql:8.0.46
```

三张镜像都应存在且平台为 `linux/amd64`。后端日志应包含 `BUILD SUCCESS`，测试汇总的 `Failures`、`Errors`、`Skipped` 均应为 0；前端日志应包含 TypeScript/Vite 构建完成信息。构建日志与测试结果应随产物保存。

## 5. 本机分别构建（可选）

### 5.1 后端 JAR

在源码根目录执行。`-f` 指定 POM，可避免切换目录后误操作：

```powershell
mvn -B -ntp -f backend/pom.xml clean verify
Get-Item backend/target/shop-0.1.0.jar
Get-ChildItem backend/target/surefire-reports/TEST-*.xml
jar tf backend/target/shop-0.1.0.jar | Select-String 'BOOT-INF/' | Select-Object -First 5
```

成功后得到可执行 JAR `backend/target/shop-0.1.0.jar` 和 JUnit XML。`.jar.original` 是重打包前的文件，部署使用不带 `.original` 的 JAR。该步骤不启动服务；运行数据库配置见项目运行手册。

### 5.2 前端静态资源

```powershell
npm --prefix frontend ci --registry=https://registry.npmmirror.com --no-audit --no-fund
npm --prefix frontend run build
Get-Item frontend/dist/index.html
Get-ChildItem frontend/dist/assets
```

`npm ci` 按锁文件安装，并重新生成前端依赖目录。应在依赖安装成功后再执行构建；不要为了绕过错误随意删除锁文件。`npm run build` 不执行端到端测试。

产物为 `frontend/dist/`，部署时使用完整目录。Vite 开发服务器的 `/api` 代理只在开发模式生效，生产部署按现有 Nginx 配置转发；直接双击 `dist/index.html` 不能验证完整业务。

## 6. 打包镜像与构建产物

当前打包脚本固定使用 `0.1.0-docker.1` 与 `mysql:8.0.46`。三张镜像构建或拉取成功后，在源码根目录选择一个尚不存在的输出目录：

```powershell
$releaseDirectory = Join-Path $PWD ('outputs/build-delivery/OxStore-0.1.0-docker.1-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
python scripts/package_docker_release.py prepare --output $releaseDirectory
```

`prepare` 创建目录并复制公开配置、手册、数据库脚本和验证脚本。此时尚未导出镜像，也未生成 ZIP。可以先在独立实例执行容器验证，保存真实结果：

```powershell
python scripts/verify_docker_release.py --bundle $releaseDirectory --output (Join-Path $releaseDirectory 'evidence/retest')
```

验证程序需要 Docker、Python 3.10+，会创建独立项目和数据卷，并在结束时清理它们。浏览器页面测试的操作方法见离线包 README。

将构建日志和测试结果保存到输出目录的 `evidence/` 后，再导出：

```powershell
python scripts/package_docker_release.py export --output $releaseDirectory
Get-Content (Join-Path $releaseDirectory 'manifest.json')
Get-Content (Join-Path $releaseDirectory 'SHA256SUMS')
Get-FileHash -Algorithm SHA256 ($releaseDirectory + '.zip')
```

`export` 从运行镜像提取 JAR 和前端静态产物，导出三张镜像为 `images.tar.gz`，并生成 manifest、逐文件校验清单和同名 ZIP。清单中记录当前 Git HEAD、工作区状态、镜像 ID 与平台信息，用于关联源码和构建产物。

输出目录只放置构建产物、配置模板和相关文档，运行环境使用的 `.env`、密码与密钥应单独保存。重新导出时使用新的目录，避免覆盖已有产物。

## 7. 构建产物清单

| 结果 | 位置 | 用途 |
| --- | --- | --- |
| 后端 JAR | 本机：`backend/target/shop-0.1.0.jar`；离线包：`build/shop-0.1.0.jar` | Spring Boot 后端产物 |
| 前端静态文件 | 本机：`frontend/dist/`；离线包：`build/frontend-dist.zip` | Nginx 托管的完整前端产物 |
| 运行镜像 | `oxstore/backend:0.1.0-docker.1`、`oxstore/frontend:0.1.0-docker.1`、`mysql:8.0.46` | 容器运行；统一保存在 `images.tar.gz` |
| 版本与校验 | `manifest.json`、`SHA256SUMS` | 源码版本、镜像 ID、平台、文件哈希 |
| 构建与测试结果 | `evidence/` 中的构建日志、JUnit XML 和容器结果 | 检查构建与测试状态 |
| 安装资料 | `README.md`、`compose.yml`、初始化脚本和 `database/` | 导入镜像、配置与启动 |
| 构建手册 | 源码：`docs/build.md`；离线包：`build-guide.md` | 构建步骤与工具说明 |

## 8. 常见问题

| 现象 | 处理 |
| --- | --- |
| Docker 只有客户端信息，提示 `dockerDesktopLinuxEngine` 管道不存在 | 启动 Docker Desktop，切换 Linux 容器，等待引擎就绪，再执行 `docker version` |
| `mvn -version` 使用 Java 21 等其他版本 | 把 `JAVA_HOME` 指向已安装的 JDK 17 并调整当前终端 PATH，或按第 4 节使用容器构建 |
| Maven/镜像依赖下载失败 | 根据日志定位失败地址，检查网络与代理配置后重试 |
| 前端 `npm ci` 提示清单与锁文件不一致 | 核对是否使用同一源码版本的两个文件；有意修改依赖后按项目流程更新锁文件 |
| TypeScript 错误或 JUnit 失败 | 根据报错修正代码或配置，重新执行构建 |
| Vite 提示大 chunk | 属于构建警告；仍需确认命令成功与产物存在，性能结果另行验证 |
| 打包提示找不到镜像或平台不符 | 核对第 4 节镜像标签及 `linux/amd64` 平台，再重新构建或拉取 |
| 离线启动提示缺少配置或找不到 schema | 确认在完整离线包根目录运行初始化脚本，且 `database/schema.sql` 存在 |

## 9. 相关文档

- 运行配置、数据库初始化与升级：源码 `docs/runbook.md`。
- 离线包安装与启动：源码 `deploy/docker/README.md`，打包后位于包根目录的 `README.md`。
- 构建文档核对记录：源码 `docs/test/build-guide-check.md`。
- 容器运行验证报告：源码 `docs/test/docker-release.md`。
