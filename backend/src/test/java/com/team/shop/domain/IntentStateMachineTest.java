package com.team.shop.domain;

import com.team.shop.exception.StateConflictException;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

class IntentStateMachineTest {
    @Test
    void onlyQueuedIntentsCanStartAndOnlyTradingIntentsCanFinish() {
        assertDoesNotThrow(() -> IntentStateMachine.assertCanEnterTrade(IntentStatus.QUEUING));
        assertThrows(StateConflictException.class,
                () -> IntentStateMachine.assertCanEnterTrade(IntentStatus.IN_TRANSACTION));

        assertDoesNotThrow(() -> IntentStateMachine.assertCanMarkSuccess(IntentStatus.IN_TRANSACTION));
        assertDoesNotThrow(() -> IntentStateMachine.assertCanMarkFailed(IntentStatus.IN_TRANSACTION));
        assertThrows(StateConflictException.class,
                () -> IntentStateMachine.assertCanMarkFailed(IntentStatus.QUEUING));
    }
}
