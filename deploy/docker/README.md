# OxStore Docker 交付版 0.1.0-docker.1

本包用于软件工程实践课程的容器交付和本机演示，包含 Linux/amd64 的前端、后端和 MySQL 镜像。Windows 使用 Docker Desktop 的 Linux 容器模式；Linux 使用 Docker Engine。ARM 主机、正式公网部署及长期运行未在本轮验收。

## 1. 文件

- `images.tar.gz`：三服务完整镜像，离线导入后无需 Maven、Node.js 或联网拉取镜像。
- `compose.yml`、`.env.example`、`init-env.ps1`、`init-env.sh`：启动配置与本地初始化。
- `database/`：新库 schema 和已有数据库升级脚本。首次启动只对空数据卷建表。
- `build/`：本次镜像中实际运行的后端 JAR、前端静态文件压缩包。
- `build-guide.md`：后续打包版本附带的完整构建手册，含工具安装、构建命令、产物与重新打包步骤。
- `evidence/`：本次构建与容器验证结果。范围以验证报告为准。
- `manifest.json`、`SHA256SUMS`：版本、镜像身份和文件校验值。

## 2. 安装与启动

本轮实测 Docker Engine 29.8.2 / Compose 5.5.1；兼容版本需支持 `docker compose up --wait`。Windows 初始化脚本要求 PowerShell 7；Linux 初始化脚本要求 sh 和 openssl。

先下载完整 ZIP 并解压到本地目录，再从该目录执行。Windows：

```powershell
./init-env.ps1
docker load -i images.tar.gz
docker compose config -q
docker compose up --no-build --pull never --wait --wait-timeout 240
docker compose ps
```

Linux 将首行替换为 `sh ./init-env.sh`，其余 Docker 命令相同。初始化脚本仅在 `.env` 不存在时生成独立随机配置，不重置已有配置。首次管理员密码在本地 `.env` 的 `ADMIN_INITIAL_PASSWORD` 查看，用户名为 `admin`。

买家：<http://127.0.0.1:8088/>；卖家：<http://127.0.0.1:8088/admin/login>。端口冲突时修改 `.env` 中 `APP_PORT`。默认仅本机可访问，数据库和后端没有宿主机端口。

## 3. 停止、日志与数据

```powershell
docker compose logs --tail 100 backend
docker compose down
docker compose up --no-build --pull never --wait --wait-timeout 240
```

`down` 保留数据库和上传图片的数据卷；不要使用 `down -v` 删除真实业务数据。重建容器时保留相同 `COMPOSE_PROJECT_NAME`、数据卷和 `.env`；随意改变项目名称会连接到另一组新数据卷。

后端使用非 root 用户运行。前端待后端健康后启动；后端健康检查会查询数据库。Nginx 请求上限为 6 MiB，以容纳业务 5 MiB 主图及 multipart 开销。

## 4. 备份、升级与恢复

已有数据库不能直接用新库 schema 覆盖。升级前停止业务写入，备份数据库、图片和 `.env`，并在副本验证恢复。`TOKEN_LOOKUP_KEY` 随有效买家口令保持稳定。V2/V3 的适用条件和回退边界参见随包 `database/database-guide.md` 与 `database/runbook.md`。

更新程序镜像不自动执行数据库迁移。应用镜像回退和数据库恢复分别处理；DDL 隐式提交，不能假定换回旧镜像即可回退数据。

## 5. 构建复现与课程成果

完整构建手册位于源码 `docs/build.md`；2026-10-18 起使用更新后打包脚本制作的离线包同时提供 `build-guide.md`。已发布的旧包保留原文件，使用本节简要步骤。

从 GitHub Release 下载同版本源码 ZIP，安装 Docker 后，在源码根目录执行：

```powershell
docker build --platform linux/amd64 -t oxstore/backend:0.1.0-docker.1 backend
docker build --platform linux/amd64 -t oxstore/frontend:0.1.0-docker.1 frontend
```

后端构建镜像使用 Maven 3.9 / Java 17 并执行全部 JUnit 测试；前端使用 Node.js 20 和锁文件安装并执行 TypeScript/Vite 构建。上游基础标签可能更新，本次实际构建 digest 和运行镜像 ID 留在构建日志及 manifest；下载包包含本次确定镜像。

前端默认沿用锁文件和本机已验证的 `https://registry.npmmirror.com` 下载源；可用 `--build-arg NPM_REGISTRY=https://registry.npmjs.org` 显式覆盖。容器实测中官方 npm 源连接被重置，镜像源安装成功，没有关闭 TLS 校验。

可复现的容器验收脚本在 `scripts/verify_docker_release.py`，仅访问脚本新建的独立项目和数据卷，不连接已有实例。运行需要 Python 3.10+ 标准库和 Docker：

```powershell
python scripts/verify_docker_release.py --bundle . --output evidence/retest
```

真实页面录屏可通过 `scripts/verify_docker_ui.ps1` 和同目录模板复现；需 PowerShell 7、Node.js/npx、Google Chrome及可下载的 Playwright CLI 0.1.22。该脚本会发布测试商品并完成交易，仅用于无活跃商品的独立测试实例：

```powershell
./scripts/verify_docker_ui.ps1 -BaseUrl http://127.0.0.1:8088 -OutputDirectory evidence/ui-retest
```

运行时在掩码提示中输入该测试实例当前管理员密码。程序不使用模拟 API，视频与截图保存至指定输出目录。

实际执行结果、录屏和限制见 `evidence/verification.md`。本包证明该版本已验证的容器场景，不代表所有课程功能、正式服务器或全部性能指标均已验收。
