# OxStore 部署运行手册 (Runbook)

## 1. 前置条件
- JDK 17 (Temurin)
- Node.js 20
- Docker & Docker Compose

## 2. 环境变量配置（基于 DEL-04 部署要求）
复制 `.env.example` 为 `.env`，配置 `DB_PASSWORD`、`JWT_SECRET`、`TOKEN_LOOKUP_KEY`、`ADMIN_INITIAL_PASSWORD`。**不允许在仓库提交真实密码。**

## 3. 本地启动（后端与前端）
**后端**：`cd backend && mvn spring-boot:run`
**前端**：`cd frontend && npm install && npm run dev`

## 4. Docker 部署（对应课程工程交付项）
```bash
docker compose up --build -d