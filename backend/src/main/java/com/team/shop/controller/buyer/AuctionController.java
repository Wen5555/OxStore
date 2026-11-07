package com.team.shop.controller.buyer;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.request.AuctionBidRequest;
import com.team.shop.dto.response.AuctionBidResponse;
import com.team.shop.dto.response.AuctionSnapshotResponse;
import com.team.shop.security.UserIdentity;
import com.team.shop.service.AuctionEventHub;
import com.team.shop.service.AuctionService;
import jakarta.validation.Valid;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.springframework.security.core.annotation.AuthenticationPrincipal;

@RestController
@RequestMapping("/api/products/{productId}/auction")
public class AuctionController {
    private final AuctionService auctions;
    private final AuctionEventHub events;

    public AuctionController(AuctionService auctions, AuctionEventHub events) {
        this.auctions = auctions;
        this.events = events;
    }

    @GetMapping
    public ApiResponse<AuctionSnapshotResponse> snapshot(@PathVariable Long productId,
                                                         @AuthenticationPrincipal UserIdentity identity) {
        return ApiResponse.ok(auctions.snapshot(productId, identity));
    }

    @PostMapping("/bids")
    public ApiResponse<AuctionBidResponse> bid(@PathVariable Long productId,
                                               @AuthenticationPrincipal UserIdentity identity,
                                               @Valid @RequestBody AuctionBidRequest request) {
        return ApiResponse.ok(auctions.placeBid(productId, identity.userId(), request.amount()));
    }

    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter stream(@PathVariable Long productId,
                             @AuthenticationPrincipal UserIdentity identity) {
        SseEmitter emitter = events.subscribe(productId);
        try {
            emitter.send(SseEmitter.event().name("snapshot").data(auctions.snapshot(productId, identity)));
        } catch (Exception ex) {
            emitter.completeWithError(ex);
        }
        return emitter;
    }
}
