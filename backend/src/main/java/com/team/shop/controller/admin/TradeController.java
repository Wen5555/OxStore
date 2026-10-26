package com.team.shop.controller.admin;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.request.FailTradeRequest;
import com.team.shop.service.TradeService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin/intents")
public class TradeController {

    private final TradeService tradeService;

    public TradeController(TradeService tradeService) {
        this.tradeService = tradeService;
    }

    @PostMapping("/{id}/start")
    public ApiResponse<Void> startTrade(@PathVariable("id") Long id) {
        tradeService.startTrade(id);
        return ApiResponse.ok(null);
    }

    @PostMapping("/{id}/success")
    public ApiResponse<Void> confirmSuccess(@PathVariable("id") Long id) {
        tradeService.confirmSuccess(id);
        return ApiResponse.ok(null);
    }

    @PostMapping("/{id}/fail")
    public ApiResponse<Void> confirmFail(@PathVariable("id") Long id,
                                         @Valid @RequestBody FailTradeRequest request) {
        tradeService.confirmFail(id, request.action());
        return ApiResponse.ok(null);
    }
}
