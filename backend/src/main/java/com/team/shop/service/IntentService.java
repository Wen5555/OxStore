package com.team.shop.service;

import com.team.shop.dto.response.IntentCreatedResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.dto.response.QueueItemResponse;

public interface IntentService {
    IntentCreatedResponse submit(Long productId, Long customerId);
    PageResponse<QueueItemResponse> getQueue(Long productId, int page, int size);
}
