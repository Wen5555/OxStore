-- Auction mode (PB-A01～A04). Apply after V5; safe to repeat.
-- Existing products become FIXED_PRICE; no product is converted to an auction.
DELIMITER //
DROP PROCEDURE IF EXISTS upgrade_oxstore_v6//
CREATE PROCEDURE upgrade_oxstore_v6()
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'product_image' AND column_name = 'size_bytes') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'V6 requires the complete V5 schema';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
      WHERE table_schema = DATABASE() AND table_name = 'product' AND column_name = 'selling_mode') THEN
    ALTER TABLE product ADD COLUMN selling_mode VARCHAR(20) NOT NULL DEFAULT 'FIXED_PRICE' AFTER category2_id;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
      WHERE constraint_schema = DATABASE() AND table_name = 'product' AND constraint_name = 'chk_product_selling_mode') THEN
    ALTER TABLE product ADD CONSTRAINT chk_product_selling_mode CHECK (selling_mode IN ('FIXED_PRICE', 'AUCTION'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints
      WHERE constraint_schema = DATABASE() AND table_name = 'product' AND constraint_name = 'chk_product_auction_stock') THEN
    ALTER TABLE product ADD CONSTRAINT chk_product_auction_stock CHECK (selling_mode <> 'AUCTION' OR stock BETWEEN 0 AND 1);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.statistics
      WHERE table_schema = DATABASE() AND table_name = 'product' AND index_name = 'idx_product_mode_status_time') THEN
    ALTER TABLE product ADD KEY idx_product_mode_status_time (selling_mode, status, published_at, id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.check_constraints
      WHERE constraint_schema = DATABASE() AND constraint_name = 'chk_event_type'
        AND check_clause LIKE '%AUCTION_UNSOLD%') THEN
    ALTER TABLE product_status_event
      DROP CHECK chk_event_type,
      ADD CONSTRAINT chk_event_type CHECK (event_type IN
        ('PUBLISHED', 'MANUAL_FREEZE', 'MANUAL_UNFREEZE', 'MANUAL_OFFLINE', 'MANUAL_ONLINE',
         'INVENTORY_OFFLINE', 'TRADE_STARTED', 'TRADE_FAILED', 'TRADE_SUCCEEDED', 'AUCTION_UNSOLD'));
  END IF;
END//
DELIMITER ;
CALL upgrade_oxstore_v6();
DROP PROCEDURE upgrade_oxstore_v6;

DROP TRIGGER IF EXISTS trg_product_selling_mode_immutable;
DELIMITER //
CREATE TRIGGER trg_product_selling_mode_immutable BEFORE UPDATE ON product
FOR EACH ROW
BEGIN
  IF NEW.selling_mode <> OLD.selling_mode THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'selling_mode cannot change after publish';
  END IF;
END//
DELIMITER ;

CREATE TABLE IF NOT EXISTS auction_session (
    id BIGINT NOT NULL AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    start_price DECIMAL(10,2) NOT NULL,
    min_increment DECIMAL(10,2) NOT NULL,
    current_price DECIMAL(10,2) NULL,
    leader_customer_id BIGINT NULL,
    bid_count INT NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    starts_at DATETIME(6) NOT NULL,
    ends_at DATETIME(6) NOT NULL,
    settled_at DATETIME(6) NULL,
    winner_intent_id BIGINT NULL,
    version BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uk_auction_product (product_id),
    UNIQUE KEY uk_auction_winner_intent (winner_intent_id),
    KEY idx_auction_status_ends (status, ends_at, id),
    KEY idx_auction_leader (leader_customer_id),
    CONSTRAINT fk_auction_product FOREIGN KEY (product_id) REFERENCES product (id),
    CONSTRAINT fk_auction_leader FOREIGN KEY (leader_customer_id) REFERENCES customer (id),
    CONSTRAINT fk_auction_winner_intent FOREIGN KEY (winner_intent_id) REFERENCES purchase_intent (id),
    CONSTRAINT chk_auction_prices CHECK (start_price > 0 AND min_increment > 0),
    CONSTRAINT chk_auction_window CHECK (ends_at > starts_at),
    CONSTRAINT chk_auction_status CHECK (status IN ('LIVE', 'ENDED_SOLD', 'ENDED_UNSOLD')),
    CONSTRAINT chk_auction_leading CHECK (
        (bid_count = 0 AND current_price IS NULL AND leader_customer_id IS NULL) OR
        (bid_count > 0 AND current_price IS NOT NULL AND current_price >= start_price AND
         leader_customer_id IS NOT NULL)),
    CONSTRAINT chk_auction_settlement CHECK (
        (status = 'LIVE' AND settled_at IS NULL AND winner_intent_id IS NULL) OR
        (status = 'ENDED_SOLD' AND settled_at IS NOT NULL AND bid_count > 0 AND winner_intent_id IS NOT NULL) OR
        (status = 'ENDED_UNSOLD' AND settled_at IS NOT NULL AND bid_count = 0 AND winner_intent_id IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS auction_bid (
    id BIGINT NOT NULL AUTO_INCREMENT,
    auction_id BIGINT NOT NULL,
    bid_seq INT NOT NULL,
    customer_id BIGINT NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    bid_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_bid_auction_seq (auction_id, bid_seq),
    UNIQUE KEY uk_bid_auction_amount (auction_id, amount),
    KEY idx_bid_customer_time (customer_id, bid_at, id),
    CONSTRAINT fk_bid_auction FOREIGN KEY (auction_id) REFERENCES auction_session (id),
    CONSTRAINT fk_bid_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT chk_bid_seq CHECK (bid_seq > 0),
    CONSTRAINT chk_bid_amount CHECK (amount > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS auction_notification (
    id BIGINT NOT NULL AUTO_INCREMENT,
    auction_id BIGINT NOT NULL,
    notification_type VARCHAR(30) NOT NULL,
    recipient_role VARCHAR(10) NOT NULL,
    recipient_customer_id BIGINT NULL,
    product_name_snapshot VARCHAR(200) NOT NULL,
    final_price DECIMAL(10,2) NULL,
    created_at DATETIME(6) NOT NULL,
    read_at DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_notification_auction_type (auction_id, notification_type),
    KEY idx_notification_customer_time (recipient_customer_id, created_at, id),
    KEY idx_notification_role_time (recipient_role, created_at, id),
    CONSTRAINT fk_notification_auction FOREIGN KEY (auction_id) REFERENCES auction_session (id),
    CONSTRAINT fk_notification_customer FOREIGN KEY (recipient_customer_id) REFERENCES customer (id),
    CONSTRAINT chk_notification_type CHECK (notification_type IN ('AUCTION_SOLD', 'AUCTION_UNSOLD', 'AUCTION_WON')),
    CONSTRAINT chk_notification_recipient CHECK (
        (recipient_role = 'SELLER' AND recipient_customer_id IS NULL AND
         notification_type IN ('AUCTION_SOLD', 'AUCTION_UNSOLD')) OR
        (recipient_role = 'CUSTOMER' AND recipient_customer_id IS NOT NULL AND notification_type = 'AUCTION_WON')),
    CONSTRAINT chk_notification_price CHECK (
        (notification_type = 'AUCTION_UNSOLD' AND final_price IS NULL) OR
        (notification_type <> 'AUCTION_UNSOLD' AND final_price IS NOT NULL AND final_price > 0)),
    CONSTRAINT chk_notification_read CHECK (read_at IS NULL OR read_at >= created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
