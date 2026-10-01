package com.team.shop.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * 修改密码请求体。对应 PUT /api/admin/auth/password。
 * 新密码强度：长度≥8位，同时包含字母、数字和特殊符号（需求 S-002）。
 */
public record ChangePasswordRequest(
        @NotBlank(message = "旧密码不能为空") String oldPassword,

        @NotBlank(message = "新密码不能为空")
        @Size(min = 8, max = 64, message = "新密码长度须在 8~64 位之间")
        @Pattern(regexp = "^(?=.*[A-Za-z])(?=.*\\d)(?=.*[^A-Za-z0-9]).+$",
                message = "新密码须同时包含字母、数字和特殊符号") String newPassword) {
}
