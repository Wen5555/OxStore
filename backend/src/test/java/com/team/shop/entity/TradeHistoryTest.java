package com.team.shop.entity;

import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.IntentStatus;
import com.team.shop.domain.ProductStatus;
import com.team.shop.dto.request.FailAction;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

class TradeHistoryTest {
    private Category category() {
        return new Category("二级类目", new Category("一级类目", null));
    }

    private Customer customer() {
        return new Customer("buyer", "hash", "00000000000", null, BusinessTime.now());
    }

    @Test
    void requeuePreservesFirstSubmissionWithoutTokenState() {
        Product product = Product.create("测试", "", BigDecimal.ONE, 1, category());
        PurchaseIntent intent = PurchaseIntent.submit(product, customer(), 1);
        var firstSubmitted = intent.getSubmittedAt();
        var processedAt = firstSubmitted.plusSeconds(2);

        intent.enterTrade(firstSubmitted.plusSeconds(1));
        intent.requeue(3, processedAt);

        assertEquals(firstSubmitted, intent.getSubmittedAt());
        assertEquals(3, intent.getQueueSeq());
        assertEquals(processedAt, intent.getProcessedAt());
        assertEquals(IntentStatus.QUEUING, intent.getStatus());
    }

    @Test
    void attemptsCannotOverwriteCompletedResult() {
        Product product = Product.create("测试", "", BigDecimal.ONE, 1, category());
        PurchaseIntent intent = PurchaseIntent.submit(product, customer(), 1);
        TradeAttempt attempt = new TradeAttempt(intent, BusinessTime.now());

        assertNull(attempt.getFinishedAt());
        attempt.fail(FailAction.REQUEUE, BusinessTime.now());
        assertEquals(com.team.shop.domain.TradeResult.FAILED, attempt.getResult());
        assertThrows(IllegalStateException.class, () -> attempt.succeed(BusinessTime.now()));
    }

    @Test
    void inventoryDeterminesWhetherSuccessfulTradeLeavesItemOnline() {
        Product inStock = Product.create("测试", "", BigDecimal.ONE, 2, category());
        inStock.startTrade(BusinessTime.now());
        assertEquals(false, inStock.markTradeSucceeded(BusinessTime.now()));
        assertEquals(1, inStock.getStock());
        assertEquals(ProductStatus.ONLINE, inStock.getStatus());

        Product lastItem = Product.create("测试", "", BigDecimal.ONE, 1, category());
        lastItem.startTrade(BusinessTime.now());
        assertEquals(true, lastItem.markTradeSucceeded(BusinessTime.now()));
        assertEquals(0, lastItem.getStock());
        assertEquals(ProductStatus.OFFLINE, lastItem.getStatus());
    }
}
