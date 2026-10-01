package com.team.shop.entity;
import com.team.shop.domain.*;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.time.LocalDateTime;
@Entity
@Table(name = "product_status_event")
public class ProductStatusEvent {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false)
    private Product product;
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "trade_attempt_id")
    private TradeAttempt tradeAttempt;
    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR) @Column(name = "event_type", nullable = false, length = 30)
    private ProductEventType eventType;
    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR) @Column(name = "from_status", length = 20)
    private ProductStatus fromStatus;
    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR) @Column(name = "to_status", nullable = false, length = 20)
    private ProductStatus toStatus;
    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR) @Column(name = "freeze_source", length = 20)
    private FreezeSource freezeSource;
    @Column(name = "occurred_at", nullable = false)
    private LocalDateTime occurredAt;
    protected ProductStatusEvent() { }
    public ProductStatusEvent(Product product, TradeAttempt attempt, ProductEventType type,
                              ProductStatus before, LocalDateTime now) {
        this.product = product; this.tradeAttempt = attempt; this.eventType = type;
        this.fromStatus = before; this.toStatus = product.getStatus();
        this.freezeSource = product.getFreezeSource(); this.occurredAt = now;
    }
    public Long getId() { return id; }
    public Product getProduct() { return product; }
    public TradeAttempt getTradeAttempt() { return tradeAttempt; }
    public ProductEventType getEventType() { return eventType; }
    public ProductStatus getFromStatus() { return fromStatus; }
    public ProductStatus getToStatus() { return toStatus; }
    public FreezeSource getFreezeSource() { return freezeSource; }
    public LocalDateTime getOccurredAt() { return occurredAt; }
}
