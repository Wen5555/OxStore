package com.team.shop.service;

import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.IntentStatus;
import com.team.shop.domain.ProductEventType;
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
import org.mockito.ArgumentCaptor;
import org.springframework.test.util.ReflectionTestUtils;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
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
    void successDeductsOneAndReturnsProductOnlineWithoutAdvancingQueue() {
        service.confirmSuccess(2L);

        assertEquals(1, product.getStock());
        assertEquals(ProductStatus.ONLINE, product.getStatus());
        assertEquals(IntentStatus.SUCCESS, intent.getStatus());
        assertEquals(TradeResult.SUCCESS, attempt.getResult());
        verify(histories).save(any(OrderHistory.class));
        verify(intents, never()).findQueueForUpdate(1L, IntentStatus.QUEUING);
    }

    @Test
    void finalUnitOfflinesProductAndFailsEveryQueuedIntentAtomically() {
        product = Product.create("test", "", BigDecimal.ONE, 1, product.getCategory());
        ReflectionTestUtils.setField(product, "id", 1L);
        product.startTrade(BusinessTime.now());
        when(products.findByIdForUpdate(1L)).thenReturn(Optional.of(product));
        PurchaseIntent pending = PurchaseIntent.submit(product, intent.getCustomer(), 2);
        ReflectionTestUtils.setField(pending, "id", 4L);
        when(intents.findQueueForUpdate(1L, IntentStatus.QUEUING)).thenReturn(List.of(pending));

        service.confirmSuccess(2L);

        assertEquals(0, product.getStock());
        assertEquals(ProductStatus.OFFLINE, product.getStatus());
        assertEquals(IntentStatus.FAILED, pending.getStatus());
        verify(histories, org.mockito.Mockito.times(2)).save(any(OrderHistory.class));
    }

    @Test
    void discardRecordsFailureWhileRequeueLeavesNextIntentQueued() {
        when(intents.maxQueueSeq(1L)).thenReturn(4L);
        service.confirmFail(2L, FailAction.REQUEUE);

        assertEquals(ProductStatus.ONLINE, product.getStatus());
        assertEquals(IntentStatus.QUEUING, intent.getStatus());
        assertEquals(5L, intent.getQueueSeq());
        assertEquals(TradeResult.FAILED, attempt.getResult());
        ArgumentCaptor<ProductStatusEvent> captor = ArgumentCaptor.forClass(ProductStatusEvent.class);
        verify(events).save(captor.capture());
        assertEquals(ProductEventType.TRADE_FAILED, captor.getValue().getEventType());
        assertEquals(ProductStatus.ONLINE, captor.getValue().getToStatus());
    }

    @Test
    void alreadyFinishedTradeCannotBeConfirmedAgain() {
        attempt.succeed(BusinessTime.now());
        when(attempts.findOpen(2L)).thenReturn(Optional.empty());
        assertThrows(StateConflictException.class, () -> service.confirmSuccess(2L));
    }
}
