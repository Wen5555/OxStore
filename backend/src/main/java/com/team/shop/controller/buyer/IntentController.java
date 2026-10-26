package com.team.shop.controller.buyer;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.IntentCreatedResponse;
import com.team.shop.security.UserIdentity;
import com.team.shop.service.IntentService;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/products/{productId}/intents")
public class IntentController {
    private final IntentService intents;

    public IntentController(IntentService intents) {
        this.intents = intents;
    }

    @PostMapping
    public ApiResponse<IntentCreatedResponse> submit(@PathVariable Long productId,
                                                       @AuthenticationPrincipal UserIdentity identity) {
        return ApiResponse.ok(intents.submit(productId, identity.userId()));
    }
}
