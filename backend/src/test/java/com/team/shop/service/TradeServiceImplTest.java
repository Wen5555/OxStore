package com.team.shop.service;

import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.IntentStatus;
import com.team.shop.domain.ProductStatus;
import com.team.shop.domain.TradeResult;
import com.team.shop.dto.request.FailAction;
import com.team.shop.entity.Category;
import com.team.shop.entity.Customer;
import com.team.shop.entity.OrderHistory;
import com.team.shop.entity.Product;
import com.team.shop.entity.ProductStatusEvent;
import com.team.shop.entity.PurchaseIntent;
import com.team.shop.entity.TradeAttempt;
import com.team.shop.exception.StateConflictException;
import com.team.shop.repository.IntentRepository;
import com.team.shop.repository.OrderHistoryRepository;
import com.team.shop.repository.ProductRepository;
import com.team.shop.repository.ProductStatusEventRepository;
import com.team.shop.repository.TradeAttemptRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.math.BigDecimal;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class TradeServiceImplTest {
    private final IntentRepository intents = mock(IntentRepository.class);
    private final ProductRepository products = mock(ProductRepository.class);
    private final TradeAttemptRepository attempts = mock(TradeAttemptRepository.class);
    private final ProductStatusEventRepository events = mock(ProductStatusEventRepository.class);
    private final OrderHistoryRepository histories = mock(OrderHistoryRepository.class);
    private final TradeServiceImpl service = new TradeServiceImpl(intents, products, attempts, events, histories);

    private Product product;
    private PurchaseIntent intent;
    private TradeAttempt attempt;

    @BeforeEach
    void setUp() {
        Category root = new Category("root", null);
        Category leaf = new Category("leaf", root);
        product = Product.create("test", "", BigDecimal.ONE, 2, leaf);
        ReflectionTestUtils.setField(product, "id", 1L);
        Customer customer = new Customer("buyer", "hash", "00000000000", null, BusinessTime.now());
        ReflectionTestUtils.setField(customer, "id", 3L);
        intent = PurchaseIntent.submit(product, customer, 1);
        ReflectionTestUtils.setField(intent, "id", 2L);
        var now = BusinessTime.now();
        intent.enterTrade(now);
        product.startTrade(now);
        attempt = new TradeAttempt(intent, now);
        ReflectionTestUtils.setField(attempt, "id", 10L);
        when(intents.findById(2L)).thenReturn(Optional.of(intent));
        when(products.findByIdForUpdate(1L)).thenReturn(Optional.of(product));
        when(intents.findByIdForUpdate(2L)).thenReturn(Optional.of(intent));
        when(attempts.findOpen(2L)).thenReturn(Optional.of(attempt));
        when(histories.save(any(OrderHistory.class))).thenAnswer(call -> call.getArgument(0));
        when(events.save(any(ProductStatusEvent.class))).thenAnswer(call -> call.getArgument(0));
    }

    @Test
    void auctionWinnerCanCompleteThroughTheExistingTradePath() {
        prepareAuctionFixture();
        service.confirmSuccess(2L);

        assertEquals(java.math.BigInteger.ZERO, product.getStock());
        assertEquals(ProductStatus.OFFLINE, product.getStatus());
        assertEquals(IntentStatus.SUCCESS, intent.getStatus());
        assertEquals(TradeResult.SUCCESS, attempt.getResult());
        verify(histories).save(any(OrderHistory.class));
        verify(intents).findQueueForUpdate(1L, IntentStatus.QUEUING);
    }

    @Test
    void fixedPriceLegacyTradeActionsAreClosedWithoutMutation() {
        StateConflictException start = assertThrows(StateConflictException.class, () -> service.startTrade(2L));
        StateConflictException success = assertThrows(StateConflictException.class, () -> service.confirmSuccess(2L));
        StateConflictException discard = assertThrows(StateConflictException.class,
                () -> service.confirmFail(2L, FailAction.DISCARD));
        StateConflictException requeue = assertThrows(StateConflictException.class,
                () -> service.confirmFail(2L, FailAction.REQUEUE));

        assertEquals(40917, start.getCode());
        assertEquals(40917, success.getCode());
        assertEquals(40917, discard.getCode());
        assertEquals(40917, requeue.getCode());
        assertEquals(java.math.BigInteger.valueOf(2), product.getStock());
        assertEquals(ProductStatus.FROZEN, product.getStatus());
        assertEquals(IntentStatus.IN_TRANSACTION, intent.getStatus());
        verifyNoInteractions(attempts, events, histories);
    }

    @Test
    void alreadyFinishedTradeCannotBeConfirmedAgain() {
        prepareAuctionFixture();
        attempt.succeed(BusinessTime.now());
        when(attempts.findOpen(2L)).thenReturn(Optional.empty());
        assertThrows(StateConflictException.class, () -> service.confirmSuccess(2L));
    }

    @Test
    void auctionFailureRejectsRequeueAndKeepsProductOffline() {
        var auctionProduct = Product.createAuction("auction", "", BigDecimal.ONE, product.getCategory());
        ReflectionTestUtils.setField(auctionProduct, "id", 11L);
        var now = BusinessTime.now();
        var auctionIntent = PurchaseIntent.createAuctionWinner(auctionProduct, intent.getCustomer(), now);
        ReflectionTestUtils.setField(auctionIntent, "id", 12L);
        auctionProduct.startTrade(now);
        var auctionAttempt = new TradeAttempt(auctionIntent, now);
        when(products.findByIdForUpdate(11L)).thenReturn(Optional.of(auctionProduct));
        when(intents.findById(12L)).thenReturn(Optional.of(auctionIntent));
        when(intents.findByIdForUpdate(12L)).thenReturn(Optional.of(auctionIntent));
        when(attempts.findOpen(12L)).thenReturn(Optional.of(auctionAttempt));

        assertThrows(StateConflictException.class, () -> service.confirmFail(12L, FailAction.REQUEUE));
        assertEquals(ProductStatus.FROZEN, auctionProduct.getStatus());

        service.confirmFail(12L, FailAction.DISCARD);
        assertEquals(ProductStatus.OFFLINE, auctionProduct.getStatus());
        assertEquals(IntentStatus.FAILED, auctionIntent.getStatus());
        assertEquals(TradeResult.FAILED, auctionAttempt.getResult());
    }

    private void prepareAuctionFixture() {
        var auctionProduct = Product.createAuction("auction", "", BigDecimal.ONE, product.getCategory());
        ReflectionTestUtils.setField(auctionProduct, "id", 1L);
        var now = BusinessTime.now();
        var auctionIntent = PurchaseIntent.createAuctionWinner(auctionProduct, intent.getCustomer(), now);
        ReflectionTestUtils.setField(auctionIntent, "id", 2L);
        auctionProduct.startTrade(now);
        var auctionAttempt = new TradeAttempt(auctionIntent, now);
        product = auctionProduct;
        intent = auctionIntent;
        attempt = auctionAttempt;
        when(products.findByIdForUpdate(1L)).thenReturn(Optional.of(auctionProduct));
        when(intents.findById(2L)).thenReturn(Optional.of(auctionIntent));
        when(intents.findByIdForUpdate(2L)).thenReturn(Optional.of(auctionIntent));
        when(attempts.findOpen(2L)).thenReturn(Optional.of(auctionAttempt));
    }
}
