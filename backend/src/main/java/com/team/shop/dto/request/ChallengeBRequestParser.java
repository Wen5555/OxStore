package com.team.shop.dto.request;

import com.fasterxml.jackson.databind.JsonNode;
import com.team.shop.exception.ApiBusinessException;
import com.team.shop.exception.BizException;
import com.team.shop.exception.NotFoundException;

import java.math.BigInteger;
import java.util.Arrays;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

public final class ChallengeBRequestParser {
    private static final Pattern POSITIVE_ID = Pattern.compile("[1-9][0-9]*");
    private static final Pattern NON_NEGATIVE_INTEGER = Pattern.compile("(0|[1-9][0-9]*)");
    private static final Pattern UUID_PATTERN = Pattern.compile(
            "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}");

    private ChallengeBRequestParser() {
    }

    public static void requireObjectWithFields(JsonNode body, String... allowedFields) {
        if (body == null || !body.isObject()) {
            throw badRequest(40002, "请求体格式不正确");
        }
        Set<String> allowed = Set.copyOf(Arrays.asList(allowedFields));
        body.fieldNames().forEachRemaining(field -> {
            if (!allowed.contains(field)) {
                throw badRequest(40002, "请求包含未知字段");
            }
        });
    }

    public static String requireTextField(JsonNode body, String field) {
        JsonNode value = body.get(field);
        if (value == null || value.isNull()) {
            throw badRequest(40001, "缺少必填请求字段");
        }
        if (!value.isTextual()) {
            throw badRequest(40002, "请求字段格式不正确");
        }
        return value.textValue();
    }

    public static Long parseId(String value, String label) {
        if (value == null || !POSITIVE_ID.matcher(value).matches()) {
            throw badRequest(40002, label + "格式不正确");
        }
        try {
            return Long.parseLong(value);
        } catch (NumberFormatException e) {
            throw new NotFoundException(label + "不存在");
        }
    }

    public static BigInteger parseNonNegativeInteger(String value) {
        if (value == null || !NON_NEGATIVE_INTEGER.matcher(value).matches()) {
            throw new BizException("数量无效，请输入正整数");
        }
        return new BigInteger(value);
    }

    public static String requireIdempotencyKey(String value) {
        if (value == null || !UUID_PATTERN.matcher(value).matches()) {
            throw badRequest(40001, "Idempotency-Key 必须为 UUID");
        }
        return UUID.fromString(value).toString();
    }

    private static ApiBusinessException badRequest(int code, String message) {
        return new ApiBusinessException(400, code, message, null);
    }
}
