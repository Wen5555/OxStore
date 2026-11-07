# 拍卖模式数据库验证报告（P-A01 / P-A02）

- 验证日期：2026-11-06（Asia/Shanghai）。
- 任务负责人：张耀文，软件2401，2412190723。
- 环境：MySQL 8.0.46（Docker 29.8.2 一次性容器，仅绑定回环地址）、Java 21.0.8 运行（编译目标 Java 17）、Maven 3.9.12。后端以 `ddl-auto=validate` 连接专用容器，未连接任何已有业务库。
- 基线提交：`6b84b68`（origin/main），本报告对应的源码、SQL、脚本和 JAR 的 SHA-256 保存在原始结果中。

## 实际结果

| 验证 | 结果 | 原始依据 |
| --- | --- | --- |
| 后端测试与打包 | `mvn clean verify` 34 项通过，失败/错误/跳过均为 0；新增 `AuctionSessionTest` 6 项、`AuctionRepositoryTest` 5 项 | [JUnit 逐项结果](evidence/r5-auction-db/iteration2-regression/junit-results.json) |
| 拍卖数据库专项 | 43 项检查全部通过 | [拍卖 MySQL 结果](evidence/r5-auction-db/mysql-results.json) |
| 迭代 2 数据库回归 | 原 53 项检查全部通过（期望已按 V6 更新：五表库执行 V4→V5→V6，重复升级执行 V5→V6） | [迭代 2 回归结果](evidence/r5-auction-db/iteration2-regression/mysql-results.json) |
| 清理 | 两次运行均停止本次 Java 进程，删除本次容器及匿名卷 | 两份结果的 `cleanup` |

## 检查分组

| 证据 ID | 内容 | 任务 |
| --- | --- | --- |
| D01～D03、S01～S04 | 空库十二表、MySQL 版本、JPA 校验通过；金额列均为 DECIMAL(10,2)；扫描/出价/提醒索引与模式触发器存在 | P-A01、P-A02 |
| F01～F04 | 现有发布接口产生的商品为 `FIXED_PRICE` 且意向→交易→成功流程不变；触发器拒绝改模式；未知模式、拍卖库存大于 1 被拒绝 | P-A01 |
| B01～B08 | 新场次无价格/领先者；同商品第二场次、非正起拍价、截止早于开始、未知状态、无出价却有价格、有出价却无价格、成交却无中标意向均被拒绝 | P-A01 |
| G01～G04 | 有效出价按序号/顾客/金额/时间可追溯；重复序号、重复金额、无效顾客外键被拒绝 | P-A02 |
| N01～N03、W01～W02 | 同场次同类型提醒不可重复；卖家提醒不带顾客；成交提醒必须带价格；模拟结拍生成的中标意向经既有 `/success` 接口完成，库存 1→0、下架、写 SUCCESS 历史；提醒可按中标人/卖家查询 | P-A02、P-A01 |
| U01～U03 | 到期扫描只返回过期 LIVE 场次；条件结拍执行一次、重复扫描影响 0 行；流拍场次不能挂中标意向 | P-A01 |
| Q01～Q02 | 交付给 R1 的查询样例实际执行，快照中领先者脱敏；到期扫描执行计划使用 `idx_auction_status_ends` | P-A01、P-A02 |
| M01～M08 | 九表库先备份再执行 V5/V6；旧商品全部为 `FIXED_PRICE` 且原列数据不变；升级库与空库结构一致；重复升级不改数据；备份恢复与升级前一致；V6 中断后可续跑；未完成 V5 的库直接跑 V6 时在任何修改前停止；缺拍卖列的十二表结构被拒绝 | P-A01、P-A02 |
| R01～R02 | MySQL 重启后场次、出价、提醒与履约关联保留；V6 升级库上后端 JPA 校验启动成功 | P-A01、P-A02 |

## 验证中发现并修复

1. 首次运行 N03 失败：`final_price > 0` 在值为 NULL 时得到 UNKNOWN，MySQL 的 CHECK 视为通过，成交提醒可以缺价格。同类问题存在于 `chk_auction_leading`（有出价但当前价为 NULL）。两处均改为显式 `IS NOT NULL`，并新增 B07 覆盖；修复后全部通过。
2. 验证容器中 `NOW()` 为 UTC，而应用按 Asia/Shanghai 写入时间。已在契约与数据字典中规定截止判断必须由应用传入 `BusinessTime.now()`。

## 复验

```powershell
mvn -B -ntp -f backend/pom.xml clean verify
python -X utf8 scripts/verify_auction_database.py --java java
python -X utf8 scripts/verify_iteration2_database.py --java java --output docs/test/evidence/r5-auction-db/iteration2-regression/mysql-results.json
```

前置条件与迭代 2 报告相同：Docker 已运行且本机已有 `mysql:8.0.46` 镜像（脚本不拉取镜像）。复验留档时用 `--output` 指定新目录。

## 范围和剩余事项

- 结拍、出价在本报告中以 SQL 模拟服务事务，用于证明表结构、约束和既有交易接口能够承接；出价/结拍服务、SSE 和前端分别属于 P-A04、P-A06、P-A07 和 P-A08～P-A11，尚未实现，不在本报告覆盖范围内。
- H2 单元测试按实体建表，不包含 MySQL CHECK 与触发器；约束结论以本报告的真实 MySQL 结果为准。
- 未执行压力并发、大数据量性能或实际业务库升级；部署前须在目标数据副本上演练备份恢复。
- P-A12 数据库专项验证由 R2 负责复核，本报告可作为其输入。
