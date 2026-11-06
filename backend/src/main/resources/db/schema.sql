-- MySQL 8.0.16+ / InnoDB / utf8mb4. Application business timestamps use Asia/Shanghai.
CREATE TABLE seller (
    id BIGINT NOT NULL AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    password_updated_at DATETIME(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_seller_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

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

CREATE TABLE category (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(80) NOT NULL,
    parent_id BIGINT NULL,
    PRIMARY KEY (id),
    KEY idx_category_parent (parent_id),
    CONSTRAINT fk_category_parent FOREIGN KEY (parent_id) REFERENCES category (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    stock INT NOT NULL,
    category2_id BIGINT NOT NULL,
    selling_mode VARCHAR(20) NOT NULL DEFAULT 'FIXED_PRICE',
    status VARCHAR(20) NOT NULL,
    freeze_source VARCHAR(20) NULL,
    published_at DATETIME(6) NOT NULL,
    status_updated_at DATETIME(6) NULL,
    sold_at DATETIME(6) NULL,
    PRIMARY KEY (id),
    KEY idx_product_category_status (category2_id, status, published_at, id),
    KEY idx_product_status_time (status, published_at, id),
    KEY idx_product_mode_status_time (selling_mode, status, published_at, id),
    CONSTRAINT fk_product_category2 FOREIGN KEY (category2_id) REFERENCES category (id),
    CONSTRAINT chk_product_price CHECK (price > 0),
    CONSTRAINT chk_product_stock CHECK (stock >= 0),
    CONSTRAINT chk_product_status CHECK (status IN ('ONLINE', 'FROZEN', 'OFFLINE')),
    CONSTRAINT chk_product_selling_mode CHECK (selling_mode IN ('FIXED_PRICE', 'AUCTION')),
    CONSTRAINT chk_product_auction_stock CHECK (selling_mode <> 'AUCTION' OR stock BETWEEN 0 AND 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- A product never switches between fixed-price and auction after it is published.
DELIMITER //
CREATE TRIGGER trg_product_selling_mode_immutable BEFORE UPDATE ON product
FOR EACH ROW
BEGIN
  IF NEW.selling_mode <> OLD.selling_mode THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'selling_mode cannot change after publish';
  END IF;
END//
DELIMITER ;

CREATE TABLE product_image (
    id BIGINT NOT NULL AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    sort_order INT NOT NULL,
    content_type VARCHAR(20) NULL,
    size_bytes BIGINT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_product_image_order (product_id, sort_order),
    CONSTRAINT fk_product_image_product FOREIGN KEY (product_id) REFERENCES product (id),
    CONSTRAINT chk_product_image_order CHECK (sort_order BETWEEN 0 AND 8),
    CONSTRAINT chk_product_image_metadata CHECK (
        (content_type IS NULL AND size_bytes IS NULL) OR
        (content_type IS NOT NULL AND size_bytes IS NOT NULL AND
         content_type IN ('image/jpeg', 'image/png') AND size_bytes BETWEEN 1 AND 5242880)
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE purchase_intent (
    id BIGINT NOT NULL AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    customer_id BIGINT NULL,
    product_name_snapshot VARCHAR(200) NOT NULL,
    buyer_name VARCHAR(100) NOT NULL,
    buyer_phone VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    submitted_at DATETIME(6) NOT NULL,
    queue_seq BIGINT NOT NULL,
    updated_at DATETIME(6) NULL,
    processed_at DATETIME(6) NULL,
    trading_product_id BIGINT GENERATED ALWAYS AS (
        CASE WHEN status = 'IN_TRANSACTION' THEN product_id ELSE NULL END
    ) STORED,
    PRIMARY KEY (id),
    UNIQUE KEY uk_intent_trading_product (trading_product_id),
    UNIQUE KEY uk_intent_product_seq (product_id, queue_seq),
    KEY idx_intent_product_status_seq (product_id, status, queue_seq),
    KEY idx_intent_customer_status_time (customer_id, status, submitted_at),
    CONSTRAINT fk_intent_product FOREIGN KEY (product_id) REFERENCES product (id),
    CONSTRAINT fk_intent_customer FOREIGN KEY (customer_id) REFERENCES customer (id),
    CONSTRAINT chk_intent_status CHECK (status IN
        ('QUEUING', 'IN_TRANSACTION', 'SUCCESS', 'FAILED', 'CANCELLED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE trade_attempt (
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

CREATE TABLE product_status_event (
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
        ('PUBLISHED', 'MANUAL_FREEZE', 'MANUAL_UNFREEZE', 'MANUAL_OFFLINE', 'MANUAL_ONLINE',
         'INVENTORY_OFFLINE', 'TRADE_STARTED', 'TRADE_FAILED', 'TRADE_SUCCEEDED', 'AUCTION_UNSOLD')),
    CONSTRAINT chk_event_publish CHECK (event_type <> 'PUBLISHED' OR from_status IS NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Auction mode (PB-A01～A04). One session per AUCTION product; the winner is fulfilled
-- through an ordinary IN_TRANSACTION purchase_intent and the existing SUCCESS/FAILED flow.
CREATE TABLE auction_session (
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

-- Only accepted bids are stored. bid_seq equals the session bid_count after acceptance.
CREATE TABLE auction_bid (
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

-- In-app settlement reminders. The type fixes the recipient, so (auction, type) is the idempotency key.
CREATE TABLE auction_notification (
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
