package com.team.shop.dto.response;

import com.team.shop.domain.ProductStatus;
import com.team.shop.entity.Favorite;

import java.time.LocalDateTime;

public record FavoriteItemResponse(String favoriteId, String productId, String productName, String unitPrice,
                                   String mainImageUrl, LocalDateTime createdAt, boolean valid,
                                   String invalidLabel, boolean canOpenDetail) {
    public static FavoriteItemResponse from(Favorite favorite) {
        var product = favorite.getProduct();
        boolean valid = !product.isAuction() && product.getStatus() == ProductStatus.ONLINE;
        return new FavoriteItemResponse(CatalogResponseValues.id(favorite.getId()),
                CatalogResponseValues.id(product.getId()), product.getName(),
                CatalogResponseValues.money(product.getPrice()), CatalogResponseValues.mainImageUrl(product),
                favorite.getCreatedAt(), valid, valid ? null : "已下架", valid);
    }
}
