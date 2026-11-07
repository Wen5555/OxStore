package com.team.shop.domain;

/**
 * 商品售卖模式，发布后不可切换。
 */
public enum SellingMode {
    /** 普通在售：一口价 + 意向队列 */
    FIXED_PRICE,
    /** 拍卖：英式增价，库存固定为 1 */
    AUCTION
}
