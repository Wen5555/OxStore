package com.team.shop.exception;

public class AuthenticationFailureException extends UnauthorizedException {
    public AuthenticationFailureException(String message) {
        super(message);
    }
}
