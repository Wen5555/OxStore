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

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.math.BigDecimal;
import java.time.LocalDateTime;

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

    @Column(name = "image_path", nullable = false, length = 500)
    private String imagePath;

    @Column(nullable = false, precision = 10, scale = 2)
    private BigDecimal price;

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

    /** 创建一件在售商品 */
    public static Product create(String name, String description, String imagePath, BigDecimal price) {
        Product p = new Product();
        p.name = name;
        p.description = description;
        p.imagePath = imagePath;
        p.price = price;
        p.status = ProductStatus.ONLINE;
        p.publishedAt = BusinessTime.now();
        p.statusUpdatedAt = p.publishedAt;
        return p;
    }

    /** 卖家手动冻结 */
    public void freezeManually(LocalDateTime now) {
        ProductStateMachine.assertCanFreezeManually(status);
        this.status = ProductStatus.FROZEN;
        this.freezeSource = FreezeSource.MANUAL;
        this.statusUpdatedAt = now;
    }

    /** 卖家手动解冻 */
    public void unfreezeManually(LocalDateTime now) {
        ProductStateMachine.assertCanUnfreezeManually(status, freezeSource);
        this.status = ProductStatus.ONLINE;
        this.freezeSource = null;
        this.statusUpdatedAt = now;
    }

    /** 开始交易（选择队首） */
    public void startTrade(LocalDateTime now) {
        ProductStateMachine.assertCanStartTrade(status);
        this.status = ProductStatus.FROZEN;
        this.freezeSource = FreezeSource.TRADE;
        this.statusUpdatedAt = now;
    }

    /** 确认交易成功：下架 */
    public void markSold(LocalDateTime now) {
        ProductStateMachine.assertCanMarkSuccess(status, freezeSource);
        this.status = ProductStatus.SOLD;
        this.freezeSource = null;
        this.soldAt = now;
        this.statusUpdatedAt = now;
    }

    /** 确认交易失败：恢复在售（若队列非空，服务层随后自动递补并再次 startTrade） */
    public void markTradeFailed(LocalDateTime now) {
        ProductStateMachine.assertCanMarkFailed(status, freezeSource);
        this.status = ProductStatus.RESTORED_ONLINE;
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

    public String getImagePath() {
        return imagePath;
    }

    public BigDecimal getPrice() {
        return price;
    }

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
