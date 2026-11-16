package com.team.shop.dto.response;

import com.team.shop.entity.Product;
import java.math.BigDecimal;
import java.math.RoundingMode;

final class CatalogResponseValues {
    private CatalogResponseValues() {
    }

    static String id(Long value) {
        return Long.toString(value);
    }

    static String money(BigDecimal value) {
        return value.setScale(2, RoundingMode.UNNECESSARY).toPlainString();
    }

    static String mainImageUrl(Product product) {
        return product.getImages().isEmpty() ? null : product.getImages().get(0).getImagePath();
    }
}
