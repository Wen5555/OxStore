package com.team.shop.entity;

import com.team.shop.domain.AuctionNotificationType;
import com.team.shop.domain.AuctionStatus;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.IntentStatus;
import com.team.shop.domain.NotificationRecipientRole;
import com.team.shop.domain.ProductStatus;
import com.team.shop.domain.SellingMode;
import com.team.shop.exception.StateConflictException;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AuctionSessionTest {
    private final LocalDateTime start = LocalDateTime.of(2026, 11, 6, 10, 0);
    private final LocalDateTime end = start.plusMinutes(2);

    private Category category() {
        return new Category("二级类目", new Category("一级类目", null));
    }

    private Customer customer(String name) {
        return new Customer(name, "hash", "13800000000", null, BusinessTime.now());
    }

    private AuctionSession session() {
        Product product = Product.createAuction("拍品", "", new BigDecimal("10.00"), category());
        return AuctionSession.open(product, new BigDecimal("10"), new BigDecimal("1.5"), start, end);
    }

    @Test
    void ordinaryProductsStayFixedPriceAndAuctionsHoldOneItem() {
        assertEquals(SellingMode.FIXED_PRICE, Product.create("普通", "", BigDecimal.ONE, 5, category()).getSellingMode());
        Product auction = Product.createAuction("拍品", "", new BigDecimal("10.00"), category());
        assertEquals(SellingMode.AUCTION, auction.getSellingMode());
        assertEquals(1, auction.getStock());
        assertEquals(ProductStatus.ONLINE, auction.getStatus());
        assertThrows(IllegalArgumentException.class, () -> AuctionSession.open(
                Product.create("普通", "", BigDecimal.ONE, 1, category()), BigDecimal.ONE, BigDecimal.ONE, start, end));
    }

    @Test
    void openRejectsInvalidParameters() {
        Product product = Product.createAuction("拍品", "", BigDecimal.TEN, category());
        assertThrows(IllegalArgumentException.class, () -> AuctionSession.open(product, BigDecimal.ZERO, BigDecimal.ONE, start, end));
        assertThrows(IllegalArgumentException.class, () -> AuctionSession.open(product, BigDecimal.ONE, new BigDecimal("-1"), start, end));
        assertThrows(IllegalArgumentException.class, () -> AuctionSession.open(product, new BigDecimal("1.001"), BigDecimal.ONE, start, end));
        assertThrows(IllegalArgumentException.class, () -> AuctionSession.open(product, BigDecimal.ONE, BigDecimal.ONE, start, start));
    }

    @Test
    void englishIncrementsUpdateLeaderAndSequence() {
        AuctionSession a = session();
        Customer first = customer("a");
        Customer second = customer("b");
        assertEquals(new BigDecimal("10.00"), a.nextMinimumBid());

        AuctionBid opening = a.acceptBid(first, new BigDecimal("10"), start.plusSeconds(1));
        assertEquals(1, opening.getBidSeq());
        assertEquals(new BigDecimal("11.50"), a.nextMinimumBid());

        StateConflictException low = assertThrows(StateConflictException.class,
                () -> a.acceptBid(second, new BigDecimal("11.49"), start.plusSeconds(2)));
        assertEquals(40907, low.getCode());
        assertEquals(1, a.getBidCount());
        assertSame(first, a.getLeader());

        AuctionBid raised = a.acceptBid(second, new BigDecimal("11.50"), start.plusSeconds(3));
        assertEquals(2, raised.getBidSeq());
        assertEquals(new BigDecimal("11.50"), a.getCurrentPrice());
        assertSame(second, a.getLeader());
    }

    @Test
    void bidsAtOrAfterTheDeadlineAreRejected() {
        AuctionSession a = session();
        StateConflictException closed = assertThrows(StateConflictException.class,
                () -> a.acceptBid(customer("a"), new BigDecimal("10"), end));
        assertEquals(40906, closed.getCode());
        assertEquals(0, a.getBidCount());
        assertNull(a.getCurrentPrice());
    }

    @Test
    void settlementHappensOnceAndMatchesBids() {
        AuctionSession unsold = session();
        assertThrows(StateConflictException.class, () -> unsold.markUnsold(end.minusNanos(1)));
        unsold.markUnsold(end);
        assertEquals(AuctionStatus.ENDED_UNSOLD, unsold.getStatus());
        assertThrows(StateConflictException.class, () -> unsold.markUnsold(end.plusSeconds(1)));

        AuctionSession sold = session();
        Customer winner = customer("winner");
        sold.acceptBid(winner, new BigDecimal("12"), start.plusSeconds(5));
        assertThrows(StateConflictException.class, () -> sold.markUnsold(end));
        PurchaseIntent intent = PurchaseIntent.submit(sold.getProduct(), winner, 1);
        intent.enterTrade(end);
        sold.markSold(intent, end);
        assertEquals(AuctionStatus.ENDED_SOLD, sold.getStatus());
        assertEquals(IntentStatus.IN_TRANSACTION, sold.getWinnerIntent().getStatus());
        assertThrows(StateConflictException.class, () -> sold.markSold(intent, end.plusSeconds(1)));
        assertTrue(!sold.isOpenAt(start.plusSeconds(10)));
    }

    @Test
    void notificationsFollowSettlementResult() {
        AuctionSession sold = session();
        Customer winner = customer("winner");
        sold.acceptBid(winner, new BigDecimal("12"), start.plusSeconds(5));
        assertThrows(IllegalArgumentException.class,
                () -> AuctionNotification.forSettlement(sold, AuctionNotificationType.AUCTION_SOLD, end));
        PurchaseIntent intent = PurchaseIntent.submit(sold.getProduct(), winner, 1);
        intent.enterTrade(end);
        sold.markSold(intent, end);

        AuctionNotification won = AuctionNotification.forSettlement(sold, AuctionNotificationType.AUCTION_WON, end);
        assertEquals(NotificationRecipientRole.CUSTOMER, won.getRecipientRole());
        assertSame(winner, won.getRecipientCustomer());
        assertEquals(new BigDecimal("12.00"), won.getFinalPrice());
        AuctionNotification seller = AuctionNotification.forSettlement(sold, AuctionNotificationType.AUCTION_SOLD, end);
        assertEquals(NotificationRecipientRole.SELLER, seller.getRecipientRole());
        assertNull(seller.getRecipientCustomer());
        assertThrows(IllegalArgumentException.class,
                () -> AuctionNotification.forSettlement(sold, AuctionNotificationType.AUCTION_UNSOLD, end));

        AuctionSession unsold = session();
        unsold.markUnsold(end);
        AuctionNotification passed = AuctionNotification.forSettlement(unsold, AuctionNotificationType.AUCTION_UNSOLD, end);
        assertNull(passed.getFinalPrice());
        assertThrows(IllegalArgumentException.class,
                () -> AuctionNotification.forSettlement(unsold, AuctionNotificationType.AUCTION_WON, end));
        passed.markRead(end.plusSeconds(1));
        passed.markRead(end.plusSeconds(9));
        assertEquals(end.plusSeconds(1), passed.getReadAt());
    }
}
