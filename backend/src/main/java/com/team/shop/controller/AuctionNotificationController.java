package com.team.shop.controller;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.AuctionNotificationResponse;
import com.team.shop.dto.response.AuctionNotificationPageResponse;
import com.team.shop.repository.AuctionNotificationRepository;
import com.team.shop.security.UserIdentity;
import com.team.shop.domain.NotificationRecipientRole;
import com.team.shop.exception.ForbiddenException;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.PaginationException;
import com.team.shop.service.AuctionEventHub;
import jakarta.transaction.Transactional;
import org.springframework.data.domain.PageRequest;
import org.springframework.web.bind.annotation.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.http.MediaType;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
public class AuctionNotificationController {
    private final AuctionNotificationRepository notifications;
    private final AuctionEventHub events;

    public AuctionNotificationController(AuctionNotificationRepository notifications, AuctionEventHub events) {
        this.notifications = notifications;
        this.events = events;
    }

    @GetMapping("/api/me/auction-notifications")
    public ApiResponse<AuctionNotificationPageResponse> customerNotifications(
            @AuthenticationPrincipal UserIdentity identity,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        validatePage(page, size);
        var result = notifications.findByRecipientCustomerIdOrderByCreatedAtDescIdDesc(identity.userId(),
                PageRequest.of(page - 1, size));
        return ApiResponse.ok(new AuctionNotificationPageResponse(
                result.getContent().stream().map(AuctionNotificationResponse::from).toList(),
                page, size, result.getTotalElements(), result.getTotalPages(),
                notifications.countByRecipientCustomerIdAndReadAtIsNull(identity.userId())));
    }

    @GetMapping("/api/admin/auction-notifications")
    public ApiResponse<AuctionNotificationPageResponse> sellerNotifications(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        validatePage(page, size);
        var result = notifications.findByRecipientRoleOrderByCreatedAtDescIdDesc(
                NotificationRecipientRole.SELLER, PageRequest.of(page - 1, size));
        return ApiResponse.ok(new AuctionNotificationPageResponse(
                result.getContent().stream().map(AuctionNotificationResponse::from).toList(),
                page, size, result.getTotalElements(), result.getTotalPages(),
                notifications.countByRecipientRoleAndReadAtIsNull(NotificationRecipientRole.SELLER)));
    }

    @PostMapping("/api/me/auction-notifications/{id}/read")
    @Transactional
    public ApiResponse<Void> readCustomer(@PathVariable Long id, @AuthenticationPrincipal UserIdentity identity) {
        var notification = notifications.findById(id)
                .orElseThrow(() -> new NotFoundException("提醒不存在", 40404));
        if (notification.getRecipientRole() != NotificationRecipientRole.CUSTOMER
                || notification.getRecipientCustomer() == null
                || !notification.getRecipientCustomer().getId().equals(identity.userId())) {
            throw new ForbiddenException("无权修改该提醒");
        }
        notification.markRead(com.team.shop.domain.BusinessTime.now());
        return ApiResponse.ok(null);
    }

    @PostMapping("/api/admin/auction-notifications/{id}/read")
    @Transactional
    public ApiResponse<Void> readSeller(@PathVariable Long id) {
        var notification = notifications.findById(id)
                .orElseThrow(() -> new NotFoundException("提醒不存在", 40404));
        if (notification.getRecipientRole() != NotificationRecipientRole.SELLER) {
            throw new ForbiddenException("无权修改该提醒");
        }
        notification.markRead(com.team.shop.domain.BusinessTime.now());
        return ApiResponse.ok(null);
    }

    @GetMapping(value = "/api/me/auction-notifications/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter customerStream(@AuthenticationPrincipal UserIdentity identity) {
        return events.subscribeNotifications(NotificationRecipientRole.CUSTOMER, identity.userId());
    }

    @GetMapping(value = "/api/admin/auction-notifications/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter sellerStream() {
        return events.subscribeNotifications(NotificationRecipientRole.SELLER, null);
    }

    private void validatePage(int page, int size) {
        if (page < 1 || size < 1 || size > 100) {
            throw new PaginationException("分页参数必须满足 page>=1 且 1<=size<=100");
        }
    }
}
