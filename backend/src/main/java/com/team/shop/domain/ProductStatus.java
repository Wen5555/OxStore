package com.team.shop.domain;

/**
 * 商品状态。唯一权威定义见《需求规格说明书V1.0》4.4 节。
 */
public enum ProductStatus {
    /** 在售：发布后的初始状态，可接收购买意向 */
    ONLINE,
    /** 已恢复在售：交易失败后恢复，功能等同于在售 */
    RESTORED_ONLINE,
    /** 冻结：不可接收新意向，来源见 FreezeSource */
    FROZEN,
    /** 已下架/交易成功：进入历史 */
    SOLD
}
