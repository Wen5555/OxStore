package com.team.shop.entity;

import com.team.shop.domain.FreezeSource;
import com.team.shop.domain.OfflineReason;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.ProductStateMachine;
import com.team.shop.domain.ProductStatus;
import com.team.shop.domain.SellingMode;
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
import java.math.BigInteger;
import jakarta.persistence.Convert;
import com.team.shop.entity.converter.BigIntegerStringConverter;
import com.team.shop.exception.BizException;
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

    @Convert(converter = BigIntegerStringConverter.class)
    @Column(nullable = false, columnDefinition = "LONGTEXT")
    private BigInteger stock;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "category2_id", nullable = false)
    private Category category;

    @OneToMany(mappedBy = "product", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("sortOrder ASC")
    private List<ProductImage> images = new ArrayList<>();

    /** 发布后不可切换；数据库触发器同样拒绝修改。 */
    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(name = "selling_mode", nullable = false, updatable = false, length = 20)
    private SellingMode sellingMode = SellingMode.FIXED_PRICE;

    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(nullable = false, length = 20)
    private ProductStatus status;

    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(name = "freeze_source", length = 20)
    private FreezeSource freezeSource;

    /** 下架原因；取消回补时据此判断能否自动恢复在售。取值与清除规则由库存维护（B-006）负责。 */
    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(name = "offline_reason", length = 20)
    private OfflineReason offlineReason;

    @Column(name = "published_at", nullable = false)
    private LocalDateTime publishedAt;

    @Column(name = "status_updated_at")
    private LocalDateTime statusUpdatedAt;

    @Column(name = "sold_at")
    private LocalDateTime soldAt;

    protected Product() {
    }

    /** Create an item with its initial inventory and category. */
    public static Product create(String name, String description, BigDecimal price, BigInteger stock, Category category) {
        requireNonNegative(stock);
        Product p = new Product();
        p.name = name;
        p.description = description;
        p.price = price;
        p.stock = stock;
        p.category = category;
        p.status = stock.signum() > 0 ? ProductStatus.ONLINE : ProductStatus.OFFLINE;
        p.offlineReason = stock.signum() == 0 ? OfflineReason.AUTO_ZERO : null;
        p.publishedAt = BusinessTime.now();
        p.statusUpdatedAt = p.publishedAt;
        return p;
    }

    /** Create an auction item: the start price is the listed price and inventory is fixed at 1. */
    public static Product createAuction(String name, String description, BigDecimal startPrice, Category category) {
        Product p = create(name, description, startPrice, 1, category);
        p.sellingMode = SellingMode.AUCTION;
        return p;
    }

    /** Compatibility for internal callers creating small legacy fixtures. */
    public static Product create(String name, String description, BigDecimal price, int stock, Category category) {
        return create(name, description, price, BigInteger.valueOf(stock), category);
    }

    public static void requireNonNegative(BigInteger stock) {
        if (stock == null || stock.signum() < 0) throw new BizException("库存不能为负数，请输入非负整数。");
    }

    /** Called inside the future checkout transaction after the product row has been locked. */
    public void deductForOrder(BigInteger quantity, LocalDateTime now) {
        requirePositiveQuantity(quantity);
        if (isAuction()) throw new com.team.shop.exception.StateConflictException("拍卖商品不能经购物车下单", 40908);
        if (status != ProductStatus.ONLINE) throw new com.team.shop.exception.StateConflictException("商品已下架");
        if (stock.compareTo(quantity) < 0) throw new com.team.shop.exception.StateConflictException("库存不足", 40905);
        stock = stock.subtract(quantity);
        if (stock.signum() == 0) {
            status = ProductStatus.OFFLINE;
            offlineReason = OfflineReason.AUTO_ZERO;
            freezeSource = null;
        }
        statusUpdatedAt = now;
    }

    /** Caller must atomically guard the order transition so this compensation runs only once. */
    public void restoreForCancelledOrder(BigInteger quantity, LocalDateTime now) {
        requirePositiveQuantity(quantity);
        if (isAuction()) throw new com.team.shop.exception.StateConflictException("拍卖商品不使用五态取消回补", 40908);
        stock = stock.add(quantity);
        if (status == ProductStatus.OFFLINE && offlineReason == OfflineReason.AUTO_ZERO && stock.signum() > 0) {
            status = ProductStatus.ONLINE;
            offlineReason = null;
            freezeSource = null;
        }
        statusUpdatedAt = now;
    }

    private static void requirePositiveQuantity(BigInteger quantity) {
        if (quantity == null || quantity.signum() <= 0) throw new BizException("数量无效，请输入正整数");
    }

    public void addImage(String imagePath, int sortOrder, String contentType, long sizeBytes) {
        images.add(new ProductImage(this, imagePath, sortOrder, contentType, sizeBytes));
    }

    public void updateInventoryAndCategory(BigInteger stock, Category category, LocalDateTime now) {
        requireNonNegative(stock);
        this.stock = stock;
        this.category = category;
        if (stock.signum() == 0) {
            this.status = ProductStatus.OFFLINE;
            if (offlineReason != OfflineReason.MANUAL) offlineReason = OfflineReason.AUTO_ZERO;
            this.freezeSource = null;
        }
        this.statusUpdatedAt = now;
    }

    public void updateInventoryAndCategory(int stock, Category category, LocalDateTime now) {
        updateInventoryAndCategory(BigInteger.valueOf(stock), category, now);
    }

    public void takeOffline(LocalDateTime now) {
        if (status != ProductStatus.ONLINE && status != ProductStatus.OFFLINE) {
            throw new com.team.shop.exception.StateConflictException("商品当前不可手动下架");
        }
        status = ProductStatus.OFFLINE;
        offlineReason = OfflineReason.MANUAL;
        freezeSource = null;
        statusUpdatedAt = now;
    }

    public void putOnline(LocalDateTime now) {
        if (status != ProductStatus.OFFLINE || stock.signum() <= 0) {
            throw new com.team.shop.exception.StateConflictException("仅库存大于零的已下架商品可以上架");
        }
        status = ProductStatus.ONLINE;
        offlineReason = null;
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
        if (stock.signum() <= 0) {
            throw new com.team.shop.exception.StateConflictException("库存不足，无法确认交易成功", 40905);
        }
        stock = stock.subtract(BigInteger.ONE);
        this.status = stock.signum() == 0 ? ProductStatus.OFFLINE : ProductStatus.ONLINE;
        this.offlineReason = stock.signum() == 0 ? OfflineReason.AUTO_ZERO : null;
        this.freezeSource = null;
        if (stock.signum() == 0) {
            this.soldAt = now;
        }
        this.statusUpdatedAt = now;
        return stock.signum() == 0;
    }

    /** A failed trade restores the item to sale without starting the next queued trade. */
    public void markTradeFailed(LocalDateTime now) {
        ProductStateMachine.assertCanMarkFailed(status, freezeSource);
        this.status = ProductStatus.ONLINE;
        this.offlineReason = null;
        this.freezeSource = null;
        this.statusUpdatedAt = now;
    }

    /** Auction fulfillment failure leaves the item offline for the seller to republish. */
    public void markAuctionTradeFailed(LocalDateTime now) {
        if (!isAuction()) {
            throw new com.team.shop.exception.StateConflictException("只有拍卖商品使用该失败收尾");
        }
        ProductStateMachine.assertCanMarkFailed(status, freezeSource);
        this.status = ProductStatus.OFFLINE;
        this.offlineReason = OfflineReason.MANUAL;
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

    public BigInteger getStock() { return stock; }

    public Category getCategory() { return category; }

    public List<ProductImage> getImages() { return images; }

    public SellingMode getSellingMode() { return sellingMode; }

    public boolean isAuction() { return sellingMode == SellingMode.AUCTION; }

    public ProductStatus getStatus() {
        return status;
    }

    public FreezeSource getFreezeSource() {
        return freezeSource;
    }

    public OfflineReason getOfflineReason() {
        return offlineReason;
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
