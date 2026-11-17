package com.team.shop.entity;

import com.team.shop.entity.converter.BigIntegerStringConverter;
import com.team.shop.entity.converter.MoneyStringConverter;
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

import java.math.BigDecimal;
import java.math.BigInteger;

/**
 * 订单明细快照：下单当时的商品名、单价、数量与行金额，之后不随商品变化改写。
 * 全部列 updatable=false，数据库触发器 trg_order_item_immutable 同样拒绝修改。
 */
@Entity
@Table(name = "order_item", uniqueConstraints = {
        @UniqueConstraint(name = "uk_order_item_product", columnNames = {"order_id", "product_id"})})
public class OrderItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "order_id", nullable = false, updatable = false)
    private ShopOrder order;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false, updatable = false)
    private Product product;

    @Column(name = "product_name_snapshot", nullable = false, updatable = false, length = 200)
    private String productNameSnapshot;

    /** 商品单价列本身是 DECIMAL(10,2)，快照沿用，不承载订单总额 */
    @Column(name = "unit_price_snapshot", nullable = false, updatable = false, precision = 10, scale = 2)
    private BigDecimal unitPriceSnapshot;

    @Convert(converter = BigIntegerStringConverter.class)
    @Column(name = "quantity_snapshot", nullable = false, updatable = false, columnDefinition = "LONGTEXT")
    private BigInteger quantitySnapshot;

    @Convert(converter = MoneyStringConverter.class)
    @Column(name = "line_amount_snapshot", nullable = false, updatable = false, columnDefinition = "LONGTEXT")
    private BigDecimal lineAmountSnapshot;

    protected OrderItem() {
    }

    OrderItem(ShopOrder order, Product product, String productName, BigDecimal unitPrice,
              BigInteger quantity, BigDecimal lineAmount) {
        if (quantity.signum() <= 0) {
            throw new IllegalArgumentException("数量必须为正整数");
        }
        this.order = order;
        this.product = product;
        this.productNameSnapshot = productName;
        this.unitPriceSnapshot = unitPrice;
        this.quantitySnapshot = quantity;
        this.lineAmountSnapshot = lineAmount;
    }

    public Long getId() { return id; }
    public ShopOrder getOrder() { return order; }
    public Product getProduct() { return product; }
    public String getProductNameSnapshot() { return productNameSnapshot; }
    public BigDecimal getUnitPriceSnapshot() { return unitPriceSnapshot; }
    public BigInteger getQuantitySnapshot() { return quantitySnapshot; }
    public BigDecimal getLineAmountSnapshot() { return lineAmountSnapshot; }
}
