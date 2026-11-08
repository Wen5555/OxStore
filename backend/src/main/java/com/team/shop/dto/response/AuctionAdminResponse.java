package com.team.shop.dto.response;

import com.team.shop.domain.AuctionStatus;
import com.team.shop.entity.AuctionSession;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/** 卖家后台的拍卖管理摘要，不暴露公开接口不应返回的买家明细。 */
public record AuctionAdminResponse(
        Long productId,
        String productName,
        AuctionStatus auctionStatus,
        BigDecimal startPrice,
        BigDecimal currentPrice,
        int bidCount,
        LocalDateTime endsAt,
        LocalDateTime settledAt,
        String winnerAlias,
        Long winnerIntentId) {

    public static AuctionAdminResponse from(AuctionSession auction) {
        return new AuctionAdminResponse(
                auction.getProduct().getId(),
                auction.getProduct().getName(),
                auction.getStatus(),
                auction.getStartPrice(),
                auction.getCurrentPrice(),
                auction.getBidCount(),
                auction.getEndsAt(),
                auction.getSettledAt(),
                auction.getLeader() == null ? null : alias(auction.getLeader().getUsername()),
                auction.getWinnerIntent() == null ? null : auction.getWinnerIntent().getId());
    }

    private static String alias(String username) {
        if (username == null || username.length() <= 1) return "*";
        return username.charAt(0) + "***" + username.charAt(username.length() - 1);
    }
}
