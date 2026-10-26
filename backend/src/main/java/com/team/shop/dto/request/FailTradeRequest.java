package com.team.shop.dto.request;
import jakarta.validation.constraints.NotNull;
public record FailTradeRequest(@NotNull(message = "action 不能为空") FailAction action) { }
