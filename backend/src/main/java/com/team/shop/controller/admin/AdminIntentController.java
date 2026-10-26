package com.team.shop.controller.admin;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.dto.response.QueueItemResponse;
import com.team.shop.service.IntentService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin/intents")
public class AdminIntentController {
    private final IntentService intents;

    public AdminIntentController(IntentService intents) {
        this.intents = intents;
    }

    @GetMapping
    public ApiResponse<PageResponse<QueueItemResponse>> queue(
            @RequestParam Long productId,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.ok(intents.getQueue(productId, page, size));
    }
}
