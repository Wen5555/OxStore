package com.team.shop.service;

import com.team.shop.dto.response.PageResponse;
import com.team.shop.dto.response.ProductDetailResponse;
import com.team.shop.dto.response.ProductSummaryResponse;
import com.team.shop.domain.SellingMode;

import java.math.BigDecimal;
import java.util.List;
import java.time.LocalDateTime;

public interface ProductService {
    default PageResponse<ProductSummaryResponse> browse(Long category2Id, String query, int page, int size) {
        return browse(category2Id, query, null, page, size);
    }
    PageResponse<ProductSummaryResponse> browse(Long category2Id, String query, SellingMode sellingMode,
                                               int page, int size);
    ProductDetailResponse getBuyerProduct(Long productId);
    PageResponse<ProductDetailResponse> getSellerProducts(int page, int size);
    ProductDetailResponse publish(String name, BigDecimal price, Long category2Id, int stock,
                                  String descriptionHtml, List<String> imagePaths);
    ProductDetailResponse publish(String name, BigDecimal price, Long category2Id, int stock,
                                  String descriptionHtml, List<String> imagePaths, SellingMode sellingMode,
                                  BigDecimal startPrice, BigDecimal minIncrement, LocalDateTime endsAt);
    ProductDetailResponse update(Long productId, Integer stock, Long category2Id);
    ProductDetailResponse takeOffline(Long productId);
    ProductDetailResponse putOnline(Long productId);
}
