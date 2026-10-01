package com.team.shop.dto.response;

import com.team.shop.domain.FreezeSource;
import com.team.shop.domain.ProductStatus;
import com.team.shop.entity.Product;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 商品响应体。买家可见（不含内部管理字段）。
 */
public record ProductResponse(
        Long id,
        String name,
        String description,
        String imagePath,
        BigDecimal price,
        ProductStatus status,
        FreezeSource freezeSource,
        LocalDateTime publishedAt,
        LocalDateTime soldAt,
        LocalDateTime statusUpdatedAt) {

    public static ProductResponse from(Product p) {
        return new ProductResponse(
                p.getId(),
                p.getName(),
                p.getDescription(),
                p.getImagePath(),
                p.getPrice(),
                p.getStatus(),
                p.getFreezeSource(),
                p.getPublishedAt(),
                p.getSoldAt(), p.getStatusUpdatedAt());
    }
}
