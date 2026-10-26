package com.team.shop.service;

import com.team.shop.dto.response.PageResponse;
import com.team.shop.dto.response.ProductDetailResponse;
import com.team.shop.dto.response.ProductSummaryResponse;

import java.math.BigDecimal;
import java.util.List;

public interface ProductService {
    PageResponse<ProductSummaryResponse> browse(Long category2Id, String query, int page, int size);
    ProductDetailResponse getBuyerProduct(Long productId);
    PageResponse<ProductDetailResponse> getSellerProducts(int page, int size);
    ProductDetailResponse publish(String name, BigDecimal price, Long category2Id, int stock,
                                  String descriptionHtml, List<String> imagePaths);
    ProductDetailResponse update(Long productId, Integer stock, Long category2Id);
    ProductDetailResponse takeOffline(Long productId);
    ProductDetailResponse putOnline(Long productId);
}
