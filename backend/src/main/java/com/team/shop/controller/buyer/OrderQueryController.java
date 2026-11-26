package com.team.shop.controller.buyer;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.OrderResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.service.OrderQueryService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OrderQueryController {
    private final OrderQueryService queries;

    public OrderQueryController(OrderQueryService queries) {
        this.queries = queries;
    }

    @GetMapping("/api/me/orders")
    public ApiResponse<PageResponse<OrderResponse>> listMine(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.ok(queries.listMine(page, size));
    }

    @GetMapping("/api/me/orders/{orderId}")
    public ApiResponse<OrderResponse> getMine(@PathVariable Long orderId) {
        return ApiResponse.ok(queries.getMine(orderId));
    }
}
