package com.team.shop.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.OrderResponse;
import com.team.shop.security.UserIdentity;
import com.team.shop.service.OrderCancellationService;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OrderCancellationController {
    private final OrderCancellationService cancellations;

    public OrderCancellationController(OrderCancellationService cancellations) {
        this.cancellations = cancellations;
    }

    @PostMapping("/api/me/orders/{orderId}/cancel")
    public ApiResponse<OrderResponse> cancelForCustomer(@PathVariable Long orderId,
                                                         @RequestBody(required = false) JsonNode body) {
        return ApiResponse.ok(cancellations.cancelForCustomer(orderId, body));
    }

    @PostMapping("/api/admin/orders/{orderId}/cancel")
    public ApiResponse<OrderResponse> cancelForSeller(@PathVariable Long orderId,
                                                       @RequestBody(required = false) JsonNode body,
                                                       @AuthenticationPrincipal UserIdentity identity) {
        return ApiResponse.ok(cancellations.cancelForSeller(orderId, body, identity));
    }
}
