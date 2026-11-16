package com.team.shop.exception;

/** Structured business failure, including batch item errors. */
public class ApiBusinessException extends RuntimeException {
    private final int status;
    private final int code;
    private final Object data;
    public ApiBusinessException(int status, int code, String message, Object data) {
        super(message); this.status = status; this.code = code; this.data = data;
    }
    public int getStatus() { return status; }
    public int getCode() { return code; }
    public Object getData() { return data; }
}
