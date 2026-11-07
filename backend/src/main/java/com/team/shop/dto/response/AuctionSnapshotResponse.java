package com.team.shop.dto.response;

import com.team.shop.domain.AuctionStatus;
import com.team.shop.domain.SellingMode;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

public record AuctionSnapshotResponse(Long productId, String productName, SellingMode sellingMode,
                                     AuctionStatus auctionStatus, BigDecimal startPrice,
                                     BigDecimal minIncrement, BigDecimal currentPrice,
                                     BigDecimal nextMinBid, int bidCount, LocalDateTime endsAt,
                                     LocalDateTime settledAt, LocalDateTime serverTime,
                                     String leaderAlias, int lastBidSeq, List<RecentBid> recentBids,
                                     boolean canBid, String myStatus) {
    public record RecentBid(int bidSeq, BigDecimal amount, String bidderAlias, LocalDateTime bidAt) {}
}
