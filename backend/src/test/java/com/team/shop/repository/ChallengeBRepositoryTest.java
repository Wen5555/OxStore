package com.team.shop.repository;

import com.team.shop.domain.OrderCancelledBy;
import com.team.shop.domain.OrderStatus;
import com.team.shop.domain.ReceiptOperationType;
import com.team.shop.entity.CartItem;
import com.team.shop.entity.CartItemTombstone;
import com.team.shop.entity.Category;
import com.team.shop.entity.CheckoutConfirmation;
import com.team.shop.entity.Customer;
import com.team.shop.entity.Favorite;
import com.team.shop.entity.FavoriteMutation;
import com.team.shop.entity.OperationReceipt;
import com.team.shop.entity.Product;
import com.team.shop.entity.ShopOrder;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.PageRequest;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.time.LocalDateTime;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 挑战 B 实体/Repository 在 H2 上的形状检查（映射、转换器、唯一约束、查询）。
 * CHECK、触发器和真实锁行为只能在 MySQL 上验证，见 scripts/verify_challenge_b_database.py。
 */
@DataJpaTest(properties = {
        "spring.datasource.url=jdbc:h2:mem:oxstore_challenge_b;MODE=MySQL;DB_CLOSE_DELAY=-1",
        "spring.datasource.username=sa",
        "spring.datasource.password=",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.jpa.hibernate.ddl-auto=create-drop"})
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class ChallengeBRepositoryTest {
    private static final LocalDateTime T0 = LocalDateTime.of(2026, 11, 15, 10, 0);
    private static final BigInteger HUGE = new BigInteger("123456789012345678901234567890");

    @Autowired private EntityManager em;
    @Autowired private ShopOrderRepository orders;
    @Autowired private OrderItemRepository orderItems;
    @Autowired private FavoriteRepository favorites;
    @Autowired private FavoriteMutationRepository mutations;
    @Autowired private CartItemRepository carts;
    @Autowired private CartItemTombstoneRepository tombstones;
    @Autowired private CheckoutConfirmationRepository confirmations;
    @Autowired private OperationReceiptRepository receipts;

    private Category leaf;
    private int sequence;

    private Customer customer() {
        Customer c = new Customer("buyer" + (++sequence), "hash", "13800000000", null, T0);
        em.persist(c);
        return c;
    }

    private Product product() {
        if (leaf == null) {
            Category root = new Category("一级", null);
            em.persist(root);
            leaf = new Category("二级", root);
            em.persist(leaf);
        }
        Product p = Product.create("商品" + (++sequence), "", new BigDecimal("19.99"), 5, leaf);
        em.persist(p);
        return p;
    }

    private void flush() {
        em.flush();
        em.clear();
    }

    @Test
    void orderKeepsUnboundedQuantityAndExactMoney() {
        Customer c = customer();
        Product p = product();
        BigDecimal line = new BigDecimal("19.99").multiply(new BigDecimal(HUGE));
        ShopOrder order = new ShopOrder(UUID.randomUUID().toString(), c, line, T0);
        order.addItem(p, p.getName(), new BigDecimal("19.99"), HUGE, line);
        orders.saveAndFlush(order);
        em.clear();

        ShopOrder loaded = orders.findByOrderNo(order.getOrderNo()).orElseThrow();
        assertEquals(OrderStatus.PLACED, loaded.getStatus());
        assertEquals(0, line.compareTo(loaded.getTotalAmount()));
        assertEquals(HUGE, orderItems.findByOrderIdOrderByProductIdAsc(loaded.getId()).get(0).getQuantitySnapshot());
        assertEquals(1, loaded.getItems().size());
    }

    @Test
    void orderNoAndItemProductAreUnique() {
        Customer c = customer();
        Product p = product();
        String no = UUID.randomUUID().toString();
        orders.saveAndFlush(new ShopOrder(no, c, new BigDecimal("1.00"), T0));
        assertThrows(DataIntegrityViolationException.class,
                () -> orders.saveAndFlush(new ShopOrder(no, c, new BigDecimal("1.00"), T0)));

        ShopOrder dup = new ShopOrder(UUID.randomUUID().toString(), c, new BigDecimal("2.00"), T0);
        dup.addItem(p, "a", BigDecimal.ONE, BigInteger.ONE, new BigDecimal("1.00"));
        dup.addItem(p, "a", BigDecimal.ONE, BigInteger.ONE, new BigDecimal("1.00"));
        assertThrows(DataIntegrityViolationException.class, () -> orders.saveAndFlush(dup));
    }

    @Test
    void cancellationRecordsInitiatorAndTime() {
        Customer c = customer();
        ShopOrder order = orders.saveAndFlush(new ShopOrder(UUID.randomUUID().toString(), c, new BigDecimal("3.00"), T0));
        order.markCancelled(OrderCancelledBy.SELLER, "缺货", T0.plusMinutes(5));
        orders.saveAndFlush(order);
        em.clear();
        ShopOrder loaded = orders.findById(order.getId()).orElseThrow();
        assertEquals(OrderStatus.CANCELLED, loaded.getStatus());
        assertEquals(OrderCancelledBy.SELLER, loaded.getCancelledBy());
        assertEquals(T0.plusMinutes(5), loaded.getCancelledAt());
    }

    @Test
    void orderHistoryPagesNewestFirstWithStableTieBreak() {
        Customer c = customer();
        for (int i = 0; i < 3; i++) {
            orders.save(new ShopOrder(UUID.randomUUID().toString(), c, new BigDecimal("1.00"), T0));
        }
        flush();
        var page = orders.findByCustomerIdOrderByCreatedAtDescIdDesc(c.getId(), PageRequest.of(0, 2));
        assertEquals(3, page.getTotalElements());
        assertTrue(page.getContent().get(0).getId() > page.getContent().get(1).getId());
    }

    @Test
    void favoriteIsUniquePerCustomerAndProductAndPagedByTime() {
        Customer c = customer();
        Product a = product();
        Product b = product();
        favorites.saveAndFlush(new Favorite(c, a, T0));
        assertThrows(DataIntegrityViolationException.class,
                () -> favorites.saveAndFlush(new Favorite(c, a, T0.plusMinutes(1))));
        em.clear();
        favorites.saveAndFlush(new Favorite(c, b, T0.plusMinutes(2)));
        var page = favorites.findByCustomerIdOrderByCreatedAtDescIdDesc(c.getId(), PageRequest.of(0, 10));
        assertEquals(b.getId(), page.getContent().get(0).getProduct().getId());
        assertEquals(1, favorites.deleteByCustomerIdAndProductId(c.getId(), a.getId()));
        assertTrue(favorites.findByCustomerIdAndProductId(c.getId(), a.getId()).isEmpty());
    }

    @Test
    void favoriteMutationSequenceTracksIndependentCancel() {
        Customer c = customer();
        Product p = product();
        FavoriteMutation m = new FavoriteMutation(c.getId(), p.getId());
        long movedAt = m.recordWrite();
        assertEquals(0, m.getLastCancelSeq());
        long cancelled = m.recordCancel();
        assertTrue(cancelled > movedAt);
        mutations.saveAndFlush(m);
        em.clear();
        FavoriteMutation loaded = mutations.findById(new FavoriteMutation.Key(c.getId(), p.getId())).orElseThrow();
        assertEquals(cancelled, loaded.getLastCancelSeq());
        assertEquals(cancelled, loaded.getOperationSeq());
    }

    @Test
    void cartRowIsUniquePerCustomerAndProductAndRejectsNonPositiveQuantity() {
        Customer c = customer();
        Product p = product();
        CartItem row = carts.saveAndFlush(new CartItem(c, p, HUGE, T0));
        em.clear();
        assertEquals(HUGE, carts.findById(row.getId()).orElseThrow().getQuantity());
        assertThrows(DataIntegrityViolationException.class,
                () -> carts.saveAndFlush(new CartItem(c, p, BigInteger.ONE, T0)));
        assertThrows(IllegalArgumentException.class, () -> new CartItem(c, p, BigInteger.ZERO, T0));
        assertThrows(IllegalArgumentException.class, () -> new CartItem(c, p, BigInteger.valueOf(-1), T0));
    }

    @Test
    void removedCartRowIsRememberedByTombstoneAndNewRowGetsNewId() {
        Customer c = customer();
        Product p = product();
        CartItem first = carts.saveAndFlush(new CartItem(c, p, BigInteger.TWO, T0));
        Long oldId = first.getId();
        tombstones.save(new CartItemTombstone(oldId, c.getId(), p.getId(), T0.plusMinutes(1)));
        carts.delete(first);
        flush();
        CartItem second = carts.saveAndFlush(new CartItem(c, p, BigInteger.ONE, T0.plusMinutes(2)));
        assertFalse(oldId.equals(second.getId()));
        assertEquals(c.getId(), tombstones.findByCartItemId(oldId).orElseThrow().getCustomerId());
        assertThrows(DataIntegrityViolationException.class, () ->
                tombstones.saveAndFlush(new CartItemTombstone(oldId, c.getId(), p.getId(), T0.plusMinutes(3))));
    }

    @Test
    void confirmationIsFoundByTokenWithItsRows() {
        Customer c = customer();
        Product p = product();
        String token = UUID.randomUUID().toString();
        CheckoutConfirmation confirmation = new CheckoutConfirmation(token, c, new BigDecimal("39.98"), "d".repeat(64), T0);
        confirmation.addItem(7L, p, new BigDecimal("19.99"), BigInteger.TWO);
        confirmations.saveAndFlush(confirmation);
        em.clear();
        CheckoutConfirmation loaded = confirmations.findByToken(token).orElseThrow();
        assertEquals(1, loaded.getItems().size());
        assertEquals(BigInteger.TWO, loaded.getItems().get(0).getQuantity());
    }

    @Test
    void receiptIsUniquePerCustomerTypeAndKey() {
        Customer c = customer();
        String key = UUID.randomUUID().toString();
        receipts.saveAndFlush(new OperationReceipt(c, ReceiptOperationType.CHECKOUT, key, "h".repeat(64), "{}", T0));
        assertTrue(receipts.findByCustomerIdAndOperationTypeAndRequestKey(c.getId(), ReceiptOperationType.CHECKOUT, key).isPresent());
        assertThrows(DataIntegrityViolationException.class, () -> receipts.saveAndFlush(
                new OperationReceipt(c, ReceiptOperationType.CHECKOUT, key, "x".repeat(64), "{}", T0)));
        em.clear();
        receipts.saveAndFlush(new OperationReceipt(c, ReceiptOperationType.CART_ADD, key, "h".repeat(64), "{}", T0));
    }
}
