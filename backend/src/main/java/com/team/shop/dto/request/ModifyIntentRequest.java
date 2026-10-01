package com.team.shop.dto.request;

import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * 买家修改意向信息请求体。对应 PUT /api/intents/{code}。
 * 姓名与电话均可选传，未传（null）的字段保持原值不变（需求 B-006：修改新姓名或电话）。
 */
public record ModifyIntentRequest(
        @Size(max = 100, message = "姓名过长")
        String buyerName,

        @Pattern(regexp = "^[0-9]{11}$", message = "联系电话须为 11 位数字")
        String buyerPhone) {
}
