package com.team.shop.dto.response;

import java.util.List;

public record MoveToFavoritesResponse(
        int movedLineCount,
        List<String> movedCartItemIds,
        List<String> skippedDeletedCartItemIds) {
}
