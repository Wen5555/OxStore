package com.team.shop.entity;

import com.team.shop.domain.AuctionNotificationType;
import com.team.shop.domain.AuctionStatus;
import com.team.shop.domain.NotificationRecipientRole;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 结拍站内提醒。类型决定收件人，(场次, 类型) 唯一，重复结拍不会重复提醒。
 */
@Entity
@Table(name = "auction_notification", uniqueConstraints =
        @UniqueConstraint(name = "uk_notification_auction_type", columnNames = {"auction_id", "notification_type"}))
public class AuctionNotification {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "auction_id", nullable = false, updatable = false)
    private AuctionSession auction;

    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(name = "notification_type", nullable = false, updatable = false, length = 30)
    private AuctionNotificationType type;

    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(name = "recipient_role", nullable = false, updatable = false, length = 10)
    private NotificationRecipientRole recipientRole;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "recipient_customer_id", updatable = false)
    private Customer recipientCustomer;

    @Column(name = "product_name_snapshot", nullable = false, updatable = false, length = 200)
    private String productNameSnapshot;

    @Column(name = "final_price", updatable = false, precision = 10, scale = 2)
    private BigDecimal finalPrice;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "read_at")
    private LocalDateTime readAt;

    protected AuctionNotification() {
    }

    /** Build the reminder for a settled session; AUCTION_WON goes to the leader, others to sellers. */
    public static AuctionNotification forSettlement(AuctionSession auction, AuctionNotificationType type,
                                                    LocalDateTime now) {
        boolean sold = auction.getStatus() == AuctionStatus.ENDED_SOLD;
        if (auction.getStatus() == AuctionStatus.LIVE || sold == (type == AuctionNotificationType.AUCTION_UNSOLD)) {
            throw new IllegalArgumentException("提醒类型与拍卖结果不一致");
        }
        AuctionNotification n = new AuctionNotification();
        n.auction = auction;
        n.type = type;
        n.recipientRole = type.recipientRole();
        n.recipientCustomer = type == AuctionNotificationType.AUCTION_WON ? auction.getLeader() : null;
        n.productNameSnapshot = auction.getProduct().getName();
        n.finalPrice = sold ? auction.getCurrentPrice() : null;
        n.createdAt = now;
        return n;
    }

    public void markRead(LocalDateTime now) {
        if (readAt == null) {
            readAt = now;
        }
    }

    public Long getId() { return id; }
    public AuctionSession getAuction() { return auction; }
    public AuctionNotificationType getType() { return type; }
    public NotificationRecipientRole getRecipientRole() { return recipientRole; }
    public Customer getRecipientCustomer() { return recipientCustomer; }
    public String getProductNameSnapshot() { return productNameSnapshot; }
    public BigDecimal getFinalPrice() { return finalPrice; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getReadAt() { return readAt; }
}
