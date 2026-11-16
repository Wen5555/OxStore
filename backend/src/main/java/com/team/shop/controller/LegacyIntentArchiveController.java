package com.team.shop.controller;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.request.ChallengeBRequestParser;
import com.team.shop.dto.response.LegacyRecordResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.service.LegacyIntentArchiveService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class LegacyIntentArchiveController {
    private final LegacyIntentArchiveService archive;

    public LegacyIntentArchiveController(LegacyIntentArchiveService archive) {
        this.archive = archive;
    }

    @GetMapping("/me/legacy-intents")
    public ApiResponse<PageResponse<LegacyRecordResponse>> customerArchive(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.ok(archive.customerArchive(page, size));
    }

    @GetMapping("/admin/legacy-intents")
    public ApiResponse<PageResponse<LegacyRecordResponse>> sellerArchive(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(required = false) String productId,
            @RequestParam(required = false) String customerId) {
        Long parsedProductId = productId == null ? null
                : ChallengeBRequestParser.parseId(productId, "商品 ID");
        Long parsedCustomerId = customerId == null ? null
                : ChallengeBRequestParser.parseId(customerId, "客户 ID");
        return ApiResponse.ok(archive.sellerArchive(page, size, parsedProductId, parsedCustomerId));
    }
}
