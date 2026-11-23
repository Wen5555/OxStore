-- B-004: close the legacy fixed-price purchase-intent flow (see docs/iterationB/B-000-公共开发约定.md §11).
-- Apply after V7 with application writes stopped and a verified backup. Safe to repeat: a second run
-- finds nothing left to change. This is NOT the V4 "intent -> FAILED" rule.
--   * FIXED_PRICE intents still QUEUING / IN_TRANSACTION get legacy_closed_at + legacy_close_reason;
--     their original status and snapshots are kept (never rewritten to CANCELLED/FAILED).
--   * Their unfinished trade attempts get legacy_closed_at; result/finished_at stay NULL.
--   * FIXED_PRICE products frozen by a trade return to ONLINE. Stock is not touched.
--   * FIXED_PRICE products frozen by the seller (MANUAL) have no frozen state any more: they become
--     OFFLINE / MANUAL so a deliberately paused item does not silently go on sale. (Review decision.)
--   * Auction products, sessions, bids, notifications and old SUCCESS/FAILED history are not touched.
-- The checks run before any change and stop the script with a message instead of skipping the
-- inventory invariant. DML runs in one transaction; the earlier DDL of V7 is not transactional.
DELIMITER //
DROP PROCEDURE IF EXISTS upgrade_oxstore_v8//
CREATE PROCEDURE upgrade_oxstore_v8()
BEGIN
  DECLARE closed_at DATETIME(6) DEFAULT CONVERT_TZ(UTC_TIMESTAMP(6), '+00:00', '+08:00');
  DECLARE closed_intents INT DEFAULT 0;
  DECLARE closed_attempts INT DEFAULT 0;
  DECLARE unfrozen_products INT DEFAULT 0;
  DECLARE paused_products INT DEFAULT 0;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'purchase_intent' AND column_name = 'legacy_closed_at')
     OR NOT EXISTS (SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'trade_attempt' AND column_name = 'legacy_closed_at')
     OR NOT EXISTS (SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'product' AND column_name = 'offline_reason') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'V8 requires the complete V7 schema; run V7 first';
  END IF;
  IF EXISTS (SELECT 1 FROM product WHERE selling_mode = 'FIXED_PRICE' AND status = 'FROZEN' AND stock = '0') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT =
      'A frozen fixed-price product has stock 0; reconcile product/stock with the backup before V8';
  END IF;
  IF EXISTS (SELECT 1 FROM product WHERE selling_mode = 'FIXED_PRICE' AND status = 'FROZEN'
             AND (freeze_source IS NULL OR freeze_source NOT IN ('TRADE', 'MANUAL'))) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT =
      'A frozen fixed-price product has an unknown freeze_source; inspect it before V8';
  END IF;
  IF EXISTS (SELECT 1 FROM purchase_intent i JOIN product p ON p.id = i.product_id
             WHERE p.selling_mode = 'FIXED_PRICE' AND i.status IN ('QUEUING', 'IN_TRANSACTION')
               AND i.legacy_closed_at IS NOT NULL AND i.legacy_close_reason <> 'FIXED_PRICE_CHALLENGE_B') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT =
      'A live fixed-price intent carries a foreign legacy_close_reason; inspect it before V8';
  END IF;

  START TRANSACTION;

  UPDATE purchase_intent i JOIN product p ON p.id = i.product_id
     SET i.legacy_closed_at = closed_at, i.legacy_close_reason = 'FIXED_PRICE_CHALLENGE_B'
   WHERE p.selling_mode = 'FIXED_PRICE' AND i.status IN ('QUEUING', 'IN_TRANSACTION')
     AND i.legacy_closed_at IS NULL;
  SET closed_intents = ROW_COUNT();

  UPDATE trade_attempt t JOIN purchase_intent i ON i.id = t.intent_id
     SET t.legacy_closed_at = closed_at
   WHERE i.legacy_close_reason = 'FIXED_PRICE_CHALLENGE_B' AND t.finished_at IS NULL
     AND t.legacy_closed_at IS NULL;
  SET closed_attempts = ROW_COUNT();

  UPDATE product SET status = 'ONLINE', freeze_source = NULL, offline_reason = NULL, status_updated_at = closed_at
   WHERE selling_mode = 'FIXED_PRICE' AND status = 'FROZEN' AND freeze_source = 'TRADE';
  SET unfrozen_products = ROW_COUNT();

  UPDATE product SET status = 'OFFLINE', freeze_source = NULL, offline_reason = 'MANUAL', status_updated_at = closed_at
   WHERE selling_mode = 'FIXED_PRICE' AND status = 'FROZEN' AND freeze_source = 'MANUAL';
  SET paused_products = ROW_COUNT();

  COMMIT;
  SELECT closed_intents AS closed_intents, closed_attempts AS closed_attempts,
         unfrozen_products AS unfrozen_products, paused_products AS paused_products;
END//
DELIMITER ;
CALL upgrade_oxstore_v8();
DROP PROCEDURE upgrade_oxstore_v8;
