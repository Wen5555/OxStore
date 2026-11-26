package com.team.shop.entity;

import com.team.shop.domain.ReceiptOperationType;
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
import jakarta.persistence.UniqueConstraint;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDateTime;

/**
 * 幂等回执：(客户, 操作类型, 请求键) 唯一，只落成功结果，且必须与业务变更在同一事务提交，
 * 失败不留回执。requestHash 用于识别“同键不同 body”；不保存 JWT 或口令。
 */
@Entity
@Table(name = "operation_receipt", uniqueConstraints = {
        @UniqueConstraint(name = "uk_receipt_request", columnNames = {"customer_id", "operation_type", "request_key"})})
public class OperationReceipt {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "customer_id", nullable = false, updatable = false)
    private Customer customer;

    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(name = "operation_type", nullable = false, updatable = false, length = 30)
    private ReceiptOperationType operationType;

    @Column(name = "request_key", nullable = false, updatable = false, length = 36, columnDefinition = "CHAR(36)")
    private String requestKey;

    @Column(name = "request_hash", nullable = false, updatable = false, length = 64, columnDefinition = "CHAR(64)")
    private String requestHash;

    /** 原成功结果的 JSON，同键重试据此返回 */
    @Column(name = "result_payload", nullable = false, updatable = false, columnDefinition = "LONGTEXT")
    private String resultPayload;

    @Column(name = "completed_at", nullable = false, updatable = false)
    private LocalDateTime completedAt;

    protected OperationReceipt() {
    }

    public OperationReceipt(Customer customer, ReceiptOperationType operationType, String requestKey,
                            String requestHash, String resultPayload, LocalDateTime completedAt) {
        this.customer = customer;
        this.operationType = operationType;
        this.requestKey = requestKey;
        this.requestHash = requestHash;
        this.resultPayload = resultPayload;
        this.completedAt = completedAt;
    }

    public Long getId() { return id; }
    public Customer getCustomer() { return customer; }
    public ReceiptOperationType getOperationType() { return operationType; }
    public String getRequestKey() { return requestKey; }
    public String getRequestHash() { return requestHash; }
    public String getResultPayload() { return resultPayload; }
    public LocalDateTime getCompletedAt() { return completedAt; }
}
