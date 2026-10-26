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
| JWT_SECRET | 顾客/卖家 JWT 签名密钥，至少 32 字节 | 必填 |
| ADMIN_INITIAL_PASSWORD | 首次卖家密码，8–64 位，含字母/数字/特殊字符 | 首次建号必填；已有 admin 后可留空 |
| DB_HOST / DB_PORT | MySQL 地址与端口 | localhost / 3306；Compose 使用 mysql |
| DB_NAME / DB_USERNAME | 库名与用户名 | shop / root |

密码和密钥使用独立随机值，真实配置保留在本地。首次创建账号后，重新设置初始化密码不会覆盖已有密码，应通过后台改密功能修改。更换 JWT 密钥会使既有登录令牌失效，账号密码不受影响。

## Docker Compose

完成环境配置后，在项目根目录启动：

```powershell
docker compose up -d --build
docker compose ps
```

前台地址为 `http://localhost/`，MySQL 默认映射宿主机 3306 端口，前端映射 80 端口；后端由 Nginx 在容器网络内代理。`mysql_data` 保存数据库，`uploads` 保存图片。正常停止会保留数据卷。

```powershell
docker compose logs --tail 100 backend
docker compose down
```

空数据库卷首次启动会导入 schema；已有卷再次启动不会自动更新结构。Nginx 上传上限为 46 MiB，以支持最多 9 张、每张不超过 5 MiB 的商品图片。

## 本地开发

### 1. 建库

空库初始化见[数据库说明](design/database.md#5-首次建库)。当前 JPA 配置为 `ddl-auto: none`，SQL 初始化为 `mode: never`，因此启动应用前应先导入 schema。

### 2. 配置并启动后端

在终端输入与本地实例一致的配置；下面的输入使用 PowerShell 7 的掩码显示：

```powershell
$env:DB_PASSWORD = Read-Host 'MySQL密码' -MaskInput
$env:JWT_SECRET = Read-Host 'JWT密钥' -MaskInput
$env:ADMIN_INITIAL_PASSWORD = Read-Host '首次管理员密码（已有账号可留空）' -MaskInput
cd backend
mvn spring-boot:run
```

后端默认端口 8080。如使用其他 MySQL 地址，按配置表设置 `$env:DB_HOST`、`$env:DB_PORT`、`$env:DB_NAME`、`$env:DB_USERNAME`。

### 3. 启动前端

在另一个终端，从项目根目录执行：

```powershell
cd frontend
npm install
npm run dev
```

开发前台运行在 `http://localhost:5173/`，Vite 将 `/api` 代理到 `http://localhost:8080`。当前更新范围为后端 API 与上传代理限制；现有前端尚未迁移到顾客登录和迭代 2 API，不能视为前后端端到端已联调。

## 已有数据库升级

1. 暂停业务写入，记录行数、状态分布和升级时间，先备份并在副本恢复演练。
2. 旧三表库先结束所有 `IN_TRANSACTION` 意向，再用 MySQL 客户端执行 `backend/src/main/resources/db/migrations/V2__queue_history.sql`。保留默认遇错停止行为，不启用 `--force`。
3. 已执行旧版 V2 的库按需运行 V3 收紧交易结果约束；新库和修订后的 V2 无需额外执行 V3。V3 若发现不完整旧结果，会拒绝升级，须核实真实结果。
4. 结束所有交易中意向后执行 `backend/src/main/resources/db/migrations/V4__iteration2_customer_inventory_catalog.sql`。
5. 核对迁移前后行数、状态分布、中文内容及队列序号。旧商品库存未知，因此 V4 会将其设为 0 并下架；卖家须核实实际库存后补充库存、手动上架。

V4 不会创建顾客账号或转换旧口令记录为新顾客历史；旧队列意向会结束为失败。商品图片路径会保留。MySQL DDL 会隐式提交；任一迁移中途失败时先核对结构与备份，不要盲目重跑。空库 schema 不能替代迁移。回退应停写并恢复已演练的备份，旧程序继续写入会破坏新数据语义。

备份命令、表结构及迁移前后检查项见[数据库设计与使用说明](design/database.md)。

## 构建与验证

- 完整步骤见 `docs/build.md`（离线包后续可参考 `build-guide.md`），包含工具安装要求、源码版本、Docker 与本机构建、产物位置及离线打包。
- 后端：在项目根目录运行 `mvn -B -ntp -f backend/pom.xml clean verify`，生成 `backend/target/shop-0.1.0.jar`，并执行包含 H2 HTTP 集成测试的后端验证。
- 前端：在项目根目录运行 `npm --prefix frontend ci --registry=https://registry.npmmirror.com --no-audit --no-fund`，成功后运行 `npm --prefix frontend run build`，生成 `frontend/dist/`。
- V4 MySQL 迁移验证：需在独立 MySQL 副本演练；当前环境未执行。现有 `scripts/verify_database.py` 仍面向旧版 schema/API，不适用于迭代 2。

接口契约见[接口说明](design/api.md)。旧数据库验证数据见[历史验证报告](test/db-validation.md)，不代表当前迭代 2 的 MySQL 迁移已验证。
