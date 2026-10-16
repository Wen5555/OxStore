package com.team.shop.dto;
import com.team.shop.dto.request.*;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class PhoneAndTradeRequestTest {
    private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();
    @Test void acceptsAnyElevenDigitsButRejectsMalformedNumbers() {
        assertTrue(validator.validate(new SubmitIntentRequest("买家", "00000000000")).isEmpty());
        for (String phone : new String[]{"123", "123456789012", "0000000000x"}) {
            assertFalse(validator.validate(new SubmitIntentRequest("买家", phone)).isEmpty());
        }
        assertTrue(validator.validate(new ModifyIntentRequest(null, null)).isEmpty());
        assertFalse(validator.validate(new ModifyIntentRequest(null, "")).isEmpty());
    }

    /** BUG-006：几十字超长姓名须被拦截，正常长度放行（提交与修改两个入口同限） */
    @Test void overlongBuyerNameIsRejected() {
        assertTrue(validator.validate(new SubmitIntentRequest("张三", "00000000000")).isEmpty());
        String longName = "赵".repeat(30);
        assertFalse(validator.validate(new SubmitIntentRequest(longName, "00000000000")).isEmpty());
        assertFalse(validator.validate(new ModifyIntentRequest(longName, null)).isEmpty());
    }
    @Test void tradeAttemptIdRequiredForConfirmations() {
        assertFalse(validator.validate(new SuccessTradeRequest(null)).isEmpty());
        assertFalse(validator.validate(new FailTradeRequest(FailAction.DISCARD, null)).isEmpty());
        assertTrue(validator.validate(new FailTradeRequest(FailAction.REQUEUE, 8L)).isEmpty());
    }
}
