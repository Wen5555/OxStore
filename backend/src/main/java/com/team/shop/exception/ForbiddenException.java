package com.team.shop.exception;

/**
 * 无权限：口令码无效/已失效等（HTTP 403）。
 */
public class ForbiddenException extends BizException {

    public ForbiddenException(String message) {
        super(message);
    }
}
