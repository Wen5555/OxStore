-- Upgrade the V1/V2 catalog to the iteration 2 contract. Back up and verify a copy first.
DELIMITER //
DROP PROCEDURE IF EXISTS guard_oxstore_v4//
CREATE PROCEDURE guard_oxstore_v4()
BEGIN
  IF EXISTS (SELECT 1 FROM purchase_intent WHERE status = 'IN_TRANSACTION') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '先结束所有交易中意向，再执行迭代2迁移';
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_schema = DATABASE() AND table_name = 'product' AND column_name = 'category2_id') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'category2_id 已存在：勿重复执行迭代2迁移';
  END IF;
END//
DELIMITER ;
CALL guard_oxstore_v4();
DROP PROCEDURE guard_oxstore_v4;

CREATE TABLE category (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(80) NOT NULL,
    parent_id BIGINT NULL,
    PRIMARY KEY (id),
    KEY idx_category_parent (parent_id),
    CONSTRAINT fk_category_parent FOREIGN KEY (parent_id) REFERENCES category (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO category (name, parent_id) VALUES ('其他', NULL);
SET @other_root = LAST_INSERT_ID();
INSERT INTO category (name, parent_id) VALUES ('其他', @other_root);
SET @other_category = LAST_INSERT_ID();

CREATE TABLE customer (
    id BIGINT NOT NULL AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    location VARCHAR(200) NULL,
    registered_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_customer_username (username),
    KEY idx_customer_registered (registered_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

ALTER TABLE product
    DROP INDEX uk_product_active,
    DROP COLUMN active_flag,
    ADD COLUMN stock INT NOT NULL DEFAULT 0 AFTER price,
    ADD COLUMN category2_id BIGINT NULL AFTER stock;

-- Legacy inventory was never persisted; do not invent stock. Existing items require seller review.
UPDATE product SET stock = 0, status = 'OFFLINE', freeze_source = NULL;
UPDATE product SET category2_id = @other_category;
ALTER TABLE product
    MODIFY category2_id BIGINT NOT NULL,
    ADD KEY idx_product_category_status (category2_id, status, published_at, id),
    ADD CONSTRAINT fk_product_category2 FOREIGN KEY (category2_id) REFERENCES category (id),
    ADD CONSTRAINT chk_product_stock CHECK (stock >= 0);

CREATE TABLE product_image (
    id BIGINT NOT NULL AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    sort_order INT NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_product_image_order (product_id, sort_order),
    CONSTRAINT fk_product_image_product FOREIGN KEY (product_id) REFERENCES product (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO product_image (product_id, image_path, sort_order)
SELECT id, image_path, 0 FROM product WHERE image_path IS NOT NULL AND image_path <> '';

ALTER TABLE product
    DROP COLUMN image_path,
    ADD CONSTRAINT chk_product_status CHECK (status IN ('ONLINE', 'FROZEN', 'OFFLINE'));

ALTER TABLE purchase_intent
    DROP INDEX uk_intent_trading,
    DROP COLUMN trading_flag,
    DROP COLUMN token_hash,
    DROP COLUMN token_lookup,
    ADD COLUMN customer_id BIGINT NULL AFTER product_id,
    ADD COLUMN product_name_snapshot VARCHAR(200) NULL AFTER customer_id,
    ADD COLUMN trading_product_id BIGINT GENERATED ALWAYS AS (
        CASE WHEN status = 'IN_TRANSACTION' THEN product_id ELSE NULL END
    ) STORED,
    ADD UNIQUE KEY uk_intent_trading_product (trading_product_id),
    ADD KEY idx_intent_customer_status_time (customer_id, status, submitted_at),
    ADD CONSTRAINT fk_intent_customer FOREIGN KEY (customer_id) REFERENCES customer (id);

UPDATE purchase_intent i
JOIN product p ON p.id = i.product_id
SET i.product_name_snapshot = p.name;
ALTER TABLE purchase_intent
    MODIFY product_name_snapshot VARCHAR(200) NOT NULL;
UPDATE purchase_intent
SET status = 'FAILED'
WHERE status = 'UNSOLD';
UPDATE purchase_intent
SET status = 'FAILED', processed_at = NOW(6)
WHERE customer_id IS NULL AND status = 'QUEUING';

CREATE TABLE order_history (
    id BIGINT NOT NULL AUTO_INCREMENT,
    intent_id BIGINT NOT NULL,
    customer_id BIGINT NOT NULL,
    product_name_snapshot VARCHAR(200) NOT NULL,
    submitted_at DATETIME(6) NOT NULL,
    status VARCHAR(20) NOT NULL,
    transacted_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_order_history_intent (intent_id),
    KEY idx_order_history_customer_time (customer_id, transacted_at, id),
    CONSTRAINT fk_order_history_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT chk_order_history_terminal CHECK (status IN ('SUCCESS', 'FAILED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

UPDATE product_status_event
SET from_status = CASE from_status
        WHEN 'RESTORED_ONLINE' THEN 'ONLINE'
        WHEN 'SOLD' THEN 'OFFLINE'
        ELSE from_status
    END,
    to_status = CASE to_status
        WHEN 'RESTORED_ONLINE' THEN 'ONLINE'
        WHEN 'SOLD' THEN 'OFFLINE'
        ELSE to_status
    END;
ALTER TABLE product_status_event
    DROP CHECK chk_event_type,
    DROP CHECK chk_event_publish,
    ADD CONSTRAINT chk_event_type CHECK (event_type IN
        ('PUBLISHED', 'MANUAL_FREEZE', 'MANUAL_UNFREEZE', 'MANUAL_OFFLINE', 'MANUAL_ONLINE',
         'INVENTORY_OFFLINE', 'TRADE_STARTED', 'TRADE_FAILED', 'TRADE_SUCCEEDED')),
    ADD CONSTRAINT chk_event_publish CHECK (event_type <> 'PUBLISHED' OR from_status IS NULL);
