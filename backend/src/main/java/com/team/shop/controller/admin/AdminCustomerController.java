package com.team.shop.controller.admin;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.CustomerResponse;
import com.team.shop.dto.response.OrderHistoryResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.service.CustomerReadService;
import com.team.shop.service.OrderHistoryService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin/customers")
public class AdminCustomerController {
    private final CustomerReadService customers;
    private final OrderHistoryService histories;

    public AdminCustomerController(CustomerReadService customers, OrderHistoryService histories) {
        this.customers = customers;
        this.histories = histories;
    }

    @GetMapping
    public ApiResponse<PageResponse<CustomerResponse>> list(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.ok(customers.list(page, size));
    }

    @GetMapping("/{customerId}/order-history")
    public ApiResponse<PageResponse<OrderHistoryResponse>> history(
            @PathVariable Long customerId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.ok(histories.getSellerCustomerHistory(customerId, page, size));
    }
}
