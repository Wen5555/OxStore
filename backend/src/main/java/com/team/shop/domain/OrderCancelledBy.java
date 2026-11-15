package com.team.shop.domain;

/** 订单取消发起方；仅 CANCELLED 订单有值。 */
public enum OrderCancelledBy {
    CUSTOMER,
    SELLER
}
