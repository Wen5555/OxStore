package com.team.shop.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Embeddable;
import jakarta.persistence.EmbeddedId;
import jakarta.persistence.Entity;
import jakarta.persistence.Table;

import java.io.Serializable;
import java.util.Objects;

/**
 * 收藏操作代次，须在持有同一客户锁时维护。转收藏成功的回执保存当时的 operationSeq；
 * 之后若 lastCancelSeq 更大，说明发生过独立取消，同键重试返回原结果而不重新收藏。
 */
@Entity
@Table(name = "favorite_mutation")
public class FavoriteMutation {

    @Embeddable
    public static class Key implements Serializable {
        @Column(name = "customer_id", nullable = false)
        private Long customerId;
        @Column(name = "product_id", nullable = false)
        private Long productId;

        protected Key() {
        }

        public Key(Long customerId, Long productId) {
            this.customerId = customerId;
            this.productId = productId;
        }

        public Long getCustomerId() { return customerId; }
        public Long getProductId() { return productId; }

        @Override
        public boolean equals(Object o) {
            return o instanceof Key k && Objects.equals(customerId, k.customerId)
                    && Objects.equals(productId, k.productId);
        }

        @Override
        public int hashCode() {
            return Objects.hash(customerId, productId);
        }
    }

    @EmbeddedId
    private Key id;

    @Column(name = "operation_seq", nullable = false)
    private long operationSeq;

    @Column(name = "last_cancel_seq", nullable = false)
    private long lastCancelSeq;

    protected FavoriteMutation() {
    }

    public FavoriteMutation(Long customerId, Long productId) {
        this.id = new Key(customerId, productId);
    }

    /** 收藏写入（含转收藏）占用一个新代次并返回它。 */
    public long recordWrite() {
        return ++operationSeq;
    }

    /** 独立取消收藏占用一个新代次，并把它记为最近一次取消。 */
    public long recordCancel() {
        lastCancelSeq = ++operationSeq;
        return lastCancelSeq;
    }

    public Key getId() { return id; }
    public long getOperationSeq() { return operationSeq; }
    public long getLastCancelSeq() { return lastCancelSeq; }
}
