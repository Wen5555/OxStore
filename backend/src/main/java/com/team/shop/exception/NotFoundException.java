package com.team.shop.exception;

/**
 * 资源不存在（HTTP 404）。
 */
public class NotFoundException extends BizException {
    private final int code;

    public NotFoundException(String message) {
        this(message, 40401);
    }

    public NotFoundException(String message, int code) {
        super(message);
        this.code = code;
    }

    public int getCode() { return code; }
}
