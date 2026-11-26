package com.team.shop.dto.response;

import com.team.shop.entity.Favorite;
import java.time.LocalDateTime;
import java.util.Optional;

public record FavoriteStateResponse(boolean favorited, LocalDateTime createdAt) {
    public static FavoriteStateResponse from(Optional<Favorite> favorite) {
        return favorite.map(value -> new FavoriteStateResponse(true, value.getCreatedAt()))
                .orElseGet(() -> new FavoriteStateResponse(false, null));
    }
}
