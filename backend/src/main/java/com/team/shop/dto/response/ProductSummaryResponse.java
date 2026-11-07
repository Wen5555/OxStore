package com.team.shop.dto.response;

import com.team.shop.entity.Product;
import com.team.shop.domain.SellingMode;

import java.math.BigDecimal;

public record ProductSummaryResponse(Long productId, String name, BigDecimal price, String mainImagePath,
                                     Long category2Id, String category2Name, SellingMode sellingMode,
                                     AuctionSummaryResponse auction) {
    public ProductSummaryResponse(Long productId, String name, BigDecimal price, String mainImagePath,
                                  Long category2Id, String category2Name) {
        this(productId, name, price, mainImagePath, category2Id, category2Name,
                SellingMode.FIXED_PRICE, null);
    }

    public static ProductSummaryResponse from(Product product) {
        return from(product, null);
    }

    public static ProductSummaryResponse from(Product product, com.team.shop.entity.AuctionSession auction) {
        String mainImage = product.getImages().isEmpty() ? null : product.getImages().get(0).getImagePath();
        return new ProductSummaryResponse(product.getId(), product.getName(), product.getPrice(), mainImage,
                product.getCategory().getId(), product.getCategory().getName(), product.getSellingMode(),
                auction == null ? null : AuctionSummaryResponse.from(auction));
    }
}
