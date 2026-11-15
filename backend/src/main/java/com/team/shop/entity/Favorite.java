package com.team.shop.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.time.LocalDateTime;

/**
 * 收藏：按商品身份绑定，一个客户对一个商品最多一条。重复收藏不更新时间；
 * 取消即删除记录，重新收藏是带新时间的新记录。
 */
@Entity
@Table(name = "favorite", uniqueConstraints = {
        @UniqueConstraint(name = "uk_favorite_customer_product", columnNames = {"customer_id", "product_id"})})
public class Favorite {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "customer_id", nullable = false, updatable = false)
    private Customer customer;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false, updatable = false)
    private Product product;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    protected Favorite() {
    }

    public Favorite(Customer customer, Product product, LocalDateTime createdAt) {
        this.customer = customer;
        this.product = product;
        this.createdAt = createdAt;
    }

    public Long getId() { return id; }
    public Customer getCustomer() { return customer; }
    public Product getProduct() { return product; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
