package com.team.shop.dto.response;

import java.util.List;

/** 分页提醒及当前收件人的未读数量。 */
public record AuctionNotificationPageResponse(
        List<AuctionNotificationResponse> items,
        int page,
        int size,
        long total,
        int pages,
        long unread) {
}
