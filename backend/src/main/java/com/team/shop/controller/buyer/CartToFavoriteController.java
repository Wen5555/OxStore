package com.team.shop.controller.buyer;

import com.fasterxml.jackson.databind.JsonNode;
import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.MoveToFavoritesResponse;
import com.team.shop.service.CartToFavoriteService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class CartToFavoriteController {
    private final CartToFavoriteService moves;

    public CartToFavoriteController(CartToFavoriteService moves) {
        this.moves = moves;
    }

    @PostMapping("/api/me/cart/move-to-favorites")
    public ApiResponse<MoveToFavoritesResponse> move(
            @RequestBody JsonNode body,
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey) {
        MoveToFavoritesResponse result = moves.move(body, idempotencyKey);
        return ApiResponse.ok("已收藏 " + result.movedLineCount() + " 件商品", result);
    }
}
