-- B-032 test-only TX fault probes for isolated DB oxstore_b032_*.
-- Installed by scripts/install_tx_probes.py. Does NOT modify application code.
-- Mechanism: InnoDB control row read by triggers on real app tables; MyISAM probe
-- log survives rollback so mid-TX writes can be proven then shown fully rolled back.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS b032_tx_probe (
  id BIGINT NOT NULL AUTO_INCREMENT,
  phase VARCHAR(64) NOT NULL,
  note VARCHAR(255) NULL,
  at_ts TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS b032_tx_control (
  id INT PRIMARY KEY,
  fail_phase VARCHAR(64) NULL,
  probe_enabled TINYINT NOT NULL DEFAULT 0,
  hold_seconds INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Upgrade path when table already existed without hold_seconds
SET @b032_hold_col := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'b032_tx_control' AND COLUMN_NAME = 'hold_seconds'
);
SET @b032_hold_sql := IF(@b032_hold_col = 0,
  'ALTER TABLE b032_tx_control ADD COLUMN hold_seconds INT NOT NULL DEFAULT 0',
  'SELECT 1');
PREPARE b032_hold_stmt FROM @b032_hold_sql;
EXECUTE b032_hold_stmt;
DEALLOCATE PREPARE b032_hold_stmt;

INSERT INTO b032_tx_control(id, fail_phase, probe_enabled, hold_seconds)
VALUES (1, NULL, 0, 0)
ON DUPLICATE KEY UPDATE id=id;

DROP TRIGGER IF EXISTS b032_trg_after_order;
DROP TRIGGER IF EXISTS b032_trg_after_product;
DROP TRIGGER IF EXISTS b032_trg_after_cart_del;
DROP TRIGGER IF EXISTS b032_trg_after_cart_upd;
DROP TRIGGER IF EXISTS b032_trg_before_receipt;

DELIMITER $$

-- Hold observability: MyISAM probe rows written inside an open InnoDB TX are NOT
-- reliably readable by other connections until that TX ends (mixed-engine lock
-- coupling). Therefore "during hold" is signaled with a MySQL named lock
-- (IS_USED_LOCK), not with SELECT on b032_tx_probe.
-- Probe INSERT still records post-facto phases; hold SLEEP runs on after_stock
-- with GET_LOCK/RELEASE_LOCK bracketing the sleep (no MyISAM write during hold).
CREATE TRIGGER b032_trg_after_order
AFTER INSERT ON shop_order FOR EACH ROW
BEGIN
  DECLARE v_fail VARCHAR(64);
  DECLARE v_probe TINYINT;
  SELECT fail_phase, probe_enabled INTO v_fail, v_probe
    FROM b032_tx_control WHERE id=1;
  IF v_probe = 1 THEN
    INSERT INTO b032_tx_probe(phase, note) VALUES ('order_created', CONCAT('order_id=', NEW.id));
  END IF;
  IF v_fail = 'after_order' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'B032 induced fail after_order';
  END IF;
END$$

CREATE TRIGGER b032_trg_after_product
AFTER UPDATE ON product FOR EACH ROW
BEGIN
  DECLARE v_fail VARCHAR(64);
  DECLARE v_probe TINYINT;
  DECLARE v_hold INT;
  IF OLD.stock <> NEW.stock THEN
    SELECT fail_phase, probe_enabled, hold_seconds INTO v_fail, v_probe, v_hold
      FROM b032_tx_control WHERE id=1;
    IF v_hold > 0 THEN
      -- Named lock is visible to other sessions via IS_USED_LOCK during SLEEP.
      DO GET_LOCK('b032_tx_hold', 0);
      DO SLEEP(v_hold);
      DO RELEASE_LOCK('b032_tx_hold');
    ELSEIF v_probe = 1 THEN
      INSERT INTO b032_tx_probe(phase, note) VALUES (
        'stock_updated',
        CONCAT('product_id=', NEW.id, ' stock=', OLD.stock, '->', NEW.stock)
      );
    END IF;
    IF v_fail = 'after_stock' THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'B032 induced fail after_stock';
    END IF;
  END IF;
END$$

CREATE TRIGGER b032_trg_after_cart_del
AFTER DELETE ON cart_item FOR EACH ROW
BEGIN
  DECLARE v_fail VARCHAR(64);
  DECLARE v_probe TINYINT;
  SELECT fail_phase, probe_enabled INTO v_fail, v_probe FROM b032_tx_control WHERE id=1;
  IF v_probe = 1 THEN
    INSERT INTO b032_tx_probe(phase, note) VALUES ('cart_deleted', CONCAT('cart_item_id=', OLD.id));
  END IF;
  IF v_fail = 'after_cart' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'B032 induced fail after_cart';
  END IF;
END$$

CREATE TRIGGER b032_trg_after_cart_upd
AFTER UPDATE ON cart_item FOR EACH ROW
BEGIN
  DECLARE v_probe TINYINT;
  SELECT probe_enabled INTO v_probe FROM b032_tx_control WHERE id=1;
  IF v_probe = 1 AND OLD.quantity <> NEW.quantity THEN
    INSERT INTO b032_tx_probe(phase, note) VALUES (
      'cart_updated',
      CONCAT('cart_item_id=', NEW.id, ' qty=', OLD.quantity, '->', NEW.quantity)
    );
  END IF;
END$$

CREATE TRIGGER b032_trg_before_receipt
BEFORE INSERT ON operation_receipt FOR EACH ROW
BEGIN
  DECLARE v_fail VARCHAR(64);
  DECLARE v_probe TINYINT;
  SELECT fail_phase, probe_enabled INTO v_fail, v_probe FROM b032_tx_control WHERE id=1;
  IF v_probe = 1 THEN
    INSERT INTO b032_tx_probe(phase, note) VALUES ('before_receipt', CONCAT('op=', NEW.operation_type));
  END IF;
  IF v_fail = 'before_receipt' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'B032 induced fail before_receipt';
  END IF;
END$$

DELIMITER ;
