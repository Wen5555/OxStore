package com.team.shop.dto.response;
import com.team.shop.domain.TradeResult;
import com.team.shop.dto.request.FailAction;
import com.team.shop.entity.TradeAttempt;
import java.time.LocalDateTime;
public record TradeAttemptResponse(Long id, Long intentId, LocalDateTime startedAt,
                                   LocalDateTime finishedAt, TradeResult result, FailAction failAction) {
    public static TradeAttemptResponse from(TradeAttempt a) {
        return new TradeAttemptResponse(a.getId(), a.getIntent().getId(), a.getStartedAt(),
                a.getFinishedAt(), a.getResult(), a.getFailAction());
    }
}
