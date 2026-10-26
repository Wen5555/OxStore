package com.team.shop.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record RegisterRequest(
        @NotBlank @Size(max = 50) String username,
        @NotBlank @Size(min = 8, max = 64) String password,
        @NotBlank @Size(max = 20) String phone,
        @Size(max = 200) String location) {
}
