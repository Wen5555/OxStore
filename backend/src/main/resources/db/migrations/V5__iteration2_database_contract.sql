-- Apply after V4. Safe to repeat; legacy image metadata remains unknown (NULL), never invented.
DELIMITER //
DROP PROCEDURE IF EXISTS upgrade_oxstore_v5//
CREATE PROCEDURE upgrade_oxstore_v5()
BEGIN
  IF (SELECT COUNT(*) FROM information_schema.tables
      WHERE table_schema = DATABASE() AND table_name IN
      ('customer', 'category', 'product_image', 'order_history')) <> 4 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'V5 requires the complete V4 schema';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'product_image' AND column_name = 'content_type') THEN
    ALTER TABLE product_image ADD COLUMN content_type VARCHAR(20) NULL AFTER sort_order;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'product_image' AND column_name = 'size_bytes') THEN
    ALTER TABLE product_image ADD COLUMN size_bytes BIGINT NULL AFTER content_type;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
      WHERE constraint_schema = DATABASE() AND table_name = 'product_image' AND constraint_name = 'chk_product_image_order') THEN
    ALTER TABLE product_image ADD CONSTRAINT chk_product_image_order CHECK (sort_order BETWEEN 0 AND 8);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
      WHERE constraint_schema = DATABASE() AND table_name = 'product_image' AND constraint_name = 'chk_product_image_metadata') THEN
    ALTER TABLE product_image ADD CONSTRAINT chk_product_image_metadata CHECK (
      (content_type IS NULL AND size_bytes IS NULL) OR
      (content_type IS NOT NULL AND size_bytes IS NOT NULL AND
       content_type IN ('image/jpeg', 'image/png') AND size_bytes BETWEEN 1 AND 5242880));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
      WHERE constraint_schema = DATABASE() AND table_name = 'purchase_intent' AND constraint_name = 'chk_intent_status') THEN
    ALTER TABLE purchase_intent ADD CONSTRAINT chk_intent_status CHECK (
      status IN ('QUEUING', 'IN_TRANSACTION', 'SUCCESS', 'FAILED', 'CANCELLED'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.statistics
      WHERE table_schema = DATABASE() AND table_name = 'product' AND index_name = 'idx_product_status_time') THEN
    ALTER TABLE product ADD KEY idx_product_status_time (status, published_at, id);
  END IF;
END//
DELIMITER ;
CALL upgrade_oxstore_v5();
DROP PROCEDURE upgrade_oxstore_v5;
