package com.team.shop.domain;

import com.team.shop.exception.StateConflictException;

/**
 * 商品状态机：唯一权威的状态迁移校验。任何商品状态变更必须经过本类校验。
 * 跨实体约束（无交易中意向、队列非空等）在服务层校验，本类只做状态级校验。
 */
public final class ProductStateMachine {

    private ProductStateMachine() {
    }

    /** 开始交易：仅在售商品可进入交易 */
    public static void assertCanStartTrade(ProductStatus status) {
        if (status != ProductStatus.ONLINE) {
            throw new StateConflictException("商品当前状态不可开始交易");
        }
    }

    /** 确认交易成功：仅交易中的商品可确认成功 */
    public static void assertCanMarkSuccess(ProductStatus status, FreezeSource source) {
        if (status != ProductStatus.FROZEN || source != FreezeSource.TRADE) {
            throw new StateConflictException("仅交易中的商品可以确认交易成功");
        }
    }

    /** 确认交易失败：仅交易中的商品可确认失败 */
    public static void assertCanMarkFailed(ProductStatus status, FreezeSource source) {
        if (status != ProductStatus.FROZEN || source != FreezeSource.TRADE) {
            throw new StateConflictException("仅交易中的商品可以确认交易失败");
        }
    }

    /** 是否为可接收购买意向的状态 */
    public static boolean isAcceptingIntent(ProductStatus status) {
        return status == ProductStatus.ONLINE;
    }
}
