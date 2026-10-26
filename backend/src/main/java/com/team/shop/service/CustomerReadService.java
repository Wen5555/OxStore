package com.team.shop.service;

import com.team.shop.dto.response.CustomerResponse;
import com.team.shop.dto.response.PageResponse;

public interface CustomerReadService {
    PageResponse<CustomerResponse> list(int page, int size);
}
