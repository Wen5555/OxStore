package com.team.shop.controller.buyer;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.request.ChallengeBRequestParser;
import com.team.shop.dto.response.FavoriteItemResponse;
import com.team.shop.dto.response.FavoriteStateResponse;
import com.team.shop.dto.response.FavoriteWriteResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.service.FavoriteService;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/me/favorites")
public class FavoriteController {
    private final FavoriteService favorites;

    public FavoriteController(FavoriteService favorites) {
        this.favorites = favorites;
    }

    @PutMapping("/{productId}")
    public ApiResponse<FavoriteWriteResponse> add(@PathVariable String productId) {
        return ApiResponse.ok("已收藏", favorites.add(
                ChallengeBRequestParser.parseId(productId, "商品 ID")));
    }

    @DeleteMapping("/{productId}")
    public ApiResponse<Void> remove(@PathVariable String productId) {
        String message = favorites.remove(ChallengeBRequestParser.parseId(productId, "商品 ID"));
        return ApiResponse.ok(message, null);
    }

    @GetMapping
    public ApiResponse<PageResponse<FavoriteItemResponse>> list(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.ok(favorites.list(page, size));
    }

    @GetMapping("/{productId}")
    public ApiResponse<FavoriteStateResponse> state(@PathVariable String productId) {
        return ApiResponse.ok(favorites.state(ChallengeBRequestParser.parseId(productId, "商品 ID")));
    }
}
