package com.team.shop.dto.response;
import com.team.shop.domain.*;
import com.team.shop.entity.ProductStatusEvent;
import java.time.LocalDateTime;
public record ProductStatusEventResponse(Long id, Long tradeAttemptId, ProductEventType eventType,
                                         ProductStatus fromStatus, ProductStatus toStatus,
                                         FreezeSource freezeSource, LocalDateTime occurredAt) {
    public static ProductStatusEventResponse from(ProductStatusEvent e) {
        return new ProductStatusEventResponse(e.getId(), e.getTradeAttempt() == null ? null : e.getTradeAttempt().getId(),
                e.getEventType(), e.getFromStatus(), e.getToStatus(), e.getFreezeSource(), e.getOccurredAt());
    }
}
