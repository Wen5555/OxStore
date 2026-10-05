package com.team.shop.exception;

import com.team.shop.dto.ApiResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.HttpRequestMethodNotSupportedException;

import static org.junit.jupiter.api.Assertions.assertEquals;

class GlobalExceptionHandlerBugFixTest {

    private GlobalExceptionHandler handler;

    @BeforeEach
    void setUp() {
        handler = new GlobalExceptionHandler();
    }

    /** BUG-005：错误 HTTP 方法须返回 405 而非兜底 500 */
    @Test
    void methodNotSupportedMapsTo405() {
        HttpRequestMethodNotSupportedException e =
                new HttpRequestMethodNotSupportedException("GET");
        ResponseEntity<ApiResponse<Void>> response = handler.handleMethodNotSupported(e);
        assertEquals(HttpStatus.METHOD_NOT_ALLOWED, response.getStatusCode());
        assertEquals(405, response.getBody().getCode());
        assertEquals("请求方法不支持：GET", response.getBody().getMessage());
    }
}
