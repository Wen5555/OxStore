package com.team.shop.entity;

import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.IntentStatus;
import com.team.shop.domain.IntentStateMachine;
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

/**
 * 首次提交时间不变；队列按 (queueSeq, id) 排序，重排仅分配新序号。
 */
@Entity
@Table(name = "purchase_intent")
public class PurchaseIntent {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false)
    private Product product;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "customer_id")
    private Customer customer;

    @Column(name = "product_name_snapshot", length = 200)
    private String productNameSnapshot;

    @Column(name = "buyer_name", nullable = false, length = 100)
    private String buyerName;

    @Column(name = "buyer_phone", nullable = false, length = 20)
    private String buyerPhone;

    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(nullable = false, length = 20)
    private IntentStatus status;

    @Column(name = "submitted_at", nullable = false)
    private LocalDateTime submittedAt;

    @Column(name = "queue_seq", nullable = false)
    private Long queueSeq;
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @Column(name = "processed_at")
    private LocalDateTime processedAt;

    protected PurchaseIntent() {
    }

    /** Submit an authenticated customer's single-item purchase intent. */
    public static PurchaseIntent submit(Product product, Customer customer, long queueSeq) {
        PurchaseIntent i = new PurchaseIntent();
        i.product = product;
        i.customer = customer;
        i.buyerName = customer.getUsername();
        i.buyerPhone = customer.getPhone();
        i.productNameSnapshot = product.getName();
        i.status = IntentStatus.QUEUING;
        i.submittedAt = BusinessTime.now();
        i.queueSeq = queueSeq;
        return i;
    }

    /** 进入交易 */
    public void enterTrade(LocalDateTime now) {
        IntentStateMachine.assertCanEnterTrade(status);
        this.status = IntentStatus.IN_TRANSACTION;
        this.processedAt = now;
    }

    /** 交易成功 */
    public void markSuccess(LocalDateTime now) {
        IntentStateMachine.assertCanMarkSuccess(status);
        this.status = IntentStatus.SUCCESS;
        this.processedAt = now;
    }

    /** 交易失败：作废 */
    public void markFailed(LocalDateTime now) {
        IntentStateMachine.assertCanMarkFailed(status);
        this.status = IntentStatus.FAILED;
        this.processedAt = now;
    }

    public void markQueuedIntentFailed(LocalDateTime now) {
        if (status != IntentStatus.QUEUING) {
            throw new com.team.shop.exception.StateConflictException("仅排队中的意向可以因下架作废");
        }
        this.status = IntentStatus.FAILED;
        this.processedAt = now;
    }

    /** Return a failed attempt to the tail of its product queue. */
    public void requeue(long newQueueSeq, LocalDateTime now) {
        IntentStateMachine.assertCanMarkFailed(status);
        this.status = IntentStatus.QUEUING;
        this.queueSeq = newQueueSeq;
        this.processedAt = now;
    }

    public Long getId() {
        return id;
    }

    public Product getProduct() {
        return product;
    }

    public Customer getCustomer() { return customer; }
    public String getProductNameSnapshot() { return productNameSnapshot; }

    public String getBuyerName() {
        return buyerName;
    }

    public String getBuyerPhone() {
        return buyerPhone;
    }

    public IntentStatus getStatus() {
        return status;
    }

    public LocalDateTime getSubmittedAt() {
        return submittedAt;
    }

    public Long getQueueSeq() { return queueSeq; }
    public LocalDateTime getUpdatedAt() {
        return updatedAt;
    }

    public LocalDateTime getProcessedAt() {
        return processedAt;
    }
}
