package com.team.shop.controller.admin;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.request.ProductUpdateRequest;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.dto.response.ProductDetailResponse;
import com.team.shop.exception.BizException;
import com.team.shop.service.ImageStorageService;
import com.team.shop.service.ProductService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@RestController
@RequestMapping("/api/admin/products")
@Validated
public class AdminProductController {
    private static final Logger log = LoggerFactory.getLogger(AdminProductController.class);
    private final ProductService products;
    private final ImageStorageService imageStorage;

    public AdminProductController(ProductService products, ImageStorageService imageStorage) {
        this.products = products;
        this.imageStorage = imageStorage;
    }

    @GetMapping
    public ApiResponse<PageResponse<ProductDetailResponse>> list(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size) {
        return ApiResponse.ok(products.getSellerProducts(page, size));
    }

    @PostMapping
    public ResponseEntity<ApiResponse<ProductDetailResponse>> publish(
            @RequestParam("name") @NotBlank @Size(max = 200) String name,
            @RequestParam("price") @NotNull @Positive BigDecimal price,
            @RequestParam("category2Id") @NotNull Long category2Id,
            @RequestParam("stock") @PositiveOrZero int stock,
            @RequestParam(value = "descriptionHtml", required = false) String descriptionHtml,
            @RequestPart(value = "images", required = false) List<MultipartFile> images,
            @RequestPart(value = "images[]", required = false) List<MultipartFile> bracketImages) {
        List<MultipartFile> suppliedImages = new ArrayList<>();
        if (images != null) suppliedImages.addAll(images);
        if (bracketImages != null) suppliedImages.addAll(bracketImages);
        if (suppliedImages.size() > 9) {
            throw new BizException("商品图片最多上传 9 张");
        }
        List<String> storedPaths = new ArrayList<>();
        try {
            for (MultipartFile image : suppliedImages) {
                storedPaths.add(imageStorage.store(image));
            }
            ProductDetailResponse created = products.publish(name, price, category2Id, stock,
                    descriptionHtml, storedPaths);
            return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.ok(created));
        } catch (RuntimeException e) {
            cleanupStoredImages(storedPaths);
            throw e;
        }
    }

    @PatchMapping("/{productId}")
    public ApiResponse<ProductDetailResponse> update(@PathVariable Long productId,
                                                     @Valid @RequestBody ProductUpdateRequest request) {
        return ApiResponse.ok(products.update(productId, request.stock(), request.category2Id()));
    }

    @PostMapping("/{productId}/offline")
    public ApiResponse<ProductDetailResponse> offline(@PathVariable Long productId) {
        return ApiResponse.ok(products.takeOffline(productId));
    }

    @PostMapping("/{productId}/online")
    public ApiResponse<ProductDetailResponse> online(@PathVariable Long productId) {
        return ApiResponse.ok(products.putOnline(productId));
    }

    private void cleanupStoredImages(List<String> paths) {
        for (String path : paths) {
            try {
                imageStorage.deleteStored(path);
            } catch (IOException cleanupError) {
                log.warn("商品发布失败后的图片清理失败", cleanupError);
            }
        }
    }
}
