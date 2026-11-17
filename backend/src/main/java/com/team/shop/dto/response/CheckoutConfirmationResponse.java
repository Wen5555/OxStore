package com.team.shop.dto.response;

import com.team.shop.entity.CheckoutConfirmation;
import java.util.List;

public record CheckoutConfirmationResponse(String confirmationToken, List<Item> items,
                                            String totalAmount, String createdAt) {
    public record Item(String cartItemId, String productId, String productName, String unitPrice,
                       String quantity, String lineAmount) { }
    public static CheckoutConfirmationResponse from(CheckoutConfirmation confirmation) {
        return new CheckoutConfirmationResponse(confirmation.getToken(), confirmation.getItems().stream()
                .map(i -> new Item(i.getCartItemId().toString(), i.getProduct().getId().toString(),
                        i.getProduct().getName(), i.getUnitPrice().toPlainString(), i.getQuantity().toString(),
                        i.getUnitPrice().multiply(new java.math.BigDecimal(i.getQuantity())).toPlainString())).toList(),
                confirmation.getTotalAmount().toPlainString(), confirmation.getCreatedAt().toString());
    }
}
