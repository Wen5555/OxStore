package com.team.shop.entity;

import com.team.shop.domain.FreezeSource;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.ProductStateMachine;
import com.team.shop.domain.ProductStatus;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.CascadeType;

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 商品。状态迁移必须走领域方法（内部经 ProductStateMachine 校验）。
 */
@Entity
@Table(name = "product")
public class Product {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 200)
    private String name;

    @Column(nullable = false, columnDefinition = "TEXT")
    private String description;

    @Column(nullable = false, precision = 10, scale = 2)
    private BigDecimal price;

    @Column(nullable = false)
    private int stock;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "category2_id", nullable = false)
    private Category category;

    @OneToMany(mappedBy = "product", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("sortOrder ASC")
    private List<ProductImage> images = new ArrayList<>();

    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(nullable = false, length = 20)
    private ProductStatus status;

    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(name = "freeze_source", length = 20)
    private FreezeSource freezeSource;

    @Column(name = "published_at", nullable = false)
    private LocalDateTime publishedAt;

    @Column(name = "status_updated_at")
    private LocalDateTime statusUpdatedAt;

    @Column(name = "sold_at")
    private LocalDateTime soldAt;

    protected Product() {
    }

    /** Create an item with its initial inventory and category. */
    public static Product create(String name, String description, BigDecimal price, int stock, Category category) {
        Product p = new Product();
        p.name = name;
        p.description = description;
        p.price = price;
        p.stock = stock;
        p.category = category;
        p.status = stock > 0 ? ProductStatus.ONLINE : ProductStatus.OFFLINE;
        p.publishedAt = BusinessTime.now();
        p.statusUpdatedAt = p.publishedAt;
        return p;
    }

    public void addImage(String imagePath, int sortOrder, String contentType, long sizeBytes) {
        images.add(new ProductImage(this, imagePath, sortOrder, contentType, sizeBytes));
    }

    public void updateInventoryAndCategory(int stock, Category category, LocalDateTime now) {
        if (stock < 0) {
            throw new IllegalArgumentException("库存不能为负数");
        }
        this.stock = stock;
        this.category = category;
        if (stock == 0) {
            this.status = ProductStatus.OFFLINE;
            this.freezeSource = null;
        }
        this.statusUpdatedAt = now;
    }

    public void takeOffline(LocalDateTime now) {
        if (status != ProductStatus.ONLINE) {
            throw new com.team.shop.exception.StateConflictException("仅在售商品可以手动下架");
        }
        status = ProductStatus.OFFLINE;
        freezeSource = null;
        statusUpdatedAt = now;
    }

    public void putOnline(LocalDateTime now) {
        if (status != ProductStatus.OFFLINE || stock <= 0) {
            throw new com.team.shop.exception.StateConflictException("仅库存大于零的已下架商品可以上架");
        }
        status = ProductStatus.ONLINE;
        freezeSource = null;
        statusUpdatedAt = now;
    }

    public void startTrade(LocalDateTime now) {
        ProductStateMachine.assertCanStartTrade(status);
        this.status = ProductStatus.FROZEN;
        this.freezeSource = FreezeSource.TRADE;
        this.statusUpdatedAt = now;
    }

    /** Confirm one successful purchase and apply its inventory change. */
    public boolean markTradeSucceeded(LocalDateTime now) {
        ProductStateMachine.assertCanMarkSuccess(status, freezeSource);
        if (stock <= 0) {
            throw new com.team.shop.exception.StateConflictException("库存不足，无法确认交易成功", 40905);
        }
        stock--;
        this.status = stock == 0 ? ProductStatus.OFFLINE : ProductStatus.ONLINE;
        this.freezeSource = null;
        if (stock == 0) {
            this.soldAt = now;
        }
        this.statusUpdatedAt = now;
        return stock == 0;
    }

    /** A failed trade restores the item to sale without starting the next queued trade. */
    public void markTradeFailed(LocalDateTime now) {
        ProductStateMachine.assertCanMarkFailed(status, freezeSource);
        this.status = ProductStatus.ONLINE;
        this.freezeSource = null;
        this.statusUpdatedAt = now;
    }

    public Long getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getDescription() {
        return description;
    }

    public BigDecimal getPrice() {
        return price;
    }

    public int getStock() { return stock; }

    public Category getCategory() { return category; }

    public List<ProductImage> getImages() { return images; }

    public ProductStatus getStatus() {
        return status;
    }

    public FreezeSource getFreezeSource() {
        return freezeSource;
    }

    public LocalDateTime getPublishedAt() {
        return publishedAt;
    }

    public LocalDateTime getStatusUpdatedAt() {
        return statusUpdatedAt;
    }

    public LocalDateTime getSoldAt() {
        return soldAt;
    }
}
