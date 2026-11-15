package com.team.shop.domain;

/**
 * 挑战 B 整单履约状态，独立于旧 IntentStatus（不复用 FAILED）。合法流转由订单状态机判定（B-013）。
 */
public enum OrderStatus {
    /** 客户下单 */
    PLACED,
    /** 商家确认 */
    CONFIRMED,
    /** 备货完成 */
    PREPARED,
    /** 开始发货 */
    SHIPPED,
    /** 交易完成（终态） */
    COMPLETED,
    /** 已取消（终态） */
    CANCELLED
}
