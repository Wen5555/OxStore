package com.team.shop.dto.response;

import com.team.shop.entity.PurchaseIntent;

import java.time.LocalDateTime;

public record IntentCreatedResponse(Long intentId, Long productId, String status, LocalDateTime createdAt) {
    public static IntentCreatedResponse from(PurchaseIntent intent) {
        return new IntentCreatedResponse(intent.getId(), intent.getProduct().getId(),
                intent.getStatus().name(), intent.getSubmittedAt());
    }
}
