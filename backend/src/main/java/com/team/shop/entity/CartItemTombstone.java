package com.team.shop.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.time.LocalDateTime;

/**
 * 购物车行被删除（删行、清空、转收藏、结算清车）时在同一事务写入的最小归属记录，
 * 让旧 cartItemId 能区分“本人已删”“他人的行”和“从未存在”。不作为车行展示。
 */
@Entity
@Table(name = "cart_item_tombstone", uniqueConstraints = {
        @UniqueConstraint(name = "uk_cart_tombstone_item", columnNames = "cart_item_id")})
public class CartItemTombstone {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "cart_item_id", nullable = false, updatable = false)
    private Long cartItemId;

    @Column(name = "customer_id", nullable = false, updatable = false)
    private Long customerId;

    @Column(name = "product_id", nullable = false, updatable = false)
    private Long productId;

    @Column(name = "removed_at", nullable = false, updatable = false)
    private LocalDateTime removedAt;

    protected CartItemTombstone() {
    }

    public CartItemTombstone(Long cartItemId, Long customerId, Long productId, LocalDateTime removedAt) {
        this.cartItemId = cartItemId;
        this.customerId = customerId;
        this.productId = productId;
        this.removedAt = removedAt;
    }

    public Long getId() { return id; }
    public Long getCartItemId() { return cartItemId; }
    public Long getCustomerId() { return customerId; }
    public Long getProductId() { return productId; }
    public LocalDateTime getRemovedAt() { return removedAt; }
}
