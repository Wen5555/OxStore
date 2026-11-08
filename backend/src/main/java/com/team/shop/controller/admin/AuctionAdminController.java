package com.team.shop.controller.admin;

import com.team.shop.domain.AuctionStatus;
import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.AuctionAdminResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.service.AuctionManagementService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/admin/auctions")
public class AuctionAdminController {
    private final AuctionManagementService auctions;

    public AuctionAdminController(AuctionManagementService auctions) {
        this.auctions = auctions;
    }

    @GetMapping
    public ApiResponse<PageResponse<AuctionAdminResponse>> list(
            @RequestParam(required = false) AuctionStatus status,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.ok(auctions.list(status, page, size));
    }
}
