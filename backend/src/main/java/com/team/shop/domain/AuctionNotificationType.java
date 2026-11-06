package com.team.shop.domain;

/**
 * 结拍站内提醒类型；类型决定收件人，同一场次每种类型至多一条。
 */
public enum AuctionNotificationType {
    /** 通知卖家：已成交 */
    AUCTION_SOLD,
    /** 通知卖家：流拍 */
    AUCTION_UNSOLD,
    /** 通知中标顾客 */
    AUCTION_WON;

    public NotificationRecipientRole recipientRole() {
        return this == AUCTION_WON ? NotificationRecipientRole.CUSTOMER : NotificationRecipientRole.SELLER;
    }
}
