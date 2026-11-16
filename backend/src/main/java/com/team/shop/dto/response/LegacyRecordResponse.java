package com.team.shop.dto.response;

import com.team.shop.entity.PurchaseIntent;

import java.time.LocalDateTime;

public record LegacyRecordResponse(String legacyIntentId, String productId, String productNameSnapshot,
                                   String originalStatus, LocalDateTime submittedAt, LocalDateTime processedAt,
                                   LocalDateTime closedAt, String displayStatus, boolean readOnly) {
    public static LegacyRecordResponse from(PurchaseIntent intent) {
        String originalStatus = intent.getStatus().name();
        String snapshot = intent.getProductNameSnapshot();
        return new LegacyRecordResponse(Long.toString(intent.getId()),
                Long.toString(intent.getProduct().getId()), snapshot == null ? "" : snapshot, originalStatus,
                intent.getSubmittedAt(), intent.getProcessedAt(), intent.getLegacyClosedAt(),
                intent.isLegacyClosed() ? "CLOSED" : originalStatus, true);
    }
}
