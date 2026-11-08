package com.team.shop.service;

import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.ProductEventType;
import com.team.shop.domain.AuctionStatus;
import com.team.shop.entity.AuctionNotification;
import com.team.shop.entity.AuctionSession;
import com.team.shop.entity.ProductStatusEvent;
import com.team.shop.entity.PurchaseIntent;
import com.team.shop.entity.TradeAttempt;
import com.team.shop.exception.NotFoundException;
import com.team.shop.repository.AuctionNotificationRepository;
import com.team.shop.repository.AuctionSessionRepository;
import com.team.shop.repository.IntentRepository;
import com.team.shop.repository.ProductStatusEventRepository;
import com.team.shop.repository.TradeAttemptRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.transaction.PlatformTransactionManager;

import java.time.LocalDateTime;

@Service
public class AuctionSettlementService {
    private final AuctionSessionRepository auctions;
    private final IntentRepository intents;
    private final TradeAttemptRepository attempts;
    private final AuctionNotificationRepository notifications;
    private final ProductStatusEventRepository events;
    private final ApplicationEventPublisher eventPublisher;
    private final TransactionTemplate transactionTemplate;

    public AuctionSettlementService(AuctionSessionRepository auctions, IntentRepository intents,
                                    TradeAttemptRepository attempts, AuctionNotificationRepository notifications,
                                    ProductStatusEventRepository events,
                                    ApplicationEventPublisher eventPublisher,
                                    PlatformTransactionManager transactionManager) {
        this.auctions = auctions;
        this.intents = intents;
        this.attempts = attempts;
        this.notifications = notifications;
        this.events = events;
        this.eventPublisher = eventPublisher;
        this.transactionTemplate = new TransactionTemplate(transactionManager);
    }

    @Scheduled(fixedDelay = 5000)
    public void scanDueAuctions() {
        LocalDateTime now = BusinessTime.now();
        for (Long id : auctions.findDueIds(AuctionStatus.LIVE, now, PageRequest.of(0, 50))) {
            transactionTemplate.executeWithoutResult(status -> settleOne(id, now));
        }
    }

    @Transactional
    public void settleOne(Long auctionId, LocalDateTime now) {
        AuctionSession auction = auctions.findByIdForUpdate(auctionId)
                .orElseThrow(() -> new NotFoundException("拍卖不存在", 40401));
        if (!auction.isDueAt(now)) return;
        if (auction.getBidCount() == 0) {
            var product = auction.getProduct();
            var before = product.getStatus();
            auction.markUnsold(now);
            product.takeOffline(now);
            events.save(new ProductStatusEvent(product, null, ProductEventType.AUCTION_UNSOLD, before, now));
            var notification = saveNotification(auction, com.team.shop.domain.AuctionNotificationType.AUCTION_UNSOLD, now);
            eventPublisher.publishEvent(new AuctionEventHub.AuctionSettledEvent(
                    product.getId(), auction.getStatus(), null, null, null, now,
                    java.util.List.of(notification)));
            return;
        }
        var product = auction.getProduct();
        var before = product.getStatus();
        product.startTrade(now);
        PurchaseIntent intent = PurchaseIntent.createAuctionWinner(product, auction.getLeader(), now);
        intents.saveAndFlush(intent);
        TradeAttempt attempt = attempts.save(new TradeAttempt(intent, now));
        auction.markSold(intent, now);
        events.save(new ProductStatusEvent(product, attempt, ProductEventType.TRADE_STARTED, before, now));
        var sellerNotification = saveNotification(auction,
                com.team.shop.domain.AuctionNotificationType.AUCTION_SOLD, now);
        var winnerNotification = saveNotification(auction,
                com.team.shop.domain.AuctionNotificationType.AUCTION_WON, now);
        eventPublisher.publishEvent(new AuctionEventHub.AuctionSettledEvent(
                product.getId(), auction.getStatus(), auction.getCurrentPrice(),
                alias(auction.getLeader().getUsername()), auction.getLeader().getId(), now,
                java.util.List.of(sellerNotification, winnerNotification)));
    }

    private com.team.shop.dto.response.AuctionNotificationResponse saveNotification(
            AuctionSession auction, com.team.shop.domain.AuctionNotificationType type, LocalDateTime now) {
        AuctionNotification notification = notifications.findByAuctionIdAndType(auction.getId(), type)
                .orElseGet(() -> notifications.saveAndFlush(
                        AuctionNotification.forSettlement(auction, type, now)));
        return com.team.shop.dto.response.AuctionNotificationResponse.from(notification);
    }

    private static String alias(String username) {
        if (username == null || username.length() <= 1) return "*";
        return username.charAt(0) + "***" + username.charAt(username.length() - 1);
    }
}
