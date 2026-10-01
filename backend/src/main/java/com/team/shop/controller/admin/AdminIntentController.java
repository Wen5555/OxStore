package com.team.shop.controller.admin;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.IntentResponse;
import com.team.shop.service.IntentService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/admin/intents")
public class AdminIntentController {

    private final IntentService intentService;

    public AdminIntentController(IntentService intentService) {
        this.intentService = intentService;
    }

    /** 队列视图：交易中意向（若有，第一位）+ 全部排队意向（需求 S-007） */
    @GetMapping
    public ApiResponse<List<IntentResponse>> queue() {
        return ApiResponse.ok(intentService.getQueue());
    }
}
