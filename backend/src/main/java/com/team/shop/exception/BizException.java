package com.team.shop.exception;

/**
 * 业务异常基类。携带面向用户的中文提示信息。
 */
public class BizException extends RuntimeException {

    public BizException(String message) {
        super(message);
    }
}
