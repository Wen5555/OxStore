package com.team.shop.dto.request;

/**
 * 交易失败处理方式。
 */
public enum FailAction {
    /** 重新排队：该意向回到队尾，原口令继续有效 */
    REQUEUE,
    /** 作废：该意向直接标记失败 */
    DISCARD
}
