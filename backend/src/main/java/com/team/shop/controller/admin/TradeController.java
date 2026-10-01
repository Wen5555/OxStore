package com.team.shop.controller.admin;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.request.FailTradeRequest;
import com.team.shop.dto.request.SuccessTradeRequest;
import com.team.shop.dto.response.IntentResponse;
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
    public ApiResponse<Void> confirmSuccess(@PathVariable("id") Long id,
                                            @Valid @RequestBody SuccessTradeRequest request) {
        tradeService.confirmSuccess(id, request.tradeAttemptId());
        return ApiResponse.ok(null);
    }

    /** data 为递补后的新交易中意向（nextIntent），队列为空时为 null（架构 7.4.2） */
    @PostMapping("/{id}/fail")
    public ApiResponse<IntentResponse> confirmFail(@PathVariable("id") Long id,
                                                   @Valid @RequestBody FailTradeRequest request) {
        return ApiResponse.ok(tradeService.confirmFail(id, request.action(), request.tradeAttemptId()));
    }
}
