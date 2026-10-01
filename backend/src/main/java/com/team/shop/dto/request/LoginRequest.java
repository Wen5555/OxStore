package com.team.shop.dto.request;

import jakarta.validation.constraints.NotBlank;

/**
 * 卖家登录请求体。对应 POST /api/admin/auth/login。
 */
public record LoginRequest(
        @NotBlank(message = "用户名不能为空") String username,
        @NotBlank(message = "密码不能为空") String password) {
}
