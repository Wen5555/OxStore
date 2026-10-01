package com.team.shop.domain;

/**
 * 购买意向状态。
 */
public enum IntentStatus {
    /** 排队中 */
    QUEUING,
    /** 交易中 */
    IN_TRANSACTION,
    /** 交易成功 */
    SUCCESS,
    /** 交易失败（被作废） */
    FAILED,
    /** 已撤销（买家主动退出） */
    CANCELLED,
    /** 未成交（商品已售出给他人） */
    UNSOLD
}
