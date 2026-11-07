package com.team.shop.dto.request;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import java.math.BigDecimal;

public record AuctionBidRequest(@NotNull @Positive BigDecimal amount) {
}
