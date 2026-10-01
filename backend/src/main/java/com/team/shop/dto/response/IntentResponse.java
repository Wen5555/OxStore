package com.team.shop.dto.response;

import com.team.shop.domain.IntentStatus;
import com.team.shop.entity.PurchaseIntent;

import java.time.LocalDateTime;

/**
 * 购买意向响应体。
 */
public record IntentResponse(
        Long id,
        Long productId,
        String buyerName,
        String buyerPhone,
        IntentStatus status,
        LocalDateTime submittedAt,
        Integer position,
        LocalDateTime processedAt,
        Long currentTradeAttemptId) {

    /**
     * 从实体构造。position 为该意向在队列中的位次（未排队时为 null）。
     */
    public static IntentResponse from(PurchaseIntent i, Integer position) {
        return from(i, position, null);
    }
    public static IntentResponse from(PurchaseIntent i, Integer position, Long currentTradeAttemptId) {
        return new IntentResponse(
                i.getId(),
                i.getProduct().getId(),
                i.getBuyerName(),
                i.getBuyerPhone(),
                i.getStatus(),
                i.getSubmittedAt(),
                position, i.getProcessedAt(), currentTradeAttemptId);
    }
}
