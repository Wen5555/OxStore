-- 仅用于已经执行旧版 V2 的库；新建库和修订后的 V2 已包含严格约束。
-- 先备份并停写，在副本演练；发现不完整交易结果时拒绝执行，不伪造结果。
-- 使用 mysql 命令行执行，不启用 --force。DDL 隐式提交。
DELIMITER //
DROP PROCEDURE IF EXISTS guard_oxstore_v3//
CREATE PROCEDURE guard_oxstore_v3()
BEGIN
  IF EXISTS (
    SELECT 1 FROM trade_attempt WHERE NOT (
      (finished_at IS NULL AND result IS NULL AND fail_action IS NULL)
      OR (finished_at IS NOT NULL AND result IS NOT NULL AND finished_at >= started_at
          AND ((result = 'SUCCESS' AND fail_action IS NULL)
               OR (result = 'FAILED' AND fail_action IS NOT NULL
                   AND fail_action IN ('REQUEUE', 'DISCARD'))))
    )
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '存在不完整交易结果，先核实修复数据再升级约束';
  END IF;
END//
DELIMITER ;
CALL guard_oxstore_v3();
DROP PROCEDURE guard_oxstore_v3;
ALTER TABLE trade_attempt DROP CHECK chk_attempt_completion,
    ADD CONSTRAINT chk_attempt_completion CHECK (
      (finished_at IS NULL AND result IS NULL AND fail_action IS NULL)
      OR (finished_at IS NOT NULL AND result IS NOT NULL AND finished_at >= started_at
          AND ((result = 'SUCCESS' AND fail_action IS NULL)
               OR (result = 'FAILED' AND fail_action IS NOT NULL
                   AND fail_action IN ('REQUEUE', 'DISCARD'))))
    );
