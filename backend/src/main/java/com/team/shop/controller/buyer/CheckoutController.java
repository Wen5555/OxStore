package com.team.shop.controller.buyer;

import com.fasterxml.jackson.databind.JsonNode;
import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.CheckoutConfirmationResponse;
import com.team.shop.dto.response.OrderResponse;
import com.team.shop.service.CheckoutService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/me")
public class CheckoutController {
    private final CheckoutService checkout;
    public CheckoutController(CheckoutService checkout) { this.checkout = checkout; }
    @PostMapping("/checkout/confirmations")
    public ApiResponse<CheckoutConfirmationResponse> confirm(@RequestBody JsonNode body) {
        return ApiResponse.ok(checkout.confirm(body));
    }
    @PostMapping("/orders")
    public ResponseEntity<ApiResponse<OrderResponse>> submit(@RequestBody JsonNode body,
            @RequestHeader(value="Idempotency-Key",required=false) String key) {
        return ResponseEntity.status(201).body(ApiResponse.ok("下单成功",checkout.submit(body,key)));
    }
}
