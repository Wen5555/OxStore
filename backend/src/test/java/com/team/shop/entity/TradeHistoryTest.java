package com.team.shop.entity;
import com.team.shop.dto.request.FailAction;
import com.team.shop.domain.*;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import static org.junit.jupiter.api.Assertions.*;
class TradeHistoryTest {
    @Test void requeuePreservesFirstSubmissionAndInvalidatesOldToken() {
        Product p = Product.create("测试", "说明", "/img", BigDecimal.ONE);
        PurchaseIntent i = PurchaseIntent.submit(p, "买家", "00000000000", "old-hash", "lookup", 1);
        LocalDateTime first = i.getSubmittedAt(), now = first.plusSeconds(2);
        i.enterTrade(first.plusSeconds(1));
        i.requeue(3, now);
        assertEquals(first, i.getSubmittedAt());
        assertEquals(3, i.getQueueSeq());
        assertEquals(now, i.getProcessedAt());
        assertNull(i.getTokenHash());
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
}
