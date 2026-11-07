package com.team.shop.service;

import com.team.shop.domain.AuctionStatus;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.SellingMode;
import com.team.shop.dto.response.AuctionBidResponse;
import com.team.shop.dto.response.AuctionSnapshotResponse;
import com.team.shop.entity.AuctionBid;
import com.team.shop.entity.AuctionSession;
import com.team.shop.entity.Customer;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.StateConflictException;
import com.team.shop.repository.AuctionBidRepository;
import com.team.shop.repository.AuctionSessionRepository;
import com.team.shop.repository.CustomerRepository;
import com.team.shop.repository.ProductRepository;
import com.team.shop.security.UserIdentity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;

@Service
public class AuctionServiceImpl implements AuctionService {
    private final ProductRepository products;
    private final AuctionSessionRepository auctions;
    private final AuctionBidRepository bids;
    private final CustomerRepository customers;
    private final AuctionEventHub events;

    public AuctionServiceImpl(ProductRepository products, AuctionSessionRepository auctions,
                               AuctionBidRepository bids, CustomerRepository customers,
                               AuctionEventHub events) {
        this.products = products;
        this.auctions = auctions;
        this.bids = bids;
        this.customers = customers;
        this.events = events;
    }

    @Override
    @Transactional(readOnly = true)
    public AuctionSnapshotResponse snapshot(Long productId, UserIdentity identity) {
        AuctionSession auction = auctions.findByProductId(productId)
                .orElseThrow(() -> new NotFoundException("拍卖不存在", 40401));
        Customer customer = customer(identity);
        return snapshotOf(auction, customer);
    }

    @Override
    @Transactional
    public AuctionBidResponse placeBid(Long productId, Long customerId, BigDecimal amount) {
        AuctionSession auction = auctions.findByProductIdForUpdate(productId)
                .orElseThrow(() -> new NotFoundException("拍卖不存在", 40401));
        if (auction.getProduct().getSellingMode() != SellingMode.AUCTION) {
            throw new StateConflictException("普通商品不能出价", 40908);
        }
        Customer customer = customers.findById(customerId)
                .orElseThrow(() -> new NotFoundException("顾客不存在", 40404));
        AuctionBid bid = auction.acceptBid(customer, amount, BusinessTime.now());
        bids.saveAndFlush(bid);
        AuctionBidResponse response = AuctionBidResponse.from(bid);
        events.publishBid(auction, bid);
        return response;
    }

    private Customer customer(UserIdentity identity) {
        if (identity == null || !"CUSTOMER".equals(identity.role())) {
            return null;
        }
        return customers.findById(identity.userId()).orElse(null);
    }

    private AuctionSnapshotResponse snapshotOf(AuctionSession auction, Customer customer) {
        List<AuctionSnapshotResponse.RecentBid> recent = bids.findTop10ByAuctionIdOrderByBidSeqDesc(auction.getId())
                .stream()
                .map(b -> new AuctionSnapshotResponse.RecentBid(b.getBidSeq(), b.getAmount(),
                        alias(b.getCustomer().getUsername()), b.getBidAt()))
                .toList();
        boolean customerCanBid = customer != null && auction.isOpenAt(BusinessTime.now());
        String myStatus = null;
        if (customer != null) {
            boolean participated = bids.existsByAuctionIdAndCustomerId(auction.getId(), customer.getId());
            if (auction.getStatus() == AuctionStatus.ENDED_SOLD && auction.getLeader() != null
                    && auction.getLeader().getId().equals(customer.getId())) {
                myStatus = "WON";
            } else if (auction.getStatus() == AuctionStatus.ENDED_SOLD && participated) {
                myStatus = "LOST";
            } else if (auction.getLeader() != null && auction.getLeader().getId().equals(customer.getId())) {
                myStatus = "LEADING";
            } else if (participated) {
                myStatus = "OUTBID";
            } else {
                myStatus = "NONE";
            }
        }
        return new AuctionSnapshotResponse(auction.getProduct().getId(), auction.getProduct().getName(),
                auction.getProduct().getSellingMode(), auction.getStatus(), auction.getStartPrice(),
                auction.getMinIncrement(), auction.getCurrentPrice(), auction.nextMinimumBid(),
                auction.getBidCount(), auction.getEndsAt(), auction.getSettledAt(), BusinessTime.now(),
                auction.getLeader() == null ? null : alias(auction.getLeader().getUsername()), auction.getBidCount(),
                recent, customerCanBid, myStatus);
    }

    private static String alias(String username) {
        if (username == null || username.length() <= 1) return "*";
        return username.charAt(0) + "***" + username.charAt(username.length() - 1);
    }
}
