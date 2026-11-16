package com.team.shop.dto.response;

import java.util.List;

public record CartResponse(List<CartItemResponse> items) {
    public CartResponse {
        items = List.copyOf(items);
    }
}
