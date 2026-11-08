package com.team.shop.service;

import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.ProductEventType;
import com.team.shop.domain.AuctionStatus;
import com.team.shop.dto.request.FailAction;
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
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
public class AuctionSettlementService {
    private final AuctionSessionRepository auctions;
    private final IntentRepository intents;
    private final TradeAttemptRepository attempts;
    private final AuctionNotificationRepository notifications;
    private final ProductStatusEventRepository events;

    public AuctionSettlementService(AuctionSessionRepository auctions, IntentRepository intents,
                                    TradeAttemptRepository attempts, AuctionNotificationRepository notifications,
                                    ProductStatusEventRepository events) {
        this.auctions = auctions;
        this.intents = intents;
        this.attempts = attempts;
        this.notifications = notifications;
        this.events = events;
    }

    @Scheduled(fixedDelay = 5000)
    public void scanDueAuctions() {
        LocalDateTime now = BusinessTime.now();
        for (Long id : auctions.findDueIds(AuctionStatus.LIVE, now, PageRequest.of(0, 50))) {
            settleOne(id, now);
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
            saveNotification(auction, com.team.shop.domain.AuctionNotificationType.AUCTION_UNSOLD, now);
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
        saveNotification(auction, com.team.shop.domain.AuctionNotificationType.AUCTION_SOLD, now);
        saveNotification(auction, com.team.shop.domain.AuctionNotificationType.AUCTION_WON, now);
    }

    private void saveNotification(AuctionSession auction,
                                  com.team.shop.domain.AuctionNotificationType type,
                                  LocalDateTime now) {
        if (!notifications.existsByAuctionIdAndType(auction.getId(), type)) {
            notifications.save(AuctionNotification.forSettlement(auction, type, now));
        }
    }
}
