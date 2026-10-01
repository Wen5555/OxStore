package com.team.shop.dto.request;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
public record FailTradeRequest(@NotNull(message = "action 不能为空") FailAction action,
                               @NotNull(message = "tradeAttemptId 不能为空") @Positive Long tradeAttemptId) { }
