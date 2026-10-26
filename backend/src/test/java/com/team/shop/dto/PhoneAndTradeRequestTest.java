package com.team.shop.dto;

import com.team.shop.dto.request.FailAction;
import com.team.shop.dto.request.FailTradeRequest;
import com.team.shop.dto.request.RegisterRequest;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PhoneAndTradeRequestTest {
    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

    @Test
    void customerRegistrationRequiresUsernamePasswordAndPhone() {
        assertTrue(validator.validate(new RegisterRequest("buyer", "password8", "00000000000", null)).isEmpty());
        assertFalse(validator.validate(new RegisterRequest("buyer", "short", "00000000000", null)).isEmpty());
        assertFalse(validator.validate(new RegisterRequest("", "password8", "00000000000", null)).isEmpty());
        assertFalse(validator.validate(new RegisterRequest("buyer", "password8", "", null)).isEmpty());
    }

    @Test
    void tradeFailureRequiresAnActionButNoLegacyAttemptToken() {
        assertTrue(validator.validate(new FailTradeRequest(FailAction.DISCARD)).isEmpty());
        assertFalse(validator.validate(new FailTradeRequest(null)).isEmpty());
    }
}
