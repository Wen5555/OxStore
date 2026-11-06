package com.team.shop.repository;

import com.team.shop.domain.AuctionNotificationType;
import com.team.shop.domain.AuctionStatus;
import com.team.shop.domain.NotificationRecipientRole;
import com.team.shop.domain.SellingMode;
import com.team.shop.entity.AuctionBid;
import com.team.shop.entity.AuctionNotification;
import com.team.shop.entity.AuctionSession;
import com.team.shop.entity.Category;
import com.team.shop.entity.Customer;
import com.team.shop.entity.Product;
import com.team.shop.entity.PurchaseIntent;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.PageRequest;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

@DataJpaTest(properties = {
        "spring.datasource.url=jdbc:h2:mem:oxstore_auction;MODE=MySQL;DB_CLOSE_DELAY=-1",
        "spring.datasource.username=sa",
        "spring.datasource.password=",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.jpa.hibernate.ddl-auto=create-drop"})
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class AuctionRepositoryTest {
    private static final LocalDateTime START = LocalDateTime.of(2026, 11, 6, 10, 0);

    @Autowired private EntityManager em;
    @Autowired private AuctionSessionRepository sessions;
    @Autowired private AuctionBidRepository bids;
    @Autowired private AuctionNotificationRepository notifications;

    private Category leaf;
    private int sequence;

    private Customer customer(String name) {
        Customer c = new Customer(name, "hash", "13800000000", null, START);
        em.persist(c);
        return c;
    }

    private AuctionSession auction(String name, LocalDateTime endsAt) {
        if (leaf == null) {
            Category root = new Category("一级", null);
            em.persist(root);
            leaf = new Category("二级", root);
            em.persist(leaf);
        }
        Product product = Product.createAuction(name + (++sequence), "", new BigDecimal("10.00"), leaf);
        em.persist(product);
        return sessions.saveAndFlush(AuctionSession.open(product, BigDecimal.TEN, BigDecimal.ONE, START, endsAt));
    }

    @Test
    void sessionAndBidsPersistAndReloadByProduct() {
        AuctionSession a = auction("拍品", START.plusMinutes(2));
        Customer buyer = customer("buyer_a");
        bids.save(a.acceptBid(buyer, new BigDecimal("10"), START.plusSeconds(1)));
        bids.save(a.acceptBid(customer("buyer_b"), new BigDecimal("11"), START.plusSeconds(2)));
        sessions.flush();
        em.clear();

        AuctionSession loaded = sessions.findByProductId(a.getProduct().getId()).orElseThrow();
        assertEquals(SellingMode.AUCTION, loaded.getProduct().getSellingMode());
        assertEquals(2, loaded.getBidCount());
        assertEquals(new BigDecimal("11.00"), loaded.getCurrentPrice());
        assertEquals("buyer_b", loaded.getLeader().getUsername());
        List<AuctionBid> recent = bids.findTop10ByAuctionIdOrderByBidSeqDesc(loaded.getId());
        assertEquals(List.of(2, 1), recent.stream().map(AuctionBid::getBidSeq).toList());
        assertTrue(bids.existsByAuctionIdAndCustomerId(loaded.getId(), buyer.getId()));
    }

    @Test
    void duplicateBidSequenceOrSessionPerProductIsRejected() {
        AuctionSession a = auction("拍品", START.plusMinutes(2));
        Customer buyer = customer("buyer_a");
        AuctionBid first = a.acceptBid(buyer, new BigDecimal("10"), START.plusSeconds(1));
        bids.saveAndFlush(first);
        em.detach(a);
        // Simulate a writer that missed the first bid (no row lock): it would reuse bid_seq 1.
        em.createNativeQuery("UPDATE auction_session SET bid_count = 0, current_price = NULL, leader_customer_id = NULL WHERE id = ?")
                .setParameter(1, a.getId()).executeUpdate();
        AuctionSession reread = sessions.findById(a.getId()).orElseThrow();
        em.refresh(reread);
        AuctionBid duplicate = reread.acceptBid(buyer, new BigDecimal("12"), START.plusSeconds(2));
        assertThrows(DataIntegrityViolationException.class, () -> bids.saveAndFlush(duplicate));
    }

    @Test
    void secondSessionForSameProductIsRejected() {
        AuctionSession a = auction("拍品", START.plusMinutes(2));
        AuctionSession again = AuctionSession.open(a.getProduct(), BigDecimal.ONE, BigDecimal.ONE, START, START.plusMinutes(1));
        assertThrows(DataIntegrityViolationException.class, () -> sessions.saveAndFlush(again));
    }

    @Test
    void dueScanFindsOnlyExpiredLiveSessionsInDeadlineOrder() {
        AuctionSession later = auction("后到期", START.plusMinutes(3));
        AuctionSession earlier = auction("先到期", START.plusMinutes(1));
        AuctionSession future = auction("未到期", START.plusMinutes(30));
        AuctionSession settled = auction("已流拍", START.plusMinutes(1));
        settled.markUnsold(START.plusMinutes(1));
        sessions.saveAndFlush(settled);

        List<Long> due = sessions.findDueIds(AuctionStatus.LIVE, START.plusMinutes(3), PageRequest.of(0, 50));
        assertEquals(List.of(earlier.getId(), later.getId()), due);
        assertTrue(!due.contains(future.getId()));
    }

    @Test
    void settlementLinksWinnerIntentAndNotificationsAreIdempotent() {
        AuctionSession a = auction("拍品", START.plusMinutes(2));
        Customer winner = customer("winner");
        bids.save(a.acceptBid(winner, new BigDecimal("15"), START.plusSeconds(5)));
        LocalDateTime end = START.plusMinutes(2);
        PurchaseIntent intent = PurchaseIntent.submit(a.getProduct(), winner, 1);
        intent.enterTrade(end);
        em.persist(intent);
        a.markSold(intent, end);
        sessions.saveAndFlush(a);
        notifications.save(AuctionNotification.forSettlement(a, AuctionNotificationType.AUCTION_SOLD, end));
        notifications.saveAndFlush(AuctionNotification.forSettlement(a, AuctionNotificationType.AUCTION_WON, end));

        assertTrue(notifications.existsByAuctionIdAndType(a.getId(), AuctionNotificationType.AUCTION_WON));
        assertEquals(1, notifications.findByRecipientCustomerIdOrderByCreatedAtDescIdDesc(
                winner.getId(), PageRequest.of(0, 10)).getTotalElements());
        assertEquals(1, notifications.countByRecipientRoleAndReadAtIsNull(NotificationRecipientRole.SELLER));
        assertThrows(DataIntegrityViolationException.class, () -> notifications.saveAndFlush(
                AuctionNotification.forSettlement(a, AuctionNotificationType.AUCTION_WON, end.plusSeconds(1))));
    }
}
