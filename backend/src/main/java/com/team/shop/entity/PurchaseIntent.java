package com.team.shop.entity;

import com.team.shop.domain.IntentStateMachine;
import com.team.shop.domain.BusinessTime;
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

    @Column(name = "buyer_name", nullable = false, length = 100)
    private String buyerName;

    @Column(name = "buyer_phone", nullable = false, length = 20)
    private String buyerPhone;

    @Column(name = "token_hash", length = 255)
    private String tokenHash;

    @Column(name = "token_lookup", length = 64)
    private String tokenLookup;

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

    /** 提交一条排队意向 */
    public static PurchaseIntent submit(Product product, String buyerName, String buyerPhone,
                                        String tokenHash, String tokenLookup, long queueSeq) {
        PurchaseIntent i = new PurchaseIntent();
        i.product = product;
        i.buyerName = buyerName;
        i.buyerPhone = buyerPhone;
        i.tokenHash = tokenHash;
        i.tokenLookup = tokenLookup;
        i.status = IntentStatus.QUEUING;
        i.submittedAt = BusinessTime.now();
        i.queueSeq = queueSeq;
        return i;
    }

    /** 买家凭口令码撤销 */
    public void cancel(LocalDateTime now) {
        IntentStateMachine.assertCanCancel(status);
        this.status = IntentStatus.CANCELLED;
        this.processedAt = now;
        this.tokenHash = null;
        this.tokenLookup = null;
    }

    /** 买家凭口令码修改姓名/电话（传 null 的字段保持原值） */
    public void modifyInfo(String newName, String newPhone) {
        IntentStateMachine.assertCanModify(status);
        if (newName != null) {
            this.buyerName = newName;
        }
        if (newPhone != null) {
            this.buyerPhone = newPhone;
        }
        this.updatedAt = BusinessTime.now();
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
        this.tokenHash = null;
        this.tokenLookup = null;
    }

    /** 交易失败：作废 */
    public void markFailed(LocalDateTime now) {
        IntentStateMachine.assertCanMarkFailed(status);
        this.status = IntentStatus.FAILED;
        this.processedAt = now;
        this.tokenHash = null;
        this.tokenLookup = null;
    }

    /** 交易失败：仅更新排序序号，首次提交时间不变，旧口令失效。 */
    public void requeue(long newQueueSeq, LocalDateTime now) {
        IntentStateMachine.assertCanMarkFailed(status);
        this.status = IntentStatus.QUEUING;
        this.queueSeq = newQueueSeq;
        this.processedAt = now;
        this.tokenHash = null;
        this.tokenLookup = null;
    }

    /** 商品售出，其余排队意向统一标记未成交 */
    public void markUnsold(LocalDateTime now) {
        this.status = IntentStatus.UNSOLD;
        this.processedAt = now;
        this.tokenHash = null;
        this.tokenLookup = null;
    }

    public Long getId() {
        return id;
    }

    public Product getProduct() {
        return product;
    }

    public String getBuyerName() {
        return buyerName;
    }

    public String getBuyerPhone() {
        return buyerPhone;
    }

    public String getTokenHash() {
        return tokenHash;
    }

    public String getTokenLookup() { return tokenLookup; }

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
