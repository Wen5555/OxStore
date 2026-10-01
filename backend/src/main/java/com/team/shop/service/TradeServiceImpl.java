package com.team.shop.service;
import com.team.shop.domain.*;
import com.team.shop.dto.request.FailAction;
import com.team.shop.dto.response.IntentResponse;
import com.team.shop.entity.*;
import com.team.shop.exception.*;
import com.team.shop.repository.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.LocalDateTime;
import java.util.List;
@Service
public class TradeServiceImpl implements TradeService {
    private static final List<ProductStatus> ACTIVE_STATUSES =
            List.of(ProductStatus.ONLINE, ProductStatus.RESTORED_ONLINE, ProductStatus.FROZEN);
    private final IntentRepository intents;
    private final ProductRepository products;
    private final TradeAttemptRepository attempts;
    private final ProductStatusEventRepository events;
    public TradeServiceImpl(IntentRepository intents, ProductRepository products,
                            TradeAttemptRepository attempts, ProductStatusEventRepository events) {
        this.intents = intents; this.products = products; this.attempts = attempts; this.events = events;
    }
    @Override @Transactional
    public void startTrade(Long intentId) {
        Product product = lockActiveProduct(null, intentId);
        PurchaseIntent intent = loadLockedIntent(intentId, product);
        ProductStateMachine.assertCanStartTrade(product.getStatus());
        if (intents.findByProductIdAndStatus(product.getId(), IntentStatus.IN_TRANSACTION).isPresent()) {
            throw new StateConflictException("已有交易中的意向");
        }
        List<PurchaseIntent> queue = intents.findQueueForUpdate(product.getId(), IntentStatus.QUEUING);
        if (queue.isEmpty() || !queue.get(0).getId().equals(intentId) || intent.getStatus() != IntentStatus.QUEUING) {
            throw new StateConflictException("仅队首排队意向可以开始交易");
        }
        enterTrade(product, intent, BusinessTime.now());
    }
    @Override @Transactional
    public void confirmSuccess(Long intentId, Long tradeAttemptId) {
        Product product = lockActiveProduct(tradeAttemptId, intentId);
        PurchaseIntent intent = loadLockedIntent(intentId, product);
        TradeAttempt attempt = requireOpenAttempt(intent, tradeAttemptId);
        var now = BusinessTime.now();
        var before = product.getStatus();
        product.markSold(now);
        intent.markSuccess(now);
        attempt.succeed(now);
        events.save(new ProductStatusEvent(product, attempt, ProductEventType.TRADE_SUCCEEDED, before, now));
        for (PurchaseIntent queued : intents.findQueueForUpdate(product.getId(), IntentStatus.QUEUING)) {
            queued.markUnsold(now);
        }
    }
    @Override @Transactional
    public IntentResponse confirmFail(Long intentId, FailAction action, Long tradeAttemptId) {
        if (action == null) throw new BizException("action 不能为空");
        Product product = lockActiveProduct(tradeAttemptId, intentId);
        PurchaseIntent intent = loadLockedIntent(intentId, product);
        TradeAttempt attempt = requireOpenAttempt(intent, tradeAttemptId);
        var now = BusinessTime.now();
        var before = product.getStatus();
        product.markTradeFailed(now);
        if (action == FailAction.REQUEUE) intent.requeue(intents.maxQueueSeq(product.getId()) + 1, now);
        else intent.markFailed(now);
        attempt.fail(action, now);
        events.save(new ProductStatusEvent(product, attempt, ProductEventType.TRADE_FAILED, before, now));
        // Release generated-column uniqueness for the old trading intent/open attempt before inserting a new one.
        intents.flush();
        attempts.flush();
        List<PurchaseIntent> queue = intents.findQueueForUpdate(product.getId(), IntentStatus.QUEUING);
        if (queue.isEmpty()) return null;
        PurchaseIntent next = queue.get(0);
        TradeAttempt nextAttempt = enterTrade(product, next, now);
        return IntentResponse.from(next, 0, nextAttempt.getId());
    }
    private TradeAttempt enterTrade(Product product, PurchaseIntent intent, LocalDateTime now) {
        var before = product.getStatus();
        intent.enterTrade(now);
        product.startTrade(now);
        // Flush status first: the unique trading_flag must be owned by the new intent before the attempt is inserted.
        intents.flush();
        TradeAttempt attempt = attempts.save(new TradeAttempt(intent, now));
        events.save(new ProductStatusEvent(product, attempt, ProductEventType.TRADE_STARTED, before, now));
        return attempt;
    }
    private TradeAttempt requireOpenAttempt(PurchaseIntent intent, Long tradeAttemptId) {
        if (tradeAttemptId == null) throw new BizException("tradeAttemptId 不能为空");
        if (intent.getStatus() != IntentStatus.IN_TRANSACTION) throw new StateConflictException("意向当前并非交易中");
        TradeAttempt attempt = attempts.findOpen(intent.getId())
                .orElseThrow(() -> new StateConflictException("交易中意向缺少未结束的交易尝试"));
        if (!attempt.getId().equals(tradeAttemptId)) throw new StateConflictException("交易尝试已失效，请刷新队列");
        return attempt;
    }
    private PurchaseIntent loadLockedIntent(Long id, Product product) {
        PurchaseIntent intent = intents.findByIdForUpdate(id).orElseThrow(() -> new NotFoundException("意向不存在"));
        if (!intent.getProduct().getId().equals(product.getId())) throw new NotFoundException("意向不属于当前商品");
        return intent;
    }
    private Product lockActiveProduct(Long attemptId, Long intentId) {
        return products.findActiveForUpdate(ACTIVE_STATUSES).orElseGet(() -> {
            if (attemptId != null && attempts.findById(attemptId)
                    .filter(a -> a.getIntent().getId().equals(intentId)).isPresent()) {
                throw new StateConflictException("交易尝试已结束，请刷新队列");
            }
            throw new NotFoundException("当前没有在售商品");
        });
    }
}
