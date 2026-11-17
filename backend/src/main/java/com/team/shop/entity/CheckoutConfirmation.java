package com.team.shop.entity;

import com.team.shop.entity.converter.MoneyStringConverter;
import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Convert;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 结算确认快照：所选行、已确认数量、商品身份与单价、总额摘要。只记录确认内容，
 * 不建订单、不扣库存，也不是自动过期取消订单的机制。下单只凭本人 token。
 */
@Entity
@Table(name = "checkout_confirmation", uniqueConstraints = {
        @UniqueConstraint(name = "uk_confirmation_token", columnNames = "token")})
public class CheckoutConfirmation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, updatable = false, length = 36, columnDefinition = "CHAR(36)")
    private String token;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "customer_id", nullable = false, updatable = false)
    private Customer customer;

    @Convert(converter = MoneyStringConverter.class)
    @Column(name = "total_amount", nullable = false, updatable = false, columnDefinition = "LONGTEXT")
    private BigDecimal totalAmount;

    @Column(nullable = false, updatable = false, length = 64, columnDefinition = "CHAR(64)")
    private String digest;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @OneToMany(mappedBy = "confirmation", cascade = CascadeType.ALL)
    @OrderBy("id ASC")
    private List<CheckoutConfirmationItem> items = new ArrayList<>();

    protected CheckoutConfirmation() {
    }

    public CheckoutConfirmation(String token, Customer customer, BigDecimal totalAmount, String digest,
                                LocalDateTime createdAt) {
        this.token = token;
        this.customer = customer;
        this.totalAmount = totalAmount;
        this.digest = digest;
        this.createdAt = createdAt;
    }

    public CheckoutConfirmationItem addItem(Long cartItemId, Product product, BigDecimal unitPrice,
                                            BigInteger quantity) {
        CheckoutConfirmationItem item = new CheckoutConfirmationItem(this, cartItemId, product, unitPrice, quantity);
        items.add(item);
        return item;
    }

    public Long getId() { return id; }
    public String getToken() { return token; }
    public Customer getCustomer() { return customer; }
    public BigDecimal getTotalAmount() { return totalAmount; }
    public String getDigest() { return digest; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public List<CheckoutConfirmationItem> getItems() { return items; }
}
