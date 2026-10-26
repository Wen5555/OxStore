package com.team.shop.service;

import com.team.shop.dto.response.OrderHistoryResponse;
import com.team.shop.dto.response.PageResponse;

public interface OrderHistoryService {
    PageResponse<OrderHistoryResponse> getCustomerHistory(Long customerId, int page, int size);
    PageResponse<OrderHistoryResponse> getSellerCustomerHistory(Long customerId, int page, int size);
}
