package com.team.shop.domain;

import com.team.shop.exception.StateConflictException;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 商品状态机单测：覆盖全部合法迁移与非法迁移。
 */
class ProductStateMachineTest {

    // ---------- 手动冻结 ----------

    @Test
    void freezeManually_allowedFromOnline() {
        assertDoesNotThrow(() -> ProductStateMachine.assertCanFreezeManually(ProductStatus.ONLINE));
    }

    @Test
    void freezeManually_allowedFromRestoredOnline() {
        assertDoesNotThrow(() -> ProductStateMachine.assertCanFreezeManually(ProductStatus.RESTORED_ONLINE));
    }

    @Test
    void freezeManually_rejectedFromFrozen() {
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanFreezeManually(ProductStatus.FROZEN));
    }

    @Test
    void freezeManually_rejectedFromSold() {
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanFreezeManually(ProductStatus.SOLD));
    }

    // ---------- 手动解冻 ----------

    @Test
    void unfreezeManually_allowedFromFrozenManual() {
        assertDoesNotThrow(() -> ProductStateMachine.assertCanUnfreezeManually(ProductStatus.FROZEN, FreezeSource.MANUAL));
    }

    @Test
    void unfreezeManually_rejectedFromFrozenTrade() {
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanUnfreezeManually(ProductStatus.FROZEN, FreezeSource.TRADE));
    }

    @Test
    void unfreezeManually_rejectedFromOnline() {
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanUnfreezeManually(ProductStatus.ONLINE, null));
    }

    @Test
    void unfreezeManually_rejectedFromSold() {
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanUnfreezeManually(ProductStatus.SOLD, null));
    }

    // ---------- 开始交易 ----------

    @Test
    void startTrade_allowedFromOnline() {
        assertDoesNotThrow(() -> ProductStateMachine.assertCanStartTrade(ProductStatus.ONLINE));
    }

    @Test
    void startTrade_allowedFromRestoredOnline() {
        assertDoesNotThrow(() -> ProductStateMachine.assertCanStartTrade(ProductStatus.RESTORED_ONLINE));
    }

    @Test
    void startTrade_rejectedFromFrozen() {
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanStartTrade(ProductStatus.FROZEN));
    }

    @Test
    void startTrade_rejectedFromSold() {
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanStartTrade(ProductStatus.SOLD));
    }

    // ---------- 确认交易成功 ----------

    @Test
    void markSuccess_allowedFromFrozenTrade() {
        assertDoesNotThrow(() -> ProductStateMachine.assertCanMarkSuccess(ProductStatus.FROZEN, FreezeSource.TRADE));
    }

    @Test
    void markSuccess_rejectedFromFrozenManual() {
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanMarkSuccess(ProductStatus.FROZEN, FreezeSource.MANUAL));
    }

    @Test
    void markSuccess_rejectedFromOnline() {
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanMarkSuccess(ProductStatus.ONLINE, null));
    }

    // ---------- 确认交易失败 ----------

    @Test
    void markFailed_allowedFromFrozenTrade() {
        assertDoesNotThrow(() -> ProductStateMachine.assertCanMarkFailed(ProductStatus.FROZEN, FreezeSource.TRADE));
    }

    @Test
    void markFailed_rejectedFromFrozenManual() {
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanMarkFailed(ProductStatus.FROZEN, FreezeSource.MANUAL));
    }

    @Test
    void markFailed_rejectedFromOnline() {
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanMarkFailed(ProductStatus.ONLINE, null));
    }

    // ---------- 是否可接收意向 ----------

    @Test
    void isAcceptingIntent_trueForOnlineAndRestoredOnline() {
        assertTrue(ProductStateMachine.isAcceptingIntent(ProductStatus.ONLINE));
        assertTrue(ProductStateMachine.isAcceptingIntent(ProductStatus.RESTORED_ONLINE));
    }

    @Test
    void isAcceptingIntent_falseForFrozenAndSold() {
        assertFalse(ProductStateMachine.isAcceptingIntent(ProductStatus.FROZEN));
        assertFalse(ProductStateMachine.isAcceptingIntent(ProductStatus.SOLD));
    }
}
