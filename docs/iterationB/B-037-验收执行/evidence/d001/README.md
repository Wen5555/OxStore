# D-001 受控复验记录（R2）

- 日期：2026-11-23；SUT `develop@ebe3f32`；测试类 `ChallengeBCheckoutPublicApiConcurrencyTest`（PR #36）。
- 数据库：MySQL 8.0 `oxstore_test_d001`，`schema.sql` 空库导入，`ddl-auto=none`。
- 命令：`mvn -B -Dtest=ChallengeBCheckoutPublicApiConcurrencyTest test`（root/密码、allowPublicKeyRetrieval 由 JAVA_TOOL_OPTIONS 传入）。
- 结果：`Tests run: 2, Failures: 0, Errors: 0, Skipped: 0`，BUILD SUCCESS。
- 产物：`d001-locked-add.json`、`d001-before-lock-change.json`、surefire XML/TXT。
- 判定：按 B-000 §8，锁后加购保留为新行（同商品最终 1 件），D-001 关闭。
