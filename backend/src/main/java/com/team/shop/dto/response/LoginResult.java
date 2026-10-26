package com.team.shop.dto.response;

/**
 * 登录响应：JWT + 用户名。
 */
public record LoginResult(String token, Long userId, String role, String username) {
}
