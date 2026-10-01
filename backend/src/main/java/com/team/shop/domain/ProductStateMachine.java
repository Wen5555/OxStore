package com.team.shop.domain;

import com.team.shop.exception.StateConflictException;

/**
 * 商品状态机：唯一权威的状态迁移校验。任何商品状态变更必须经过本类校验。
 * 跨实体约束（无交易中意向、队列非空等）在服务层校验，本类只做状态级校验。
 */
public final class ProductStateMachine {

    private ProductStateMachine() {
    }

    /** 手动冻结：仅 ONLINE / RESTORED_ONLINE 可冻结 */
    public static void assertCanFreezeManually(ProductStatus status) {
        if (status != ProductStatus.ONLINE && status != ProductStatus.RESTORED_ONLINE) {
            throw new StateConflictException("仅处于在售状态的商品可以手动冻结");
        }
    }

    /** 手动解冻：仅 FROZEN(手动) 可解冻，交易中禁止解冻 */
    public static void assertCanUnfreezeManually(ProductStatus status, FreezeSource source) {
        if (status != ProductStatus.FROZEN || source != FreezeSource.MANUAL) {
            throw new StateConflictException("仅卖家手动冻结的商品可以解冻，交易中须先标记交易结果");
        }
    }

    /** 开始交易：仅 ONLINE / RESTORED_ONLINE 可进入交易 */
    public static void assertCanStartTrade(ProductStatus status) {
        if (status != ProductStatus.ONLINE && status != ProductStatus.RESTORED_ONLINE) {
            throw new StateConflictException("商品当前状态不可开始交易");
        }
    }

    /** 确认交易成功：仅 FROZEN(交易) 可确认成功 */
    public static void assertCanMarkSuccess(ProductStatus status, FreezeSource source) {
        if (status != ProductStatus.FROZEN || source != FreezeSource.TRADE) {
            throw new StateConflictException("仅交易中的商品可以确认交易成功");
        }
    }

    /** 确认交易失败：仅 FROZEN(交易) 可确认失败 */
    public static void assertCanMarkFailed(ProductStatus status, FreezeSource source) {
        if (status != ProductStatus.FROZEN || source != FreezeSource.TRADE) {
            throw new StateConflictException("仅交易中的商品可以确认交易失败");
        }
    }

    /** 是否为可接收购买意向的状态 */
    public static boolean isAcceptingIntent(ProductStatus status) {
        return status == ProductStatus.ONLINE || status == ProductStatus.RESTORED_ONLINE;
    }
}
