# OxStore 部署运行手册 (Runbook)

## 1. 前置条件
- **JDK 17** (Temurin，已验证 `java -version` 为 17.x)
- **Node.js 20** (验证 `node -v` 为 20.x)
- **Maven** (用于后端构建，未配置可参照 Maven 官方文档)
- **Docker & Docker Compose** (用于容器化部署)

## 2. 环境变量配置（基于 DEL-04 部署要求）
复制 `.env.example` 为 `.env`，配置以下变量：
- `DB_PASSWORD`：本地或容器数据库密码（新增，默认值已被覆盖逻辑兼容，不影响 Jenkins/Docker）。
- `JWT_SECRET`：JWT 签名密钥（建议 `openssl rand -hex 32` 生成）。
- `TOKEN_LOOKUP_KEY`：Token 索引密钥（同上）。
- `ADMIN_INITIAL_PASSWORD`：唯一卖家账号初始密码。

⚠️ **安全提醒**：严禁在仓库、聊天记录或日志中提交真实密码。`.env` 文件已在 `.gitignore` 中。

## 3. 本地启动（前后端分离）
**步骤 1：启动后端**
```bash
cd backend
mvn spring-boot:run