package com.team.shop.exception;

/**
 * 资源不存在（HTTP 404）。
 */
public class NotFoundException extends BizException {

    public NotFoundException(String message) {
        super(message);
    }
}
