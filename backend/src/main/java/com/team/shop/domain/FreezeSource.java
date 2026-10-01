package com.team.shop.domain;

/**
 * 商品冻结来源，仅当商品处于 FROZEN 时有意义。
 */
public enum FreezeSource {
    /** 卖家手动冻结（可手动解冻） */
    MANUAL,
    /** 因买家进入交易而冻结（须先标记交易结果，不可直接解冻） */
    TRADE
}
