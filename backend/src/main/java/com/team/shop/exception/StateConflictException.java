package com.team.shop.exception;

/**
 * 状态冲突：违反状态机不变量或非法状态迁移（HTTP 409）。
 */
public class StateConflictException extends BizException {

    public StateConflictException(String message) {
        super(message);
    }
}
