package com.team.shop.controller.admin;

import com.fasterxml.jackson.databind.JsonNode;
import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.OrderResponse;
import com.team.shop.security.UserIdentity;
import com.team.shop.service.OrderCommandService;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

@RestController
public class AdminOrderCommandController {
    private final OrderCommandService commands;
    public AdminOrderCommandController(OrderCommandService commands) { this.commands = commands; }
    @PostMapping("/api/admin/orders/{orderId}/actions")
    public ApiResponse<OrderResponse> advance(@PathVariable Long orderId, @RequestBody JsonNode body,
                                             @AuthenticationPrincipal UserIdentity identity) {
        return ApiResponse.ok(commands.advance(orderId,body,identity));
    }
}
