package com.team.shop.dto.response;

import com.team.shop.entity.AuctionBid;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record AuctionBidResponse(Long bidId, Long auctionId, int bidSeq, BigDecimal amount,
                                 BigDecimal currentPrice, BigDecimal nextMinBid,
                                 int bidCount, LocalDateTime bidAt) {
    public static AuctionBidResponse from(AuctionBid bid) {
        var auction = bid.getAuction();
        return new AuctionBidResponse(bid.getId(), auction.getId(), bid.getBidSeq(), bid.getAmount(),
                auction.getCurrentPrice(), auction.nextMinimumBid(), auction.getBidCount(), bid.getBidAt());
    }
}
