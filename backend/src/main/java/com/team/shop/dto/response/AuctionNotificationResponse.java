package com.team.shop.dto.response;

import com.team.shop.domain.AuctionNotificationType;
import com.team.shop.entity.AuctionNotification;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record AuctionNotificationResponse(Long notificationId, Long auctionId, Long productId,
                                          AuctionNotificationType type, String productName,
                                          BigDecimal finalPrice, LocalDateTime createdAt,
                                          LocalDateTime readAt) {
    public static AuctionNotificationResponse from(AuctionNotification n) {
        return new AuctionNotificationResponse(n.getId(), n.getAuction().getId(),
                n.getAuction().getProduct().getId(), n.getType(), n.getProductNameSnapshot(),
                n.getFinalPrice(), n.getCreatedAt(), n.getReadAt());
    }
}
