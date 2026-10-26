package com.team.shop.exception;

/**
 * 状态冲突：违反状态机不变量或非法状态迁移（HTTP 409）。
 */
public class StateConflictException extends BizException {
    private final int code;

    public StateConflictException(String message) {
        this(message, 40901);
    }

    public StateConflictException(String message, int code) {
        super(message);
        this.code = code;
    }

    public int getCode() { return code; }
}
