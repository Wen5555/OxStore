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

import java.math.BigDecimal;
import java.math.BigInteger;

/** 确认快照中的一行。cart_item_id 不加外键：车行之后可能被删，快照仍须保留。 */
@Entity
@Table(name = "checkout_confirmation_item", uniqueConstraints = {
        @UniqueConstraint(name = "uk_confirmation_item_cart", columnNames = {"confirmation_id", "cart_item_id"})})
public class CheckoutConfirmationItem {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "confirmation_id", nullable = false, updatable = false)
    private CheckoutConfirmation confirmation;

    @Column(name = "cart_item_id", nullable = false, updatable = false)
    private Long cartItemId;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false, updatable = false)
    private Product product;

    @Column(name = "unit_price", nullable = false, updatable = false, precision = 10, scale = 2)
    private BigDecimal unitPrice;

    @Convert(converter = BigIntegerStringConverter.class)
    @Column(nullable = false, updatable = false, columnDefinition = "LONGTEXT")
    private BigInteger quantity;

    protected CheckoutConfirmationItem() {
    }

    CheckoutConfirmationItem(CheckoutConfirmation confirmation, Long cartItemId, Product product,
                             BigDecimal unitPrice, BigInteger quantity) {
        this.confirmation = confirmation;
        this.cartItemId = cartItemId;
        this.product = product;
        this.unitPrice = unitPrice;
        this.quantity = quantity;
    }

    public Long getId() { return id; }
    public CheckoutConfirmation getConfirmation() { return confirmation; }
    public Long getCartItemId() { return cartItemId; }
    public Product getProduct() { return product; }
    public BigDecimal getUnitPrice() { return unitPrice; }
    public BigInteger getQuantity() { return quantity; }
}
