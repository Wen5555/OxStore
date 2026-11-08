package com.team.shop.service;

import com.team.shop.domain.AuctionStatus;
import com.team.shop.domain.NotificationRecipientRole;
import com.team.shop.dto.response.AuctionNotificationResponse;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

/** 单实例拍卖事件 Hub，负责竞价流和结拍提醒流的隔离、清理及心跳。 */
@Component
public class AuctionEventHub {
    private final Map<Long, CopyOnWriteArrayList<ProductSubscriber>> productSubscribers = new ConcurrentHashMap<>();
    private final Map<NotificationSubscription, CopyOnWriteArrayList<SseEmitter>> notificationSubscribers =
            new ConcurrentHashMap<>();

    public SseEmitter subscribeProduct(Long productId, Long customerId) {
        SseEmitter emitter = new SseEmitter(30 * 60 * 1000L);
        ProductSubscriber subscriber = new ProductSubscriber(emitter, customerId);
        productSubscribers.computeIfAbsent(productId, ignored -> new CopyOnWriteArrayList<>()).add(subscriber);
        Runnable cleanup = () -> removeProduct(productId, subscriber);
        emitter.onCompletion(cleanup);
        emitter.onTimeout(cleanup);
        emitter.onError(ignored -> cleanup.run());
        return emitter;
    }

    public SseEmitter subscribeNotifications(NotificationRecipientRole role, Long customerId) {
        NotificationSubscription subscription = new NotificationSubscription(role, customerId);
        SseEmitter emitter = new SseEmitter(30 * 60 * 1000L);
        notificationSubscribers.computeIfAbsent(subscription, ignored -> new CopyOnWriteArrayList<>()).add(emitter);
        Runnable cleanup = () -> removeNotification(subscription, emitter);
        emitter.onCompletion(cleanup);
        emitter.onTimeout(cleanup);
        emitter.onError(ignored -> cleanup.run());
        return emitter;
    }

    /** 事务提交后广播竞价，避免数据库回滚但前端已收到事件。 */
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT, fallbackExecution = true)
    public void onBidCommitted(BidCommittedEvent event) {
        for (ProductSubscriber subscriber : productSubscribers.getOrDefault(
                event.productId(), new CopyOnWriteArrayList<>())) {
            Boolean youAreLeading = subscriber.customerId() == null || event.leaderCustomerId() == null
                    ? null : subscriber.customerId().equals(event.leaderCustomerId());
            BidEvent payload = new BidEvent(event.productId(), event.bidSeq(), event.amount(), event.currentPrice(),
                    event.nextMinBid(), event.bidCount(), event.leaderAlias(), event.bidAt(), youAreLeading);
            send(subscriber.emitter(), SseEmitter.event().name("bid")
                    .id(String.valueOf(event.bidSeq())).data(payload),
                    () -> removeProduct(event.productId(), subscriber));
        }
    }

    /** 事务提交后广播结拍和站内提醒。 */
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT, fallbackExecution = true)
    public void onAuctionSettled(AuctionSettledEvent event) {
        for (ProductSubscriber subscriber : productSubscribers.getOrDefault(
                event.productId(), new CopyOnWriteArrayList<>())) {
            Boolean youWon = subscriber.customerId() == null || event.winnerCustomerId() == null
                    ? null : subscriber.customerId().equals(event.winnerCustomerId());
            SettlementEvent payload = new SettlementEvent(event.productId(), event.status(), event.finalPrice(),
                    event.winnerAlias(), event.settledAt(), youWon);
            send(subscriber.emitter(), SseEmitter.event().name("settled").id("settled").data(payload),
                    () -> removeProduct(event.productId(), subscriber));
        }
        for (AuctionNotificationResponse notification : event.notifications()) {
            NotificationSubscription subscription = notification.type().recipientRole() == NotificationRecipientRole.SELLER
                    ? new NotificationSubscription(NotificationRecipientRole.SELLER, null)
                    : new NotificationSubscription(NotificationRecipientRole.CUSTOMER, event.winnerCustomerId());
            for (SseEmitter emitter : notificationSubscribers.getOrDefault(subscription, new CopyOnWriteArrayList<>())) {
                send(emitter, SseEmitter.event().name("notification")
                        .id(String.valueOf(notification.notificationId())).data(notification),
                        () -> removeNotification(subscription, emitter));
            }
        }
    }

    /** SSE 注释心跳，防止代理或浏览器关闭长期空闲连接。 */
    @Scheduled(fixedRate = 15_000)
    public void heartbeat() {
        productSubscribers.forEach((productId, subscribers) -> {
            for (ProductSubscriber subscriber : subscribers) {
                send(subscriber.emitter(), SseEmitter.event().comment("ping"),
                        () -> removeProduct(productId, subscriber));
            }
        });
        notificationSubscribers.forEach((subscription, emitters) -> {
            for (SseEmitter emitter : emitters) {
                send(emitter, SseEmitter.event().comment("ping"),
                        () -> removeNotification(subscription, emitter));
            }
        });
    }

    private void send(SseEmitter emitter, SseEmitter.SseEventBuilder event, Runnable cleanup) {
        try {
            emitter.send(event);
        } catch (IOException | IllegalStateException ex) {
            cleanup.run();
        }
    }

    private void removeProduct(Long productId, ProductSubscriber subscriber) {
        CopyOnWriteArrayList<ProductSubscriber> list = productSubscribers.get(productId);
        if (list != null) {
            list.remove(subscriber);
            if (list.isEmpty()) productSubscribers.remove(productId, list);
        }
    }

    private void removeNotification(NotificationSubscription subscription, SseEmitter emitter) {
        CopyOnWriteArrayList<SseEmitter> list = notificationSubscribers.get(subscription);
        if (list != null) {
            list.remove(emitter);
            if (list.isEmpty()) notificationSubscribers.remove(subscription, list);
        }
    }

    public record BidCommittedEvent(Long productId, int bidSeq, BigDecimal amount, BigDecimal currentPrice,
                                    BigDecimal nextMinBid, int bidCount, String leaderAlias,
                                    Long leaderCustomerId, LocalDateTime bidAt) { }

    public record AuctionSettledEvent(Long productId, AuctionStatus status, BigDecimal finalPrice,
                                      String winnerAlias, Long winnerCustomerId, LocalDateTime settledAt,
                                      java.util.List<AuctionNotificationResponse> notifications) { }

    private record ProductSubscriber(SseEmitter emitter, Long customerId) { }
    private record NotificationSubscription(NotificationRecipientRole role, Long customerId) { }
    private record BidEvent(Long productId, int bidSeq, BigDecimal amount, BigDecimal currentPrice,
                            BigDecimal nextMinBid, int bidCount, String leaderAlias, LocalDateTime bidAt,
                            Boolean youAreLeading) { }
    private record SettlementEvent(Long productId, AuctionStatus auctionStatus, BigDecimal finalPrice,
                                   String winnerAlias, LocalDateTime settledAt, Boolean youWon) { }
}
