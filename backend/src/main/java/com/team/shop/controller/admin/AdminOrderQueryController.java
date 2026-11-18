package com.team.shop.controller.admin;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.OrderResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.security.UserIdentity;
import com.team.shop.service.OrderQueryService;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AdminOrderQueryController {
    private final OrderQueryService queries;

    public AdminOrderQueryController(OrderQueryService queries) {
        this.queries = queries;
    }

    @GetMapping("/api/admin/orders")
    public ApiResponse<PageResponse<OrderResponse>> listAll(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size,
            @AuthenticationPrincipal UserIdentity identity) {
        return ApiResponse.ok(queries.listAll(page, size, identity));
    }

    @GetMapping("/api/admin/orders/{orderId}")
    public ApiResponse<OrderResponse> getAny(
            @PathVariable Long orderId,
            @AuthenticationPrincipal UserIdentity identity) {
        return ApiResponse.ok(queries.getAny(orderId, identity));
    }
}
