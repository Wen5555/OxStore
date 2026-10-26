package com.team.shop.dto.request;

import jakarta.validation.constraints.NotBlank;

public record CustomerLoginRequest(@NotBlank String username, @NotBlank String password) {
}
