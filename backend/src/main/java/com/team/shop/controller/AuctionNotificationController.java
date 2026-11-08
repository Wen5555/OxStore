package com.team.shop.controller;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.AuctionNotificationResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.entity.AuctionNotification;
import com.team.shop.repository.AuctionNotificationRepository;
import com.team.shop.security.UserIdentity;
import jakarta.transaction.Transactional;
import org.springframework.data.domain.PageRequest;
import org.springframework.web.bind.annotation.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;

@RestController
public class AuctionNotificationController {
    private final AuctionNotificationRepository notifications;

    public AuctionNotificationController(AuctionNotificationRepository notifications) {
        this.notifications = notifications;
    }

    @GetMapping("/api/me/auction-notifications")
    public ApiResponse<PageResponse<AuctionNotificationResponse>> customerNotifications(
            @AuthenticationPrincipal UserIdentity identity,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        var result = notifications.findByRecipientCustomerIdOrderByCreatedAtDescIdDesc(identity.userId(),
                PageRequest.of(page - 1, size));
        return ApiResponse.ok(new PageResponse<>(result.getContent().stream().map(AuctionNotificationResponse::from).toList(),
                page, size, result.getTotalElements(), result.getTotalPages()));
    }

    @GetMapping("/api/admin/auction-notifications")
    public ApiResponse<PageResponse<AuctionNotificationResponse>> sellerNotifications(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        var result = notifications.findByRecipientRoleOrderByCreatedAtDescIdDesc(
                com.team.shop.domain.NotificationRecipientRole.SELLER, PageRequest.of(page - 1, size));
        return ApiResponse.ok(new PageResponse<>(result.getContent().stream().map(AuctionNotificationResponse::from).toList(),
                page, size, result.getTotalElements(), result.getTotalPages()));
    }

    @PostMapping("/api/me/auction-notifications/{id}/read")
    @Transactional
    public ApiResponse<Void> readCustomer(@PathVariable Long id, @AuthenticationPrincipal UserIdentity identity) {
        notifications.findByIdAndRecipientCustomerId(id, identity.userId()).ifPresent(n -> n.markRead(com.team.shop.domain.BusinessTime.now()));
        return ApiResponse.ok(null);
    }
}
