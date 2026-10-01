package com.team.shop.exception;

/**
 * 未登录或认证失效（HTTP 401）。
 */
public class UnauthorizedException extends BizException {

    public UnauthorizedException(String message) {
        super(message);
    }
}
