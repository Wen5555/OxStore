package com.team.shop.dto.request;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Digits;

import java.math.BigDecimal;

public record AuctionBidRequest(@NotNull @Positive @Digits(integer = 8, fraction = 2) BigDecimal amount) {
}
