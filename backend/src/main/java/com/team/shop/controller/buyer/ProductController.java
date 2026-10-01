package com.team.shop.controller.buyer;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.ProductResponse;
import com.team.shop.service.ProductService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/products")
public class ProductController {

    private final ProductService productService;

    public ProductController(ProductService productService) {
        this.productService = productService;
    }

    /** 买家查看当前商品（在售/冻结），无商品时 data 为 null */
    @GetMapping("/current")
    public ApiResponse<ProductResponse> current() {
        return ApiResponse.ok(productService.getCurrentProduct());
    }
}
