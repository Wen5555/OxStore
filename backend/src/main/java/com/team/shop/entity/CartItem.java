package com.team.shop.entity;

import com.team.shop.entity.converter.BigIntegerStringConverter;
import jakarta.persistence.Column;
import jakarta.persistence.Convert;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.math.BigInteger;
import java.time.LocalDateTime;

/**
 * 购物车行：一个客户对一个商品最多一行，数量为任意正整数。数量 0 由删除行表达，
 * 删除后重新加购得到新 id（AUTO_INCREMENT 持久，不复用），旧行改量不能让它复活。
 */
@Entity
@Table(name = "cart_item", uniqueConstraints = {
        @UniqueConstraint(name = "uk_cart_customer_product", columnNames = {"customer_id", "product_id"})})
public class CartItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "customer_id", nullable = false, updatable = false)
    private Customer customer;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false, updatable = false)
    private Product product;

    @Convert(converter = BigIntegerStringConverter.class)
    @Column(nullable = false, columnDefinition = "LONGTEXT")
    private BigInteger quantity;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    protected CartItem() {
    }

    public CartItem(Customer customer, Product product, BigInteger quantity, LocalDateTime now) {
        this.customer = customer;
        this.product = product;
        changeQuantity(quantity, now);
    }

    /** 改量；0 或负数不入库（要删行，请用 Repository 删除并写墓碑）。 */
    public void changeQuantity(BigInteger quantity, LocalDateTime now) {
        if (quantity.signum() <= 0) {
            throw new IllegalArgumentException("数量必须为正整数");
        }
        this.quantity = quantity;
        this.updatedAt = now;
    }

    public Long getId() { return id; }
    public Customer getCustomer() { return customer; }
    public Product getProduct() { return product; }
    public BigInteger getQuantity() { return quantity; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
}
