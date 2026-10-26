package com.team.shop.controller.buyer;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.OrderHistoryResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.security.UserIdentity;
import com.team.shop.service.OrderHistoryService;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/me/order-history")
public class OrderHistoryController {
    private final OrderHistoryService histories;

    public OrderHistoryController(OrderHistoryService histories) {
        this.histories = histories;
    }

    @GetMapping
    public ApiResponse<PageResponse<OrderHistoryResponse>> getMine(
            @AuthenticationPrincipal UserIdentity identity,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.ok(histories.getCustomerHistory(identity.userId(), page, size));
    }
}
