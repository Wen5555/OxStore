package com.team.shop.service;

import com.team.shop.dto.response.AuctionBidResponse;
import com.team.shop.entity.AuctionBid;
import com.team.shop.entity.AuctionSession;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Component
public class AuctionEventHub {
    private final Map<Long, CopyOnWriteArrayList<SseEmitter>> subscribers = new ConcurrentHashMap<>();

    public SseEmitter subscribe(Long productId) {
        SseEmitter emitter = new SseEmitter(30 * 60 * 1000L);
        subscribers.computeIfAbsent(productId, ignored -> new CopyOnWriteArrayList<>()).add(emitter);
        Runnable cleanup = () -> remove(productId, emitter);
        emitter.onCompletion(cleanup);
        emitter.onTimeout(cleanup);
        emitter.onError(ignored -> cleanup.run());
        return emitter;
    }

    public void publishBid(AuctionSession auction, AuctionBid bid) {
        BidEvent payload = new BidEvent(auction.getProduct().getId(), bid.getBidSeq(), bid.getAmount(),
                auction.getCurrentPrice(), auction.nextMinimumBid(), auction.getBidCount(),
                alias(bid.getCustomer().getUsername()), bid.getBidAt());
        for (SseEmitter emitter : subscribers.getOrDefault(auction.getProduct().getId(), new CopyOnWriteArrayList<>())) {
            try {
                emitter.send(SseEmitter.event().name("bid").id(String.valueOf(bid.getBidSeq())).data(payload));
            } catch (IOException ex) {
                remove(auction.getProduct().getId(), emitter);
            }
        }
    }

    private static String alias(String username) {
        if (username == null || username.length() <= 1) return "*";
        return username.charAt(0) + "***" + username.charAt(username.length() - 1);
    }

    private record BidEvent(Long productId, int bidSeq, BigDecimal amount, BigDecimal currentPrice,
                            BigDecimal nextMinBid, int bidCount, String leaderAlias, LocalDateTime bidAt) { }

    private void remove(Long productId, SseEmitter emitter) {
        CopyOnWriteArrayList<SseEmitter> list = subscribers.get(productId);
        if (list != null) {
            list.remove(emitter);
            if (list.isEmpty()) subscribers.remove(productId, list);
        }
    }
}
