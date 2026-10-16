package com.team.shop.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * 买家提交购买意向请求体。对应 POST /api/intents。
 */
public record SubmitIntentRequest(
        @NotBlank(message = "姓名不能为空")
        @Size(max = 20, message = "姓名过长（最多 20 字）")
        String buyerName,

        @NotBlank(message = "电话不能为空")
        @Pattern(regexp = "^[0-9]{11}$", message = "联系电话须为 11 位数字")
        String buyerPhone) {
}
