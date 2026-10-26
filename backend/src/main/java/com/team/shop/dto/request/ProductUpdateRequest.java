package com.team.shop.dto.request;

import jakarta.validation.constraints.PositiveOrZero;

public record ProductUpdateRequest(@PositiveOrZero Integer stock, Long category2Id) {
    public boolean hasChanges() {
        return stock != null || category2Id != null;
    }
}
