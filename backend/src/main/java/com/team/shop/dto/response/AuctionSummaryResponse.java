package com.team.shop.dto.response;

import com.team.shop.domain.AuctionStatus;
import com.team.shop.entity.AuctionSession;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record AuctionSummaryResponse(AuctionStatus auctionStatus, BigDecimal currentPrice,
                                     BigDecimal nextMinBid, LocalDateTime endsAt, int bidCount) {
    public static AuctionSummaryResponse from(AuctionSession auction) {
        return new AuctionSummaryResponse(auction.getStatus(), auction.getCurrentPrice(),
                auction.nextMinimumBid(), auction.getEndsAt(), auction.getBidCount());
    }
}
