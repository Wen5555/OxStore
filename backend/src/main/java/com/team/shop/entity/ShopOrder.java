package com.team.shop.entity;

import com.team.shop.domain.OrderCancelledBy;
import com.team.shop.domain.OrderStatus;
import com.team.shop.entity.converter.MoneyStringConverter;
import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Convert;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
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
import jakarta.persistence.Version;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 挑战 B 订单主表。订单号、归属、总额、创建时间不可变；明细见 {@link OrderItem}（快照只读）。
 * 状态合法性由订单状态机判定（B-013/B-014），这里只负责持久化形状；数据库 CHECK 与触发器
 * 同样拒绝取消元数据不成对、终态再变化。
 */
@Entity
@Table(name = "shop_order", uniqueConstraints = {
        @UniqueConstraint(name = "uk_shop_order_no", columnNames = "order_no")})
public class ShopOrder {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /** UUID，不可变，与旧意向 ID 不共用空间 */
    @Column(name = "order_no", nullable = false, updatable = false, length = 36, columnDefinition = "CHAR(36)")
    private String orderNo;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "customer_id", nullable = false, updatable = false)
    private Customer customer;

    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(nullable = false, length = 20)
    private OrderStatus status;

    @Convert(converter = MoneyStringConverter.class)
    @Column(name = "total_amount", nullable = false, updatable = false, columnDefinition = "LONGTEXT")
    private BigDecimal totalAmount;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(name = "cancelled_by", length = 20)
    private OrderCancelledBy cancelledBy;

    @Column(name = "cancelled_at")
    private LocalDateTime cancelledAt;

    @Column(name = "cancel_reason", length = 500)
    private String cancelReason;

    /** 仅用于状态并发控制；任何商品更新都不得据此重算历史快照 */
    @Version
    @Column(nullable = false)
    private long version;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL)
    @OrderBy("id ASC")
    private List<OrderItem> items = new ArrayList<>();

    protected ShopOrder() {
    }

    public ShopOrder(String orderNo, Customer customer, BigDecimal totalAmount, LocalDateTime createdAt) {
        this.orderNo = orderNo;
        this.customer = customer;
        this.totalAmount = totalAmount;
        this.createdAt = createdAt;
        this.status = OrderStatus.PLACED;
    }

    /** 追加一条不可变明细快照；同单同商品只能有一条（数据库唯一约束兜底）。 */
    public OrderItem addItem(Product product, String productName, BigDecimal unitPrice,
                             BigInteger quantity, BigDecimal lineAmount) {
        OrderItem item = new OrderItem(this, product, productName, unitPrice, quantity, lineAmount);
        items.add(item);
        return item;
    }

    /** 持久化状态变更；是否合法由订单状态机先行判定。 */
    public void applyStatus(OrderStatus next) {
        this.status = next;
    }

    /** 记录取消元数据并置为 CANCELLED；是否允许取消由 B-014 判定。 */
    public void markCancelled(OrderCancelledBy by, String reason, LocalDateTime at) {
        this.status = OrderStatus.CANCELLED;
        this.cancelledBy = by;
        this.cancelledAt = at;
        this.cancelReason = reason;
    }

    public Long getId() { return id; }
    public String getOrderNo() { return orderNo; }
    public Customer getCustomer() { return customer; }
    public OrderStatus getStatus() { return status; }
    public BigDecimal getTotalAmount() { return totalAmount; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public OrderCancelledBy getCancelledBy() { return cancelledBy; }
    public LocalDateTime getCancelledAt() { return cancelledAt; }
    public String getCancelReason() { return cancelReason; }
    public long getVersion() { return version; }
    public List<OrderItem> getItems() { return items; }
}
