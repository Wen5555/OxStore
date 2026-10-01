-- 一次性升级旧库；先备份、在副本演练，停写后由 mysql 命令行执行（需支持 DELIMITER）。
-- 禁止带 IN_TRANSACTION 意向升级：旧数据不能凭 processed_at 推测交易开始时间。
-- MySQL DDL 隐式提交；失败时勿直接重复执行，先核对备份和当前表结构。
-- 执行前保存：SELECT COUNT(*), status FROM purchase_intent GROUP BY status;
--            SELECT COUNT(*) FROM product; SELECT NOW(6) AS history_complete_since;
DELIMITER //
-- 前一次仅被 guard 拦截时可能留下此过程；清理辅助过程后重新检查业务前置条件。
DROP PROCEDURE IF EXISTS guard_oxstore_v2//
CREATE PROCEDURE guard_oxstore_v2()
BEGIN
  IF EXISTS (SELECT 1 FROM purchase_intent WHERE status = 'IN_TRANSACTION') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '先结束交易中意向，再执行迁移';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = DATABASE()
             AND table_name = 'purchase_intent' AND column_name = 'queue_seq') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'queue_seq 已存在：勿重复执行升级';
  END IF;
END//
DELIMITER ;
CALL guard_oxstore_v2();
DROP PROCEDURE guard_oxstore_v2;

ALTER TABLE purchase_intent ADD COLUMN queue_seq BIGINT NULL AFTER submitted_at,
    ADD COLUMN token_lookup VARCHAR(64) NULL AFTER token_hash;
UPDATE purchase_intent AS i
JOIN (SELECT id, ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY submitted_at, id) AS seq
      FROM purchase_intent) AS numbered ON numbered.id = i.id
SET i.queue_seq = numbered.seq;
-- 此处 NULL/重复均必须为 0；如非 0，停止执行并排查，不得忽略。
SELECT COUNT(*) AS null_queue_seq FROM purchase_intent WHERE queue_seq IS NULL;
SELECT COUNT(*) AS duplicated_pairs FROM (
  SELECT product_id, queue_seq FROM purchase_intent GROUP BY product_id, queue_seq HAVING COUNT(*) > 1
) AS duplicates;
ALTER TABLE purchase_intent MODIFY queue_seq BIGINT NOT NULL,
    ADD UNIQUE KEY uk_intent_product_seq (product_id, queue_seq),
    ADD UNIQUE KEY uk_intent_token_lookup (token_lookup),
    ADD KEY idx_intent_product_status_seq (product_id, status, queue_seq);
-- 旧 DATETIME(0) 历史不会凭升级补造微秒；以后写入采用 DATETIME(6)。
ALTER TABLE product MODIFY published_at DATETIME(6) NOT NULL,
    MODIFY status_updated_at DATETIME(6) NULL, MODIFY sold_at DATETIME(6) NULL;
ALTER TABLE purchase_intent MODIFY submitted_at DATETIME(6) NOT NULL,
    MODIFY updated_at DATETIME(6) NULL, MODIFY processed_at DATETIME(6) NULL;
ALTER TABLE seller MODIFY password_updated_at DATETIME(6) NULL;

CREATE TABLE IF NOT EXISTS trade_attempt (
    id BIGINT NOT NULL AUTO_INCREMENT,
    intent_id BIGINT NOT NULL,
    started_at DATETIME(6) NOT NULL,
    finished_at DATETIME(6) NULL,
    result VARCHAR(10) NULL,
    fail_action VARCHAR(10) NULL,
    open_intent_id BIGINT GENERATED ALWAYS AS (
        CASE WHEN finished_at IS NULL THEN intent_id ELSE NULL END
    ) STORED,
    PRIMARY KEY (id),
    UNIQUE KEY uk_attempt_open_intent (open_intent_id),
    KEY idx_attempt_intent_time (intent_id, started_at, id),
    CONSTRAINT fk_attempt_intent FOREIGN KEY (intent_id) REFERENCES purchase_intent (id),
    CONSTRAINT chk_attempt_completion CHECK (
        (finished_at IS NULL AND result IS NULL AND fail_action IS NULL)
        OR (finished_at IS NOT NULL AND result IS NOT NULL AND finished_at >= started_at AND
            ((result = 'SUCCESS' AND fail_action IS NULL) OR
             (result = 'FAILED' AND fail_action IS NOT NULL AND fail_action IN ('REQUEUE','DISCARD'))))
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS product_status_event (
    id BIGINT NOT NULL AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    trade_attempt_id BIGINT NULL,
    event_type VARCHAR(30) NOT NULL,
    from_status VARCHAR(20) NULL,
    to_status VARCHAR(20) NOT NULL,
    freeze_source VARCHAR(20) NULL,
    occurred_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    KEY idx_event_product_time (product_id, occurred_at, id),
    KEY idx_event_attempt (trade_attempt_id),
    CONSTRAINT fk_event_product FOREIGN KEY (product_id) REFERENCES product (id),
    CONSTRAINT fk_event_attempt FOREIGN KEY (trade_attempt_id) REFERENCES trade_attempt (id),
    CONSTRAINT chk_event_type CHECK (event_type IN
        ('PUBLISHED','MANUAL_FREEZE','MANUAL_UNFREEZE','TRADE_STARTED','TRADE_FAILED','TRADE_SUCCEEDED')),
    CONSTRAINT chk_event_publish CHECK (event_type <> 'PUBLISHED' OR from_status IS NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 执行后保存本次校验结果、行数与状态分布；与执行前快照逐项核对。
SELECT COUNT(*) AS intent_count FROM purchase_intent;
SELECT status, COUNT(*) AS count_by_status FROM purchase_intent GROUP BY status;
SELECT COUNT(*) AS null_queue_seq FROM purchase_intent WHERE queue_seq IS NULL;
SELECT COUNT(*) AS duplicated_pairs FROM (
  SELECT product_id, queue_seq FROM purchase_intent GROUP BY product_id, queue_seq HAVING COUNT(*) > 1
) AS duplicates;
SELECT COUNT(*) AS attempt_count FROM trade_attempt;
SELECT COUNT(*) AS event_count FROM product_status_event;
-- 将升级截止时间设入 HISTORY_COMPLETE_SINCE，旧记录的逐次尝试/事件可能不完整。
