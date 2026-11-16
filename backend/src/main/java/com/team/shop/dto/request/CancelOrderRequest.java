package com.team.shop.dto.request;

import com.fasterxml.jackson.databind.JsonNode;
import com.team.shop.domain.OrderStatus;
import com.team.shop.exception.ApiBusinessException;

public record CancelOrderRequest(OrderStatus expectedStatus, String reason) {
    public static CancelOrderRequest parse(JsonNode body) {
        if (body != null && body.isObject() && (body.has("items") || body.has("itemIds"))) {
            throw new ApiBusinessException(400, 40004, "不支持部分取消", null);
        }
        ChallengeBRequestParser.requireObjectWithFields(body, "expectedStatus", "reason");

        String statusText = ChallengeBRequestParser.requireTextField(body, "expectedStatus");
        OrderStatus expectedStatus;
        try {
            expectedStatus = OrderStatus.valueOf(statusText);
        } catch (IllegalArgumentException e) {
            throw new ApiBusinessException(400, 40002, "expectedStatus格式不正确", null);
        }

        JsonNode reasonNode = body.get("reason");
        String reason = null;
        if (reasonNode != null) {
            if (!reasonNode.isTextual()) {
                throw new ApiBusinessException(400, 40002, "reason格式不正确", null);
            }
            reason = reasonNode.textValue();
            if (reason.length() > 500) {
                throw new ApiBusinessException(400, 40002, "reason长度不能超过500个字符", null);
            }
        }
        return new CancelOrderRequest(expectedStatus, reason);
    }
}
