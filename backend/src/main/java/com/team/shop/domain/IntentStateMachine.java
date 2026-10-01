package com.team.shop.domain;

import com.team.shop.exception.StateConflictException;

/**
 * 意向状态机：唯一权威的意向状态迁移校验。
 * 队首判定等跨记录约束在服务层校验，本类只做状态级校验。
 */
public final class IntentStateMachine {

    private IntentStateMachine() {
    }

    /** 买家撤销：仅排队中可撤销 */
    public static void assertCanCancel(IntentStatus status) {
        if (status != IntentStatus.QUEUING) {
            throw new StateConflictException("仅排队中的意向可以撤销");
        }
    }

    /** 买家修改信息：仅排队中可修改 */
    public static void assertCanModify(IntentStatus status) {
        if (status != IntentStatus.QUEUING) {
            throw new StateConflictException("仅排队中的意向可以修改信息");
        }
    }

    /** 进入交易：仅排队中可进入交易（是否队首由服务层判定） */
    public static void assertCanEnterTrade(IntentStatus status) {
        if (status != IntentStatus.QUEUING) {
            throw new StateConflictException("仅排队中的意向可以进入交易");
        }
    }

    /** 确认交易成功：仅交易中 */
    public static void assertCanMarkSuccess(IntentStatus status) {
        if (status != IntentStatus.IN_TRANSACTION) {
            throw new StateConflictException("仅交易中的意向可以确认成功");
        }
    }

    /** 确认交易失败：仅交易中 */
    public static void assertCanMarkFailed(IntentStatus status) {
        if (status != IntentStatus.IN_TRANSACTION) {
            throw new StateConflictException("仅交易中的意向可以确认失败");
        }
    }
}
