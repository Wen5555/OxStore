package com.team.shop.dto.response;

import com.team.shop.entity.OrderItem;

public record OrderItemResponse(
        String productId,
        String productName,
        String unitPrice,
        String quantity,
        String lineAmount) {
    public static OrderItemResponse from(OrderItem item) {
        return new OrderItemResponse(
                item.getProduct().getId().toString(),
                item.getProductNameSnapshot(),
                item.getUnitPriceSnapshot().toPlainString(),
                item.getQuantitySnapshot().toString(),
                item.getLineAmountSnapshot().toPlainString());
    }
}
