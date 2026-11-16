package com.team.shop.dto.response;

import com.team.shop.domain.ProductStatus;
import com.team.shop.entity.CartItem;

import java.time.LocalDateTime;

public record CartItemResponse(String cartItemId, String productId, String productName, String unitPrice,
                               String mainImageUrl, String quantity, String stock, boolean online,
                               String invalidLabel, boolean defaultCheckoutSelected,
                               boolean canCheckoutSelect, boolean canFavoriteSelect, LocalDateTime updatedAt) {
    public static CartItemResponse from(CartItem item) {
        var product = item.getProduct();
        boolean online = product.getStatus() == ProductStatus.ONLINE;
        boolean fixedPrice = !product.isAuction();
        boolean selectable = online && fixedPrice;
        boolean enoughStock = item.getQuantity().compareTo(product.getStock()) <= 0;
        return new CartItemResponse(CatalogResponseValues.id(item.getId()),
                CatalogResponseValues.id(product.getId()), product.getName(),
                CatalogResponseValues.money(product.getPrice()), CatalogResponseValues.mainImageUrl(product),
                item.getQuantity().toString(), product.getStock().toString(), online,
                online ? null : "已下架", selectable && enoughStock, selectable, selectable, item.getUpdatedAt());
    }
}
