package com.team.shop.domain;

import com.team.shop.entity.Category;
import com.team.shop.entity.Product;
import com.team.shop.exception.StateConflictException;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ProductStateMachineTest {
    @Test
    void onlyOnlineProductsAcceptIntentsAndStartTrades() {
        assertTrue(ProductStateMachine.isAcceptingIntent(ProductStatus.ONLINE));
        assertFalse(ProductStateMachine.isAcceptingIntent(ProductStatus.FROZEN));
        assertFalse(ProductStateMachine.isAcceptingIntent(ProductStatus.OFFLINE));
        assertDoesNotThrow(() -> ProductStateMachine.assertCanStartTrade(ProductStatus.ONLINE));
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanStartTrade(ProductStatus.FROZEN));
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanStartTrade(ProductStatus.OFFLINE));
    }

    @Test
    void tradeResultsRequireTradeFreeze() {
        assertDoesNotThrow(() ->
                ProductStateMachine.assertCanMarkSuccess(ProductStatus.FROZEN, FreezeSource.TRADE));
        assertDoesNotThrow(() ->
                ProductStateMachine.assertCanMarkFailed(ProductStatus.FROZEN, FreezeSource.TRADE));
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanMarkSuccess(ProductStatus.FROZEN, FreezeSource.MANUAL));
        assertThrows(StateConflictException.class,
                () -> ProductStateMachine.assertCanMarkFailed(ProductStatus.ONLINE, null));
    }

    @Test
    void refillingAnOfflineProductDoesNotAutomaticallyPublishIt() {
        LocalDateTime now = LocalDateTime.now();
        Category category = new Category("其他", null);
        Product product = Product.create("商品", "", BigDecimal.ONE, 1, category);

        product.takeOffline(now);
        product.updateInventoryAndCategory(0, category, now);
        product.updateInventoryAndCategory(2, category, now);

        assertEquals(ProductStatus.OFFLINE, product.getStatus());
        product.putOnline(now);
        assertEquals(ProductStatus.ONLINE, product.getStatus());
    }
}
