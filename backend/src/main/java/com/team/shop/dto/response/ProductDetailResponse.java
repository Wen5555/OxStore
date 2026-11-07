package com.team.shop.dto.response;

import com.team.shop.domain.ProductStatus;
import com.team.shop.domain.SellingMode;
import com.team.shop.entity.Product;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

public record ProductDetailResponse(Long productId, String name, BigDecimal price, Long category2Id,
                                    String category2Name, int stock, String descriptionHtml,
                                    List<String> images, String mainImagePath, ProductStatus status,
                                    boolean canPurchase, LocalDateTime publishedAt, LocalDateTime statusUpdatedAt,
                                    SellingMode sellingMode, AuctionSummaryResponse auction) {
    public ProductDetailResponse(Long productId, String name, BigDecimal price, Long category2Id,
                                 String category2Name, int stock, String descriptionHtml,
                                 List<String> images, String mainImagePath, ProductStatus status,
                                 boolean canPurchase, LocalDateTime publishedAt, LocalDateTime statusUpdatedAt) {
        this(productId, name, price, category2Id, category2Name, stock, descriptionHtml, images, mainImagePath,
                status, canPurchase, publishedAt, statusUpdatedAt, SellingMode.FIXED_PRICE, null);
    }

    public static ProductDetailResponse from(Product product) {
        return from(product, null);
    }

    public static ProductDetailResponse from(Product product, com.team.shop.entity.AuctionSession auction) {
        List<String> images = product.getImages().stream().map(image -> image.getImagePath()).toList();
        return new ProductDetailResponse(product.getId(), product.getName(), product.getPrice(),
                product.getCategory().getId(), product.getCategory().getName(), product.getStock(),
                product.getDescription(), images, images.isEmpty() ? null : images.get(0),
                product.getStatus(), product.getStatus() == ProductStatus.ONLINE && !product.isAuction(),
                product.getPublishedAt(), product.getStatusUpdatedAt(), product.getSellingMode(),
                auction == null ? null : AuctionSummaryResponse.from(auction));
    }
}
