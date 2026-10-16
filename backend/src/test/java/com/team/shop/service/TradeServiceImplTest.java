package com.team.shop.service;

import com.team.shop.domain.*;
import com.team.shop.dto.request.FailAction;
import com.team.shop.entity.*;
import com.team.shop.exception.StateConflictException;
import com.team.shop.repository.*;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.test.util.ReflectionTestUtils;
import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class TradeServiceImplTest {
    private final IntentRepository intents = mock(IntentRepository.class);
    private final ProductRepository products = mock(ProductRepository.class);
    private final TradeAttemptRepository attempts = mock(TradeAttemptRepository.class);
    private final ProductStatusEventRepository events = mock(ProductStatusEventRepository.class);
    private final TradeServiceImpl service = new TradeServiceImpl(intents, products, attempts, events);
    private Product product;
    private PurchaseIntent intent;
    private TradeAttempt old;
    @BeforeEach void setUp() {
        product = Product.create("test", "description", "/img", BigDecimal.ONE);
        ReflectionTestUtils.setField(product, "id", 1L);
        intent = PurchaseIntent.submit(product, "buyer", "00000000000", "hash", "lookup", 1);
        ReflectionTestUtils.setField(intent, "id", 2L);
        var now = BusinessTime.now();
        intent.enterTrade(now);
        product.startTrade(now);
        old = new TradeAttempt(intent, now);
        ReflectionTestUtils.setField(old, "id", 10L);
        when(products.findActiveForUpdate(anyCollection())).thenReturn(Optional.of(product));
        when(intents.findByIdForUpdate(2L)).thenReturn(Optional.of(intent));
        when(attempts.findOpen(2L)).thenReturn(Optional.of(old));
    }
    @Test void oldAttemptCannotFinishNewTrade() {
        assertThrows(StateConflictException.class, () -> service.confirmSuccess(2L, 9L));
        assertEquals(IntentStatus.IN_TRANSACTION, intent.getStatus());
        assertNull(old.getFinishedAt());
        verifyNoInteractions(events);
    }
    @Test void requeueSingleBuyerClosesOldAttemptAndCreatesNewOneWithTwoEvents() {
        when(intents.maxQueueSeq(1L)).thenReturn(1L);
        when(intents.findQueueForUpdate(1L, IntentStatus.QUEUING)).thenReturn(List.of(intent));
        when(attempts.save(any(TradeAttempt.class))).thenAnswer(invocation -> {
            TradeAttempt value = invocation.getArgument(0);
            ReflectionTestUtils.setField(value, "id", 11L);
            return value;
        });
        var response = service.confirmFail(2L, FailAction.REQUEUE, 10L);
        assertNotNull(response);
        assertEquals(11L, response.currentTradeAttemptId());
        assertEquals(IntentStatus.IN_TRANSACTION, intent.getStatus());
        assertEquals(2L, intent.getQueueSeq());
        assertEquals(TradeResult.FAILED, old.getResult());
        assertEquals("hash", intent.getTokenHash());
        assertEquals("lookup", intent.getTokenLookup());
        ArgumentCaptor<ProductStatusEvent> captor = ArgumentCaptor.forClass(ProductStatusEvent.class);
        verify(events, times(2)).save(captor.capture());
        assertEquals(ProductEventType.TRADE_FAILED, captor.getAllValues().get(0).getEventType());
        assertEquals(ProductStatus.RESTORED_ONLINE, captor.getAllValues().get(0).getToStatus());
        assertEquals(ProductEventType.TRADE_STARTED, captor.getAllValues().get(1).getEventType());
        assertEquals(ProductStatus.FROZEN, captor.getAllValues().get(1).getToStatus());
    }
}
