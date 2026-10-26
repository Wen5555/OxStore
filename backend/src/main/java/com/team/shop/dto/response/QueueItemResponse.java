package com.team.shop.dto.response;

import com.team.shop.entity.PurchaseIntent;

import java.time.LocalDateTime;

public record QueueItemResponse(Long intentId, Long productId, Long customerId, String username, String phone,
                                String status, int position, LocalDateTime submittedAt) {
    public static QueueItemResponse from(PurchaseIntent intent, int position) {
        return new QueueItemResponse(intent.getId(), intent.getProduct().getId(),
                intent.getCustomer() == null ? null : intent.getCustomer().getId(),
                intent.getBuyerName(), intent.getBuyerPhone(), intent.getStatus().name(),
                position, intent.getSubmittedAt());
    }
}
