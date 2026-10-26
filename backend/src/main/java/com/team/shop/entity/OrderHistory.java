package com.team.shop.entity;

import com.team.shop.domain.IntentStatus;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;

@Entity
@Table(name = "order_history")
public class OrderHistory {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "intent_id", nullable = false, unique = true)
    private Long intentId;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "customer_id", nullable = false)
    private Customer customer;

    @Column(name = "product_name_snapshot", nullable = false, length = 200)
    private String productNameSnapshot;

    @Column(name = "submitted_at", nullable = false)
    private LocalDateTime submittedAt;

    @Enumerated(EnumType.STRING)
    @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(nullable = false, length = 20)
    private IntentStatus status;

    @Column(name = "transacted_at", nullable = false)
    private LocalDateTime transactedAt;

    protected OrderHistory() {
    }

    public OrderHistory(Long intentId, Customer customer, String productNameSnapshot,
                        LocalDateTime submittedAt, IntentStatus status, LocalDateTime transactedAt) {
        if (status != IntentStatus.SUCCESS && status != IntentStatus.FAILED) {
            throw new IllegalArgumentException("Order history only stores terminal success/failure records");
        }
        this.intentId = intentId;
        this.customer = customer;
        this.productNameSnapshot = productNameSnapshot;
        this.submittedAt = submittedAt;
        this.status = status;
        this.transactedAt = transactedAt;
    }

    public Long getId() { return id; }
    public Long getIntentId() { return intentId; }
    public Customer getCustomer() { return customer; }
    public String getProductNameSnapshot() { return productNameSnapshot; }
    public LocalDateTime getSubmittedAt() { return submittedAt; }
    public IntentStatus getStatus() { return status; }
    public LocalDateTime getTransactedAt() { return transactedAt; }
}
