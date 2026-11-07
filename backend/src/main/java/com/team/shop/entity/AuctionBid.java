package com.team.shop.entity;

import jakarta.persistence.Column;
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
import java.time.LocalDateTime;

/**
 * 一次有效出价，只能由 AuctionSession.acceptBid 生成；无效出价不落库。
 * bidSeq 与金额在场次内唯一，并发重复接受同一序号或同一金额会被数据库拒绝。
 */
@Entity
@Table(name = "auction_bid", uniqueConstraints = {
        @UniqueConstraint(name = "uk_bid_auction_seq", columnNames = {"auction_id", "bid_seq"}),
        @UniqueConstraint(name = "uk_bid_auction_amount", columnNames = {"auction_id", "amount"})})
public class AuctionBid {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "auction_id", nullable = false, updatable = false)
    private AuctionSession auction;

    @Column(name = "bid_seq", nullable = false, updatable = false)
    private int bidSeq;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "customer_id", nullable = false, updatable = false)
    private Customer customer;

    @Column(nullable = false, updatable = false, precision = 10, scale = 2)
    private BigDecimal amount;

    @Column(name = "bid_at", nullable = false, updatable = false)
    private LocalDateTime bidAt;

    protected AuctionBid() {
    }

    AuctionBid(AuctionSession auction, int bidSeq, Customer customer, BigDecimal amount, LocalDateTime bidAt) {
        this.auction = auction;
        this.bidSeq = bidSeq;
        this.customer = customer;
        this.amount = amount;
        this.bidAt = bidAt;
    }

    public Long getId() { return id; }
    public AuctionSession getAuction() { return auction; }
    public int getBidSeq() { return bidSeq; }
    public Customer getCustomer() { return customer; }
    public BigDecimal getAmount() { return amount; }
    public LocalDateTime getBidAt() { return bidAt; }
}
