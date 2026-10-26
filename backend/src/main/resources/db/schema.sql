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
    status VARCHAR(20) NOT NULL,
    freeze_source VARCHAR(20) NULL,
    published_at DATETIME(6) NOT NULL,
    status_updated_at DATETIME(6) NULL,
    sold_at DATETIME(6) NULL,
    PRIMARY KEY (id),
    KEY idx_product_category_status (category2_id, status, published_at, id),
    CONSTRAINT fk_product_category2 FOREIGN KEY (category2_id) REFERENCES category (id),
    CONSTRAINT chk_product_price CHECK (price > 0),
    CONSTRAINT chk_product_stock CHECK (stock >= 0),
    CONSTRAINT chk_product_status CHECK (status IN ('ONLINE', 'FROZEN', 'OFFLINE'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE product_image (
    id BIGINT NOT NULL AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    sort_order INT NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_product_image_order (product_id, sort_order),
    CONSTRAINT fk_product_image_product FOREIGN KEY (product_id) REFERENCES product (id)
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
         'INVENTORY_OFFLINE', 'TRADE_STARTED', 'TRADE_FAILED', 'TRADE_SUCCEEDED')),
    CONSTRAINT chk_event_publish CHECK (event_type <> 'PUBLISHED' OR from_status IS NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
