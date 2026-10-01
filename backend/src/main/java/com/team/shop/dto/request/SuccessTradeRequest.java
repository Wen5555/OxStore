package com.team.shop.dto.request;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
public record SuccessTradeRequest(@NotNull(message = "tradeAttemptId 不能为空")
                                  @Positive Long tradeAttemptId) { }
