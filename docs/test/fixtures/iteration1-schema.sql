-- 仅用于空数据库首次建表；已有数据请使用 db/migrations/V2__queue_history.sql。
-- MySQL 8.0.16+ / InnoDB / utf8mb4；应用业务时间统一为 Asia/Shanghai。
CREATE TABLE IF NOT EXISTS seller (
    id BIGINT NOT NULL AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    password_updated_at DATETIME(6) NULL,
    PRIMARY KEY (id), UNIQUE KEY uk_seller_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS product (
    id BIGINT NOT NULL AUTO_INCREMENT,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    image_path VARCHAR(500) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    freeze_source VARCHAR(20) NULL,
    published_at DATETIME(6) NOT NULL,
    status_updated_at DATETIME(6) NULL,
    sold_at DATETIME(6) NULL,
    active_flag TINYINT GENERATED ALWAYS AS (
        CASE WHEN status IN ('ONLINE','RESTORED_ONLINE','FROZEN') THEN 1 ELSE NULL END
    ) STORED,
    PRIMARY KEY (id), UNIQUE KEY uk_product_active (active_flag),
    CONSTRAINT chk_product_price CHECK (price > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS purchase_intent (
    id BIGINT NOT NULL AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    buyer_name VARCHAR(100) NOT NULL,
    buyer_phone VARCHAR(20) NOT NULL,
    token_hash VARCHAR(255) NULL,
    token_lookup VARCHAR(64) NULL,
    status VARCHAR(20) NOT NULL,
    submitted_at DATETIME(6) NOT NULL,
    queue_seq BIGINT NOT NULL,
    updated_at DATETIME(6) NULL,
    processed_at DATETIME(6) NULL,
    trading_flag TINYINT GENERATED ALWAYS AS (
        CASE WHEN status = 'IN_TRANSACTION' THEN 1 ELSE NULL END
    ) STORED,
    PRIMARY KEY (id), UNIQUE KEY uk_intent_trading (trading_flag),
    UNIQUE KEY uk_intent_product_seq (product_id, queue_seq),
    UNIQUE KEY uk_intent_token_lookup (token_lookup),
    KEY idx_intent_product_status_seq (product_id, status, queue_seq),
    CONSTRAINT fk_intent_product FOREIGN KEY (product_id) REFERENCES product (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

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
