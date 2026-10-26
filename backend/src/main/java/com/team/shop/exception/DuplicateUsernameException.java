package com.team.shop.exception;

public class DuplicateUsernameException extends StateConflictException {
    public DuplicateUsernameException(String message) {
        super(message);
    }
}
