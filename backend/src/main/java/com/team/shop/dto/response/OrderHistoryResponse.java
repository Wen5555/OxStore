package com.team.shop.dto.response;

import com.team.shop.entity.OrderHistory;

import java.time.LocalDateTime;

public record OrderHistoryResponse(Long orderId, String productName, LocalDateTime submittedAt,
                                   String status, LocalDateTime transactedAt) {
    public static OrderHistoryResponse from(OrderHistory history) {
        return new OrderHistoryResponse(history.getId(), history.getProductNameSnapshot(),
                history.getSubmittedAt(), history.getStatus().name(), history.getTransactedAt());
    }
}
