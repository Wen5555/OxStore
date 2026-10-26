package com.team.shop.service;

import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.IntentStatus;
import com.team.shop.domain.ProductEventType;
import com.team.shop.domain.ProductStatus;
import com.team.shop.dto.request.FailAction;
import com.team.shop.entity.OrderHistory;
import com.team.shop.entity.Product;
import com.team.shop.entity.PurchaseIntent;
import com.team.shop.entity.TradeAttempt;
import com.team.shop.exception.BizException;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.StateConflictException;
import com.team.shop.repository.IntentRepository;
import com.team.shop.repository.OrderHistoryRepository;
import com.team.shop.repository.ProductRepository;
import com.team.shop.repository.ProductStatusEventRepository;
import com.team.shop.repository.TradeAttemptRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
public class TradeServiceImpl implements TradeService {
    private final IntentRepository intents;
    private final ProductRepository products;
    private final TradeAttemptRepository attempts;
    private final ProductStatusEventRepository events;
    private final OrderHistoryRepository orderHistory;

    public TradeServiceImpl(IntentRepository intents, ProductRepository products,
                            TradeAttemptRepository attempts, ProductStatusEventRepository events,
                            OrderHistoryRepository orderHistory) {
        this.intents = intents;
        this.products = products;
        this.attempts = attempts;
        this.events = events;
        this.orderHistory = orderHistory;
    }

    @Override
    @Transactional
    public void startTrade(Long intentId) {
        Product product = lockProductForIntent(intentId);
        PurchaseIntent intent = lockIntent(intentId, product);
        if (intents.findByProductIdAndStatus(product.getId(), IntentStatus.IN_TRANSACTION).isPresent()) {
            throw new StateConflictException("该商品已有交易中的意向", 40902);
        }
        var queue = intents.findQueueForUpdate(product.getId(), IntentStatus.QUEUING);
        if (queue.isEmpty() || !queue.get(0).getId().equals(intentId)) {
            throw new StateConflictException("仅商品队首意向可以开始交易", 40902);
        }
        LocalDateTime now = BusinessTime.now();
        ProductStatus before = product.getStatus();
        intent.enterTrade(now);
        product.startTrade(now);
        intents.flush();
        TradeAttempt attempt = attempts.save(new TradeAttempt(intent, now));
        events.save(new com.team.shop.entity.ProductStatusEvent(
                product, attempt, ProductEventType.TRADE_STARTED, before, now));
    }

    @Override
    @Transactional
    public void confirmSuccess(Long intentId) {
        Product product = lockProductForIntent(intentId);
        PurchaseIntent intent = lockIntent(intentId, product);
        TradeAttempt attempt = requireOpenAttempt(intent);
        LocalDateTime now = BusinessTime.now();
        ProductStatus before = product.getStatus();
        boolean inventoryEmpty = product.markTradeSucceeded(now);
        intent.markSuccess(now);
        attempt.succeed(now);
        OrderHistory successHistory = historyFor(intent, IntentStatus.SUCCESS, now);
        if (successHistory != null) {
            orderHistory.save(successHistory);
        }
        events.save(new com.team.shop.entity.ProductStatusEvent(
                product, attempt, ProductEventType.TRADE_SUCCEEDED, before, now));
        if (inventoryEmpty) {
            failQueuedIntents(product, now);
        }
    }

    @Override
    @Transactional
    public void confirmFail(Long intentId, FailAction action) {
        if (action == null) {
            throw new BizException("action 不能为空");
        }
        Product product = lockProductForIntent(intentId);
        PurchaseIntent intent = lockIntent(intentId, product);
        TradeAttempt attempt = requireOpenAttempt(intent);
        LocalDateTime now = BusinessTime.now();
        ProductStatus before = product.getStatus();
        product.markTradeFailed(now);
        if (action == FailAction.REQUEUE) {
            intent.requeue(intents.maxQueueSeq(product.getId()) + 1, now);
        } else {
            intent.markFailed(now);
            OrderHistory failureHistory = historyFor(intent, IntentStatus.FAILED, now);
            if (failureHistory != null) {
                orderHistory.save(failureHistory);
            }
        }
        attempt.fail(action, now);
        events.save(new com.team.shop.entity.ProductStatusEvent(
                product, attempt, ProductEventType.TRADE_FAILED, before, now));
        intents.flush();
        attempts.flush();
    }

    private Product lockProductForIntent(Long intentId) {
        PurchaseIntent reference = intents.findById(intentId)
                .orElseThrow(() -> new NotFoundException("意向不存在", 40403));
        return products.findByIdForUpdate(reference.getProduct().getId())
                .orElseThrow(() -> new NotFoundException("商品不存在"));
    }

    private PurchaseIntent lockIntent(Long intentId, Product product) {
        PurchaseIntent intent = intents.findByIdForUpdate(intentId)
                .orElseThrow(() -> new NotFoundException("意向不存在", 40403));
        if (!intent.getProduct().getId().equals(product.getId())) {
            throw new NotFoundException("意向不属于该商品", 40403);
        }
        return intent;
    }

    private TradeAttempt requireOpenAttempt(PurchaseIntent intent) {
        if (intent.getStatus() != IntentStatus.IN_TRANSACTION) {
            throw new StateConflictException("该意向当前不在交易中");
        }
        return attempts.findOpen(intent.getId())
                .orElseThrow(() -> new StateConflictException("交易尝试已结束，请刷新队列"));
    }

    private OrderHistory historyFor(PurchaseIntent intent, IntentStatus status, LocalDateTime transactedAt) {
        if (intent.getCustomer() == null) {
            return null;
        }
        return new OrderHistory(intent.getId(), intent.getCustomer(), intent.getProductNameSnapshot(),
                intent.getSubmittedAt(), status, transactedAt);
    }

    private void failQueuedIntents(Product product, LocalDateTime now) {
        for (PurchaseIntent queued : intents.findQueueForUpdate(product.getId(), IntentStatus.QUEUING)) {
            queued.markQueuedIntentFailed(now);
            if (queued.getCustomer() != null) {
                orderHistory.save(historyFor(queued, IntentStatus.FAILED, now));
            }
        }
    }
}
