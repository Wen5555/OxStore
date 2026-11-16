package com.team.shop.controller.buyer;

import com.fasterxml.jackson.databind.JsonNode;
import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.request.ChallengeBRequestParser;
import com.team.shop.dto.response.CartItemResponse;
import com.team.shop.dto.response.CartResponse;
import com.team.shop.service.CartService;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.math.BigInteger;

@RestController
@RequestMapping("/api/me/cart")
public class CartController {
    private final CartService cart;

    public CartController(CartService cart) {
        this.cart = cart;
    }

    @PostMapping("/items")
    public ApiResponse<CartItemResponse> add(
            @RequestBody JsonNode body,
            @RequestHeader(value = "Idempotency-Key", required = false) String requestKey) {
        ChallengeBRequestParser.requireObjectWithFields(body, "productId");
        Long productId = ChallengeBRequestParser.parseId(
                ChallengeBRequestParser.requireTextField(body, "productId"), "商品 ID");
        return ApiResponse.ok("已加入购物车",
                cart.add(productId, ChallengeBRequestParser.requireIdempotencyKey(requestKey)));
    }

    @PatchMapping("/items/{cartItemId}")
    public ApiResponse<CartItemResponse> setQuantity(@PathVariable String cartItemId,
                                                     @RequestBody JsonNode body) {
        ChallengeBRequestParser.requireObjectWithFields(body, "quantity");
        BigInteger quantity = ChallengeBRequestParser.parseNonNegativeInteger(
                ChallengeBRequestParser.requireTextField(body, "quantity"));
        return ApiResponse.ok(quantity.signum() == 0 ? "已移除" : "已更新",
                cart.setQuantity(ChallengeBRequestParser.parseId(cartItemId, "购物车行 ID"), quantity));
    }

    @DeleteMapping("/items/{cartItemId}")
    public ApiResponse<Void> remove(@PathVariable String cartItemId) {
        cart.remove(ChallengeBRequestParser.parseId(cartItemId, "购物车行 ID"));
        return ApiResponse.ok("已移除", null);
    }

    @GetMapping
    public ApiResponse<CartResponse> getCart() {
        return ApiResponse.ok(cart.getCart());
    }

    @DeleteMapping
    public ApiResponse<Void> clear() {
        cart.clear();
        return ApiResponse.ok(null);
    }
}
