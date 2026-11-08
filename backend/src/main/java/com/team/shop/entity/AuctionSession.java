package com.team.shop.entity;

import com.team.shop.domain.AuctionStatus;
import com.team.shop.exception.StateConflictException;
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
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import jakarta.persistence.Version;

import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;

/**
 * 拍卖场次，与 AUCTION 商品一对一。只记录有效出价后的当前价与领先者；
 * 结拍成功时挂接一条既有交易中意向，履约终态沿用意向的 SUCCESS/FAILED。
 */
@Entity
@Table(name = "auction_session", uniqueConstraints = {
        @UniqueConstraint(name = "uk_auction_product", columnNames = "product_id"),
        @UniqueConstraint(name = "uk_auction_winner_intent", columnNames = "winner_intent_id")})
public class AuctionSession {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false, updatable = false)
    private Product product;

    @Column(name = "start_price", nullable = false, updatable = false, precision = 10, scale = 2)
    private BigDecimal startPrice;

    @Column(name = "min_increment", nullable = false, updatable = false, precision = 10, scale = 2)
    private BigDecimal minIncrement;

    @Column(name = "current_price", precision = 10, scale = 2)
    private BigDecimal currentPrice;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "leader_customer_id")
    private Customer leader;

    @Column(name = "bid_count", nullable = false)
    private int bidCount;

    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR)
    @Column(nullable = false, length = 20)
    private AuctionStatus status;

    @Column(name = "starts_at", nullable = false, updatable = false)
    private LocalDateTime startsAt;

    @Column(name = "ends_at", nullable = false, updatable = false)
    private LocalDateTime endsAt;

    @Column(name = "settled_at")
    private LocalDateTime settledAt;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "winner_intent_id")
    private PurchaseIntent winnerIntent;

    @Version
    @Column(nullable = false)
    private long version;

    protected AuctionSession() {
    }

    /** Open a live session for a newly published auction product. */
    public static AuctionSession open(Product product, BigDecimal startPrice, BigDecimal minIncrement,
                                      LocalDateTime startsAt, LocalDateTime endsAt) {
        if (!product.isAuction()) {
            throw new IllegalArgumentException("只有拍卖商品可以创建拍卖场次");
        }
        BigDecimal start = money(startPrice);
        BigDecimal increment = money(minIncrement);
        if (start.signum() <= 0 || increment.signum() <= 0) {
            throw new IllegalArgumentException("起拍价和最小加价必须大于 0");
        }
        if (!endsAt.isAfter(startsAt)) {
            throw new IllegalArgumentException("截止时间必须晚于开始时间");
        }
        AuctionSession a = new AuctionSession();
        a.product = product;
        a.startPrice = start;
        a.minIncrement = increment;
        a.status = AuctionStatus.LIVE;
        a.startsAt = startsAt;
        a.endsAt = endsAt;
        return a;
    }

    /** 无有效出价时为起拍价，否则为当前价 + 最小加价。 */
    public BigDecimal nextMinimumBid() {
        return bidCount == 0 ? startPrice : currentPrice.add(minIncrement);
    }

    /** 截止时刻本身已不可出价。 */
    public boolean isOpenAt(LocalDateTime now) {
        return status == AuctionStatus.LIVE && now.isBefore(endsAt);
    }

    public boolean isDueAt(LocalDateTime now) {
        return status == AuctionStatus.LIVE && !now.isBefore(endsAt);
    }

    /** Record one valid bid; callers must hold the session row lock. Invalid bids change nothing. */
    public AuctionBid acceptBid(Customer bidder, BigDecimal amount, LocalDateTime now) {
        if (!isOpenAt(now)) {
            throw new StateConflictException("拍卖已截止或已结拍", 40906);
        }
        BigDecimal bid = money(amount);
        if (bid.compareTo(nextMinimumBid()) < 0) {
            throw new StateConflictException("出价低于当前最低可出价 " + nextMinimumBid().toPlainString(), 40907);
        }
        bidCount++;
        currentPrice = bid;
        leader = bidder;
        return new AuctionBid(this, bidCount, bidder, bid, now);
    }

    /** Settle with the current leader; the winner intent must already be IN_TRANSACTION. */
    public void markSold(PurchaseIntent intent, LocalDateTime now) {
        assertDue(now);
        if (bidCount == 0) {
            throw new StateConflictException("无人出价的拍卖只能流拍");
        }
        status = AuctionStatus.ENDED_SOLD;
        settledAt = now;
        winnerIntent = intent;
    }

    public void markUnsold(LocalDateTime now) {
        assertDue(now);
        if (bidCount > 0) {
            throw new StateConflictException("已有出价的拍卖必须由领先者中标");
        }
        status = AuctionStatus.ENDED_UNSOLD;
        settledAt = now;
    }

    private void assertDue(LocalDateTime now) {
        if (status != AuctionStatus.LIVE) {
            throw new StateConflictException("拍卖已结拍");
        }
        if (now.isBefore(endsAt)) {
            throw new StateConflictException("拍卖尚未到截止时间");
        }
    }

    private static BigDecimal money(BigDecimal value) {
        if (value == null || value.signum() <= 0 || value.compareTo(new BigDecimal("99999999.99")) > 0) {
            throw new IllegalArgumentException("金额必须在 0.01 至 99999999.99 之间");
        }
        try {
            return value.setScale(2, RoundingMode.UNNECESSARY);
        } catch (ArithmeticException e) {
            throw new IllegalArgumentException("金额最多保留两位小数", e);
        }
    }

    public Long getId() { return id; }
    public Product getProduct() { return product; }
    public BigDecimal getStartPrice() { return startPrice; }
    public BigDecimal getMinIncrement() { return minIncrement; }
    public BigDecimal getCurrentPrice() { return currentPrice; }
    public Customer getLeader() { return leader; }
    public int getBidCount() { return bidCount; }
    public AuctionStatus getStatus() { return status; }
    public LocalDateTime getStartsAt() { return startsAt; }
    public LocalDateTime getEndsAt() { return endsAt; }
    public LocalDateTime getSettledAt() { return settledAt; }
    public PurchaseIntent getWinnerIntent() { return winnerIntent; }
    public long getVersion() { return version; }
}
