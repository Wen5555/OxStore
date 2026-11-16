package com.team.shop.dto.response;

import com.team.shop.domain.OrderStatus;
import com.team.shop.entity.ShopOrder;

import java.util.Comparator;
import java.util.List;

public record OrderResponse(
        String orderId,
        String orderNo,
        String customerId,
        OrderStatus status,
        List<OrderItemResponse> items,
        String totalAmount,
        String createdAt,
        String cancelledBy,
        String cancelledAt,
        String cancelReason,
        List<String> allowedActions) {

    public static OrderResponse from(ShopOrder order, boolean sellerView) {
        return new OrderResponse(
                order.getId().toString(),
                order.getOrderNo(),
                order.getCustomer().getId().toString(),
                order.getStatus(),
                order.getItems().stream()
                        .sorted(Comparator.comparing(item -> item.getProduct().getId()))
                        .map(OrderItemResponse::from)
                        .toList(),
                order.getTotalAmount().toPlainString(),
                order.getCreatedAt().toString(),
                order.getCancelledBy() == null ? null : order.getCancelledBy().name(),
                order.getCancelledAt() == null ? null : order.getCancelledAt().toString(),
                order.getCancelReason(),
                allowedActions(order.getStatus(), sellerView));
    }

    private static List<String> allowedActions(OrderStatus status, boolean sellerView) {
        if (status == OrderStatus.CANCELLED || status == OrderStatus.COMPLETED) {
            return List.of();
        }
        if (!sellerView) {
            return status == OrderStatus.SHIPPED ? List.of() : List.of("CANCEL");
        }
        return switch (status) {
            case PLACED -> List.of("CONFIRM", "CANCEL");
            case CONFIRMED -> List.of("PREPARE", "CANCEL");
            case PREPARED -> List.of("SHIP", "CANCEL");
            case SHIPPED -> List.of("COMPLETE", "CANCEL");
            case COMPLETED, CANCELLED -> List.of();
        };
    }
}
