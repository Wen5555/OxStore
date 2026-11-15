-- Challenge B model and numeric contract (B-001～B-003; see docs/iterationB/B-000-公共开发约定.md §5).
-- Apply after V6; safe to repeat. DDL commits implicitly: stop writes and back up first, and on failure
-- restore the backup instead of expecting an automatic rollback.
-- Quantities, stock and order amounts are unbounded canonical decimal strings (LONGTEXT) so that no
-- int/long, JS-safe-integer or column-width limit becomes a business cap. Shapes are enforced with
-- CHECKs that use NOT REGEXP '[^0-9]' instead of '$' anchors (ICU '$' also matches before a trailing newline).
DELIMITER //
DROP PROCEDURE IF EXISTS upgrade_oxstore_v7//
CREATE PROCEDURE upgrade_oxstore_v7()
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'product' AND column_name = 'selling_mode') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'V7 requires the complete V6 schema';
  END IF;

  -- product.offline_reason: why an OFFLINE product is offline (AUTO_ZERO from stock 0, MANUAL by the seller).
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'product' AND column_name = 'offline_reason') THEN
    ALTER TABLE product ADD COLUMN offline_reason VARCHAR(20) NULL AFTER freeze_source;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
      WHERE constraint_schema = DATABASE() AND table_name = 'product' AND constraint_name = 'chk_product_offline_reason') THEN
    ALTER TABLE product ADD CONSTRAINT chk_product_offline_reason CHECK (
      offline_reason IS NULL OR offline_reason IN ('AUTO_ZERO', 'MANUAL'));
  END IF;

  -- product.stock: INT -> canonical non-negative decimal string. The numeric CHECKs are dropped first
  -- and re-created below, so an interrupted run resumes from whichever step is missing.
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'product' AND column_name = 'stock') <> 'longtext' THEN
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_schema = DATABASE() AND table_name = 'product' AND constraint_name = 'chk_product_stock') THEN
      ALTER TABLE product DROP CHECK chk_product_stock;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_schema = DATABASE() AND table_name = 'product' AND constraint_name = 'chk_product_auction_stock') THEN
      ALTER TABLE product DROP CHECK chk_product_auction_stock;
    END IF;
    ALTER TABLE product MODIFY COLUMN stock LONGTEXT NOT NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
      WHERE constraint_schema = DATABASE() AND table_name = 'product' AND constraint_name = 'chk_product_stock') THEN
    ALTER TABLE product ADD CONSTRAINT chk_product_stock CHECK (
      stock <> '' AND stock NOT REGEXP '[^0-9]' AND (stock = '0' OR stock NOT LIKE '0%'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
      WHERE constraint_schema = DATABASE() AND table_name = 'product' AND constraint_name = 'chk_product_auction_stock') THEN
    ALTER TABLE product ADD CONSTRAINT chk_product_auction_stock CHECK (
      selling_mode <> 'AUCTION' OR stock IN ('0', '1'));
  END IF;

  -- Initialise the reason for existing fixed-price OFFLINE products only (never for auctions).
  UPDATE product SET offline_reason = IF(stock = '0', 'AUTO_ZERO', 'MANUAL')
   WHERE selling_mode = 'FIXED_PRICE' AND status = 'OFFLINE' AND offline_reason IS NULL;

  -- Legacy fixed-price archive markers (set by V8; original status/snapshots stay untouched).
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'purchase_intent' AND column_name = 'legacy_closed_at') THEN
    ALTER TABLE purchase_intent
      ADD COLUMN legacy_closed_at DATETIME(6) NULL,
      ADD COLUMN legacy_close_reason VARCHAR(40) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
      WHERE constraint_schema = DATABASE() AND table_name = 'purchase_intent' AND constraint_name = 'chk_intent_legacy_close') THEN
    ALTER TABLE purchase_intent ADD CONSTRAINT chk_intent_legacy_close CHECK (
      (legacy_closed_at IS NULL AND legacy_close_reason IS NULL) OR
      (legacy_closed_at IS NOT NULL AND legacy_close_reason IS NOT NULL));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.statistics
      WHERE table_schema = DATABASE() AND table_name = 'purchase_intent' AND index_name = 'idx_intent_legacy_customer') THEN
    ALTER TABLE purchase_intent
      ADD KEY idx_intent_legacy_customer (customer_id, legacy_closed_at, submitted_at),
      ADD KEY idx_intent_legacy_product (product_id, legacy_closed_at, submitted_at);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'trade_attempt' AND column_name = 'legacy_closed_at') THEN
    ALTER TABLE trade_attempt ADD COLUMN legacy_closed_at DATETIME(6) NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
      WHERE constraint_schema = DATABASE() AND table_name = 'trade_attempt' AND constraint_name = 'chk_attempt_legacy_close') THEN
    ALTER TABLE trade_attempt ADD CONSTRAINT chk_attempt_legacy_close CHECK (
      legacy_closed_at IS NULL OR (finished_at IS NULL AND result IS NULL AND fail_action IS NULL));
  END IF;
END//
DELIMITER ;
CALL upgrade_oxstore_v7();
DROP PROCEDURE upgrade_oxstore_v7;

-- B-001: order header and immutable item snapshots. Fixed-price orders never use purchase_intent.
CREATE TABLE IF NOT EXISTS shop_order (
    id BIGINT NOT NULL AUTO_INCREMENT,
    order_no CHAR(36) NOT NULL,
    customer_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL,
    total_amount LONGTEXT NOT NULL,
    created_at DATETIME(6) NOT NULL,
    cancelled_by VARCHAR(20) NULL,
    cancelled_at DATETIME(6) NULL,
    cancel_reason VARCHAR(500) NULL,
    version BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uk_shop_order_no (order_no),
    KEY idx_shop_order_customer_time (customer_id, created_at, id),
    KEY idx_shop_order_time (created_at, id),
    CONSTRAINT fk_shop_order_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT chk_shop_order_no CHECK (order_no REGEXP
        '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'),
    CONSTRAINT chk_shop_order_status CHECK (status IN
        ('PLACED', 'CONFIRMED', 'PREPARED', 'SHIPPED', 'COMPLETED', 'CANCELLED')),
    CONSTRAINT chk_shop_order_total CHECK (
        total_amount NOT REGEXP '[^0-9.]' AND total_amount REGEXP '^[0-9]+[.][0-9]{2}$' AND
        (total_amount NOT LIKE '0%' OR total_amount LIKE '0.%')),
    CONSTRAINT chk_shop_order_cancel CHECK (
        (status = 'CANCELLED' AND cancelled_by IN ('CUSTOMER', 'SELLER') AND
         cancelled_at IS NOT NULL AND cancelled_at >= created_at) OR
        (status <> 'CANCELLED' AND cancelled_by IS NULL AND cancelled_at IS NULL AND cancel_reason IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS order_item (
    id BIGINT NOT NULL AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    product_name_snapshot VARCHAR(200) NOT NULL,
    unit_price_snapshot DECIMAL(10,2) NOT NULL,
    quantity_snapshot LONGTEXT NOT NULL,
    line_amount_snapshot LONGTEXT NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_order_item_product (order_id, product_id),
    KEY idx_order_item_product (product_id),
    CONSTRAINT fk_order_item_order FOREIGN KEY (order_id) REFERENCES shop_order (id),
    CONSTRAINT fk_order_item_product FOREIGN KEY (product_id) REFERENCES product (id),
    CONSTRAINT chk_order_item_price CHECK (unit_price_snapshot > 0),
    CONSTRAINT chk_order_item_quantity CHECK (
        quantity_snapshot <> '' AND quantity_snapshot NOT REGEXP '[^0-9]' AND quantity_snapshot NOT LIKE '0%'),
    CONSTRAINT chk_order_item_amount CHECK (
        line_amount_snapshot NOT REGEXP '[^0-9.]' AND line_amount_snapshot REGEXP '^[0-9]+[.][0-9]{2}$' AND
        (line_amount_snapshot NOT LIKE '0%' OR line_amount_snapshot LIKE '0.%'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Identity and money never change after creation; a terminal order never leaves its state.
DROP TRIGGER IF EXISTS trg_shop_order_guard;
DROP TRIGGER IF EXISTS trg_order_item_immutable;
DELIMITER //
CREATE TRIGGER trg_shop_order_guard BEFORE UPDATE ON shop_order
FOR EACH ROW
BEGIN
  IF NEW.order_no <> OLD.order_no OR NEW.customer_id <> OLD.customer_id
     OR NEW.total_amount <> OLD.total_amount OR NEW.created_at <> OLD.created_at THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'order identity, owner, total and creation time are immutable';
  END IF;
  IF OLD.status IN ('COMPLETED', 'CANCELLED') AND
     (NEW.status <> OLD.status OR NOT (NEW.cancelled_by <=> OLD.cancelled_by)
      OR NOT (NEW.cancelled_at <=> OLD.cancelled_at) OR NOT (NEW.cancel_reason <=> OLD.cancel_reason)) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'terminal orders cannot change';
  END IF;
END//
CREATE TRIGGER trg_order_item_immutable BEFORE UPDATE ON order_item
FOR EACH ROW
BEGIN
  IF NEW.order_id <> OLD.order_id OR NEW.product_id <> OLD.product_id
     OR NEW.product_name_snapshot <> OLD.product_name_snapshot
     OR NEW.unit_price_snapshot <> OLD.unit_price_snapshot
     OR NEW.quantity_snapshot <> OLD.quantity_snapshot
     OR NEW.line_amount_snapshot <> OLD.line_amount_snapshot THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'order item snapshots are immutable';
  END IF;
END//
DELIMITER ;

-- B-002: server-side favorites and cart. One row per (customer, product); cart rows are removed by
-- DELETE (never by quantity 0) and a removed row id is remembered in cart_item_tombstone.
CREATE TABLE IF NOT EXISTS favorite (
    id BIGINT NOT NULL AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_favorite_customer_product (customer_id, product_id),
    KEY idx_favorite_customer_time (customer_id, created_at, id),
    KEY idx_favorite_product (product_id),
    CONSTRAINT fk_favorite_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT fk_favorite_product FOREIGN KEY (product_id) REFERENCES product (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Per-customer/product operation counters, maintained under the customer lock. A move-to-favorites
-- receipt stores the sequence it produced, so a later independent cancel is detected by
-- last_cancel_seq > stored sequence rather than by guessing from whether the favorite exists.
CREATE TABLE IF NOT EXISTS favorite_mutation (
    customer_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    operation_seq BIGINT NOT NULL DEFAULT 0,
    last_cancel_seq BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (customer_id, product_id),
    KEY idx_favorite_mutation_product (product_id),
    CONSTRAINT fk_favorite_mutation_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT fk_favorite_mutation_product FOREIGN KEY (product_id) REFERENCES product (id),
    CONSTRAINT chk_favorite_mutation_seq CHECK (last_cancel_seq >= 0 AND operation_seq >= last_cancel_seq)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cart_item (
    id BIGINT NOT NULL AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    quantity LONGTEXT NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_cart_customer_product (customer_id, product_id),
    KEY idx_cart_customer (customer_id, id),
    KEY idx_cart_product (product_id),
    CONSTRAINT fk_cart_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT fk_cart_product FOREIGN KEY (product_id) REFERENCES product (id),
    CONSTRAINT chk_cart_quantity CHECK (
        quantity <> '' AND quantity NOT REGEXP '[^0-9]' AND quantity NOT LIKE '0%')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Written in the same transaction as every cart row removal (delete, clear, move, checkout remainder 0).
-- No foreign key on cart_item_id: the row is gone. AUTO_INCREMENT is persistent in MySQL 8, so ids are
-- never reused and a stale cartItemId can be told apart from an unknown one.
CREATE TABLE IF NOT EXISTS cart_item_tombstone (
    id BIGINT NOT NULL AUTO_INCREMENT,
    cart_item_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    removed_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_cart_tombstone_item (cart_item_id),
    KEY idx_cart_tombstone_customer (customer_id, cart_item_id),
    CONSTRAINT fk_cart_tombstone_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT fk_cart_tombstone_product FOREIGN KEY (product_id) REFERENCES product (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- B-003: checkout confirmation snapshot (no order, no stock change) and idempotency receipts.
CREATE TABLE IF NOT EXISTS checkout_confirmation (
    id BIGINT NOT NULL AUTO_INCREMENT,
    token CHAR(36) NOT NULL,
    customer_id BIGINT NOT NULL,
    total_amount LONGTEXT NOT NULL,
    digest CHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_confirmation_token (token),
    KEY idx_confirmation_customer_time (customer_id, created_at, id),
    CONSTRAINT fk_confirmation_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT chk_confirmation_total CHECK (
        total_amount NOT REGEXP '[^0-9.]' AND total_amount REGEXP '^[0-9]+[.][0-9]{2}$' AND
        (total_amount NOT LIKE '0%' OR total_amount LIKE '0.%'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS checkout_confirmation_item (
    id BIGINT NOT NULL AUTO_INCREMENT,
    confirmation_id BIGINT NOT NULL,
    cart_item_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    quantity LONGTEXT NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_confirmation_item_cart (confirmation_id, cart_item_id),
    KEY idx_confirmation_item_product (product_id),
    CONSTRAINT fk_confirmation_item_confirmation FOREIGN KEY (confirmation_id) REFERENCES checkout_confirmation (id),
    CONSTRAINT fk_confirmation_item_product FOREIGN KEY (product_id) REFERENCES product (id),
    CONSTRAINT chk_confirmation_item_price CHECK (unit_price > 0),
    CONSTRAINT chk_confirmation_item_quantity CHECK (
        quantity <> '' AND quantity NOT REGEXP '[^0-9]' AND quantity NOT LIKE '0%')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Only successful results are stored, in the same transaction as the business change; no JWT or password.
CREATE TABLE IF NOT EXISTS operation_receipt (
    id BIGINT NOT NULL AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    operation_type VARCHAR(30) NOT NULL,
    request_key CHAR(36) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    result_payload LONGTEXT NOT NULL,
    completed_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_receipt_request (customer_id, operation_type, request_key),
    CONSTRAINT fk_receipt_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT chk_receipt_type CHECK (operation_type IN ('CART_ADD', 'CHECKOUT', 'MOVE_TO_FAVORITES')),
    CONSTRAINT chk_receipt_payload CHECK (JSON_VALID(result_payload))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
