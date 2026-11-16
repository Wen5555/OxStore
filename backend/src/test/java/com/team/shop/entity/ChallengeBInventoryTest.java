package com.team.shop.entity;

import com.team.shop.domain.OfflineReason;
import com.team.shop.domain.ProductStatus;
import com.team.shop.exception.BizException;
import com.team.shop.exception.StateConflictException;
import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.time.LocalDateTime;
import static org.junit.jupiter.api.Assertions.*;

class ChallengeBInventoryTest {
    private final Category category = new Category("test", null);
    private final LocalDateTime now = LocalDateTime.now();
    private Product product(int stock) { return Product.create("item", "", BigDecimal.ONE, stock, category); }

    @Test void hugeStockAndSmallSnapshotsRemainExact() {
        BigInteger huge = new BigInteger("900719925474099312345678901234567890");
        Product p = Product.create("huge", "", BigDecimal.ONE, huge, category);
        p.deductForOrder(BigInteger.valueOf(3), now);
        assertEquals(huge.subtract(BigInteger.valueOf(3)), p.getStock());
        p.updateInventoryAndCategory(BigInteger.valueOf(7), category, now);
        p.restoreForCancelledOrder(BigInteger.valueOf(3), now);
        assertEquals(BigInteger.TEN, p.getStock());
    }

    @Test void onlyCancellationRestoresAnAutomaticallyOfflineProduct() {
        Product p = product(2);
        p.deductForOrder(BigInteger.TWO, now);
        assertEquals(ProductStatus.OFFLINE, p.getStatus());
        assertEquals(OfflineReason.AUTO_ZERO, p.getOfflineReason());
        p.restoreForCancelledOrder(BigInteger.TWO, now);
        assertEquals(ProductStatus.ONLINE, p.getStatus());
        assertNull(p.getOfflineReason());
        p.updateInventoryAndCategory(BigInteger.ZERO, category, now);
        p.updateInventoryAndCategory(BigInteger.valueOf(4), category, now);
        assertEquals(ProductStatus.OFFLINE, p.getStatus());
        p.putOnline(now);
        assertEquals(ProductStatus.ONLINE, p.getStatus());
        assertNull(p.getOfflineReason());
    }

    @Test void explicitManualOfflineWinsOverAutomaticRecoveryIncludingZeroStock() {
        Product p = product(2);
        p.deductForOrder(BigInteger.TWO, now);
        p.takeOffline(now); // Explicitly stay offline, even if already automatically offline.
        p.restoreForCancelledOrder(BigInteger.TWO, now);
        assertEquals(OfflineReason.MANUAL, p.getOfflineReason());
        assertEquals(ProductStatus.OFFLINE, p.getStatus());
        p.updateInventoryAndCategory(BigInteger.ZERO, category, now);
        p.restoreForCancelledOrder(BigInteger.ONE, now);
        assertEquals(ProductStatus.OFFLINE, p.getStatus());
    }

    @Test void rejectedChangesLeaveStockAndStatusUntouched() {
        Product p = product(1);
        assertThrows(StateConflictException.class, () -> p.deductForOrder(BigInteger.TWO, now));
        assertThrows(BizException.class, () -> p.deductForOrder(BigInteger.ZERO, now));
        assertThrows(BizException.class, () -> p.updateInventoryAndCategory(BigInteger.valueOf(-1), category, now));
        assertEquals(BigInteger.ONE, p.getStock());
        assertEquals(ProductStatus.ONLINE, p.getStatus());
        Product empty = product(0);
        assertEquals(OfflineReason.AUTO_ZERO, empty.getOfflineReason());
        assertThrows(StateConflictException.class, () -> empty.putOnline(now));
    }

    @Test void auctionFulfilmentRemainsSeparateFromNewOrderInventory() {
        Product p = Product.createAuction("auction", "", BigDecimal.ONE, category);
        assertThrows(StateConflictException.class, () -> p.deductForOrder(BigInteger.ONE, now));
        assertThrows(StateConflictException.class, () -> p.restoreForCancelledOrder(BigInteger.ONE, now));
        p.startTrade(now);
        assertTrue(p.markTradeSucceeded(now));
        assertEquals(BigInteger.ZERO, p.getStock());
        assertEquals(OfflineReason.AUTO_ZERO, p.getOfflineReason());
    }
}
