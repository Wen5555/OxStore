# OxStore 运行手册

## 环境要求

- 本地开发：JDK 17、Maven 3.9+、Node.js 20+、MySQL 8.0.16+。
- 容器部署：Docker 和 Docker Compose。
- 数据库字符集使用 utf8mb4；应用与数据库业务时区统一为 Asia/Shanghai。

## 配置说明

从项目根目录复制 `.env.example` 为 `.env`。Compose 自动读取该文件；本地 Spring Boot 读取终端环境变量。

| 变量 | 说明 | 默认或适用条件 |
| --- | --- | --- |
| DB_PASSWORD | 数据库密码 | 必填 |
| JWT_SECRET | JWT签名密钥，至少32字节 | 必填 |
| TOKEN_LOOKUP_KEY | HMAC口令查询密钥，至少32字节 | 必填，存在有效买家口令时保持稳定 |
| ADMIN_INITIAL_PASSWORD | 首次卖家密码，8–64位，含字母/数字/特殊字符 | 首次建号必填；已有admin后可留空 |
| DB_HOST / DB_PORT | MySQL地址与端口 | localhost / 3306；Compose使用mysql |
| DB_NAME / DB_USERNAME | 库名与用户名 | shop / root |
| HISTORY_COMPLETE_SINCE | 旧库升级截止时间 | 新库留空；迁移后按真实时间填写 |

密码和密钥使用独立随机值，真实配置保留在本地。首次创建账号后，重新设置初始化密码不会覆盖已有密码，应通过后台改密功能修改。

`TOKEN_LOOKUP_KEY`支撑已发放口令的索引查找，应随数据库备份妥善保留；JWT密钥与它独立管理。更换JWT密钥会使旧登录令牌失效，卖家密码不受影响。旧公开的默认凭据应更换为实例自己的值。

## Docker Compose

完成环境配置后，在项目根目录启动：

```powershell
docker compose up -d --build
docker compose ps
```

前台为 `http://localhost/`，卖家登录为 `http://localhost/admin/login`，用户名 `admin`。MySQL默认映射宿主机3306端口，前端映射80端口；后端由Nginx在容器网络内代理。

日志与停止：

```powershell
docker compose logs --tail 100 backend
docker compose down
```

`mysql_data`保存数据库，`uploads`保存图片。正常停止保留这些数据卷。空数据库卷首次启动会导入schema；已有卷再次启动不会自动更新结构。

## 本地开发

### 1. 建库

空库初始化见[数据库说明](design/database.md#首次建库)。当前JPA配置为 `ddl-auto: none`，SQL初始化为 `mode: never`，因此启动应用前应先导入schema。

### 2. 配置并启动后端

在终端输入与本地实例一致的配置；下面的输入使用PowerShell7的掩码显示。已有实例使用保存的密钥，避免每次启动重新生成：

```powershell
$env:DB_PASSWORD = Read-Host 'MySQL密码' -MaskInput
$env:JWT_SECRET = Read-Host 'JWT密钥' -MaskInput
$env:TOKEN_LOOKUP_KEY = Read-Host '口令索引密钥' -MaskInput
$env:ADMIN_INITIAL_PASSWORD = Read-Host '首次管理员密码（已有账号可留空）' -MaskInput
cd backend
mvn spring-boot:run
```

后端默认端口8080。如使用其他MySQL地址，按配置表设置 `$env:DB_HOST`、`$env:DB_PORT`、`$env:DB_NAME`、`$env:DB_USERNAME`。

### 3. 启动前端

在另一个终端，从项目根目录执行：

```powershell
cd frontend
npm install
npm run dev
```

开发前台运行在 `http://localhost:5173/`，Vite将 `/api`代理到 `http://localhost:8080`。

## 已有数据库升级

1. 暂停业务写入，记录行数、状态分布和升级时间，先备份并在副本恢复演练。
2. 旧三表库先结束所有 `IN_TRANSACTION`意向，再用mysql客户端执行 `backend/src/main/resources/db/migrations/V2__queue_history.sql`。保留默认遇错停止行为，不启用 `--force`。
3. 已经执行旧版V2的库另用V3收紧交易结果约束；新库和修订后的V2无需额外执行V3。V3若发现不完整旧结果，会拒绝升级，须核实真实结果。
4. 核对迁移前后行数、状态、联系方式、原时间及队列序号无空/重复；设置 `HISTORY_COMPLETE_SINCE`，例如 `2026-10-01T10:00:00`，后台会标识旧历史可能不完整。

MySQL DDL会隐式提交。V2只有在前置检查拦截且未改表时，才能处理交易状态后重试；其他中途失败应先核对结构与备份。空库schema不能替代迁移。需要回退时停写并恢复已演练的备份，旧程序继续写入会破坏新历史语义。

旧版已覆盖的首次时间、未记录的失败历史，以及已清空的口令凭证无法恢复。旧有效码的 `token_lookup`可保留NULL，兼容路径逐个BCrypt校验；大量旧码下的查询性能需单独验证，勿为提速清除仍有效的口令。

备份命令、表结构及迁移前后检查项见[数据库设计与使用说明](design/database.md)。

## 构建与验证

- 后端：在backend运行 `mvn test package`。
- 前端：在frontend运行 `npm run build`。
- 数据库集成验证：构建后端后，在根目录运行 `python scripts/verify_database.py`。

脚本创建独立MySQL测试容器并自动清理本次容器。验证报告见[数据库验证](test/db-validation.md)，交易请求及响应含义见[接口说明](design/api.md)。
