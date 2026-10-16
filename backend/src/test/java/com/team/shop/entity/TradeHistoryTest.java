package com.team.shop.entity;
import com.team.shop.dto.request.FailAction;
import com.team.shop.domain.*;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import static org.junit.jupiter.api.Assertions.*;
class TradeHistoryTest {
    @Test void requeuePreservesFirstSubmissionAndOriginalToken() {
        Product p = Product.create("测试", "说明", "/img", BigDecimal.ONE);
        PurchaseIntent i = PurchaseIntent.submit(p, "买家", "00000000000", "old-hash", "lookup", 1);
        LocalDateTime first = i.getSubmittedAt(), now = first.plusSeconds(2);
        i.enterTrade(first.plusSeconds(1));
        i.requeue(3, now);
        assertEquals(first, i.getSubmittedAt());
        assertEquals(3, i.getQueueSeq());
        assertEquals(now, i.getProcessedAt());
        assertEquals("old-hash", i.getTokenHash());
        assertEquals("lookup", i.getTokenLookup());
        assertEquals(IntentStatus.QUEUING, i.getStatus());
    }
    @Test void attemptsCannotOverwriteCompletedResult() {
        Product p = Product.create("测试", "说明", "/img", BigDecimal.ONE);
        PurchaseIntent i = PurchaseIntent.submit(p,"买家","00000000000","hash","lookup",1);
        var a = new TradeAttempt(i, BusinessTime.now());
        assertNull(a.getFinishedAt());
        a.fail(FailAction.REQUEUE, BusinessTime.now());
        assertEquals(TradeResult.FAILED, a.getResult());
        assertThrows(IllegalStateException.class, () -> a.succeed(BusinessTime.now()));
    }

    @Test void finalIntentStatesInvalidateBothTokenFields() {
        Product p = Product.create("测试", "说明", "/img", BigDecimal.ONE);
        for (IntentStatus terminal : new IntentStatus[] {
                IntentStatus.CANCELLED, IntentStatus.FAILED, IntentStatus.SUCCESS, IntentStatus.UNSOLD}) {
            PurchaseIntent i = PurchaseIntent.submit(p, "买家", "00000000000", "hash", "lookup", 1);
            LocalDateTime now = i.getSubmittedAt().plusSeconds(1);
            if (terminal == IntentStatus.CANCELLED) i.cancel(now);
            else if (terminal == IntentStatus.UNSOLD) i.markUnsold(now);
            else {
                i.enterTrade(now);
                if (terminal == IntentStatus.FAILED) i.markFailed(now.plusSeconds(1));
                else i.markSuccess(now.plusSeconds(1));
            }
            assertEquals(terminal, i.getStatus());
            assertNull(i.getTokenHash(), terminal.name());
            assertNull(i.getTokenLookup(), terminal.name());
        }
    }
}
