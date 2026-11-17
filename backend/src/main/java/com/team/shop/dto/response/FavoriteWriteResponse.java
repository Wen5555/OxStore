package com.team.shop.dto.response;

import com.team.shop.entity.Favorite;
import java.time.LocalDateTime;

public record FavoriteWriteResponse(String favoriteId, String productId, LocalDateTime createdAt) {
    public static FavoriteWriteResponse from(Favorite favorite) {
        return new FavoriteWriteResponse(CatalogResponseValues.id(favorite.getId()),
                CatalogResponseValues.id(favorite.getProduct().getId()), favorite.getCreatedAt());
    }
}
