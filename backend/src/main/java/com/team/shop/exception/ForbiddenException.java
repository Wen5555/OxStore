package com.team.shop.exception;

/**
 * 当前身份无权执行请求（HTTP 403）。
 */
public class ForbiddenException extends BizException {

    public ForbiddenException(String message) {
        super(message);
    }
}
