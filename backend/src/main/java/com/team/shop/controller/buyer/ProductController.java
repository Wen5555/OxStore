package com.team.shop.controller.buyer;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.dto.response.ProductDetailResponse;
import com.team.shop.dto.response.ProductSummaryResponse;
import com.team.shop.service.ProductService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/products")
public class ProductController {
    private final ProductService products;

    public ProductController(ProductService products) {
        this.products = products;
    }

    @GetMapping
    public ApiResponse<PageResponse<ProductSummaryResponse>> browse(
            @RequestParam(required = false) Long category2Id,
            @RequestParam(required = false, name = "q") String query,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.ok(products.browse(category2Id, query, page, size));
    }

    @GetMapping("/{productId}")
    public ApiResponse<ProductDetailResponse> detail(@PathVariable Long productId) {
        return ApiResponse.ok(products.getBuyerProduct(productId));
    }
}
