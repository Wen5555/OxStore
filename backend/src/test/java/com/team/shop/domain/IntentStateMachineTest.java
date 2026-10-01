package com.team.shop.domain;

import com.team.shop.exception.StateConflictException;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

/**
 * 意向状态机单测：覆盖全部合法迁移与非法迁移。
 */
class IntentStateMachineTest {

    // ---------- 撤销 ----------

    @Test
    void cancel_allowedFromQueuing() {
        assertDoesNotThrow(() -> IntentStateMachine.assertCanCancel(IntentStatus.QUEUING));
    }

    @Test
    void cancel_rejectedFromOtherStatuses() {
        for (IntentStatus s : IntentStatus.values()) {
            if (s == IntentStatus.QUEUING) {
                continue;
            }
            assertThrows(StateConflictException.class, () -> IntentStateMachine.assertCanCancel(s));
        }
    }

    // ---------- 修改信息 ----------

    @Test
    void modify_allowedFromQueuing() {
        assertDoesNotThrow(() -> IntentStateMachine.assertCanModify(IntentStatus.QUEUING));
    }

    @Test
    void modify_rejectedFromOtherStatuses() {
        for (IntentStatus s : IntentStatus.values()) {
            if (s == IntentStatus.QUEUING) {
                continue;
            }
            assertThrows(StateConflictException.class, () -> IntentStateMachine.assertCanModify(s));
        }
    }

    // ---------- 进入交易 ----------

    @Test
    void enterTrade_allowedFromQueuing() {
        assertDoesNotThrow(() -> IntentStateMachine.assertCanEnterTrade(IntentStatus.QUEUING));
    }

    @Test
    void enterTrade_rejectedFromOtherStatuses() {
        for (IntentStatus s : IntentStatus.values()) {
            if (s == IntentStatus.QUEUING) {
                continue;
            }
            assertThrows(StateConflictException.class, () -> IntentStateMachine.assertCanEnterTrade(s));
        }
    }

    // ---------- 确认成功 ----------

    @Test
    void markSuccess_allowedFromInTransaction() {
        assertDoesNotThrow(() -> IntentStateMachine.assertCanMarkSuccess(IntentStatus.IN_TRANSACTION));
    }

    @Test
    void markSuccess_rejectedFromOtherStatuses() {
        for (IntentStatus s : IntentStatus.values()) {
            if (s == IntentStatus.IN_TRANSACTION) {
                continue;
            }
            assertThrows(StateConflictException.class, () -> IntentStateMachine.assertCanMarkSuccess(s));
        }
    }

    // ---------- 确认失败 ----------

    @Test
    void markFailed_allowedFromInTransaction() {
        assertDoesNotThrow(() -> IntentStateMachine.assertCanMarkFailed(IntentStatus.IN_TRANSACTION));
    }

    @Test
    void markFailed_rejectedFromOtherStatuses() {
        for (IntentStatus s : IntentStatus.values()) {
            if (s == IntentStatus.IN_TRANSACTION) {
                continue;
            }
            assertThrows(StateConflictException.class, () -> IntentStateMachine.assertCanMarkFailed(s));
        }
    }
}
