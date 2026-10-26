package com.team.shop.dto.response;

import com.team.shop.domain.ProductStatus;
import com.team.shop.entity.Product;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

public record ProductDetailResponse(Long productId, String name, BigDecimal price, Long category2Id,
                                    String category2Name, int stock, String descriptionHtml,
                                    List<String> images, String mainImagePath, ProductStatus status,
                                    boolean canPurchase, LocalDateTime publishedAt, LocalDateTime statusUpdatedAt) {
    public static ProductDetailResponse from(Product product) {
        List<String> images = product.getImages().stream().map(image -> image.getImagePath()).toList();
        return new ProductDetailResponse(product.getId(), product.getName(), product.getPrice(),
                product.getCategory().getId(), product.getCategory().getName(), product.getStock(),
                product.getDescription(), images, images.isEmpty() ? null : images.get(0),
                product.getStatus(), product.getStatus() == ProductStatus.ONLINE,
                product.getPublishedAt(), product.getStatusUpdatedAt());
    }
}
