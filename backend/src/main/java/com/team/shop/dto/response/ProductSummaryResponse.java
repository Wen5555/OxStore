package com.team.shop.dto.response;

import com.team.shop.entity.Product;

import java.math.BigDecimal;

public record ProductSummaryResponse(Long productId, String name, BigDecimal price, String mainImagePath,
                                     Long category2Id, String category2Name) {
    public static ProductSummaryResponse from(Product product) {
        String mainImage = product.getImages().isEmpty() ? null : product.getImages().get(0).getImagePath();
        return new ProductSummaryResponse(product.getId(), product.getName(), product.getPrice(), mainImage,
                product.getCategory().getId(), product.getCategory().getName());
    }
}
