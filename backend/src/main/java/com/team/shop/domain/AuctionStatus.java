package com.team.shop.domain;

/**
 * 拍卖场次状态。履约终态仍复用意向的 SUCCESS/FAILED。
 */
public enum AuctionStatus {
    /** 竞拍中，发布即开始 */
    LIVE,
    /** 已结拍且有中标人，已挂接交易中意向 */
    ENDED_SOLD,
    /** 已结拍且无人出价（流拍） */
    ENDED_UNSOLD
}
