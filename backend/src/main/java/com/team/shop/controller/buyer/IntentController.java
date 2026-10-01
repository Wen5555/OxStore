package com.team.shop.controller.buyer;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.request.ModifyIntentRequest;
import com.team.shop.dto.request.SubmitIntentRequest;
import com.team.shop.dto.response.IntentResponse;
import com.team.shop.dto.response.SubmitIntentResult;
import com.team.shop.service.IntentService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/intents")
public class IntentController {

    private final IntentService intentService;

    public IntentController(IntentService intentService) {
        this.intentService = intentService;
    }

    @PostMapping
    public ApiResponse<SubmitIntentResult> submit(@Valid @RequestBody SubmitIntentRequest request) {
        return ApiResponse.ok(intentService.submit(request.buyerName(), request.buyerPhone()));
    }

    @GetMapping("/{code}")
    public ApiResponse<IntentResponse> query(@PathVariable("code") String code) {
        return ApiResponse.ok(intentService.queryByToken(code));
    }

    /** 姓名与电话均可选传；未传字段保持原值 */
    @PutMapping("/{code}")
    public ApiResponse<IntentResponse> modify(@PathVariable("code") String code,
                                              @Valid @RequestBody ModifyIntentRequest request) {
        return ApiResponse.ok(intentService.modifyByToken(code, request.buyerName(), request.buyerPhone()));
    }

    @DeleteMapping("/{code}")
    public ApiResponse<Void> cancel(@PathVariable("code") String code) {
        intentService.cancelByToken(code);
        return ApiResponse.ok(null);
    }
}
