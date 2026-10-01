package com.team.shop.controller.admin;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.dto.response.ProductHistoryDetail;
import com.team.shop.dto.response.ProductResponse;
import com.team.shop.service.ImageStorageService;
import com.team.shop.service.ProductService;
import com.team.shop.exception.BizException;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.math.BigDecimal;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@RestController
@RequestMapping("/api/admin/products")
@Validated
public class AdminProductController {
    private static final Logger log = LoggerFactory.getLogger(AdminProductController.class);

    private final ProductService productService;
    private final ImageStorageService imageStorageService;

    public AdminProductController(ProductService productService, ImageStorageService imageStorageService) {
        this.productService = productService;
        this.imageStorageService = imageStorageService;
    }

    @GetMapping("/current")
    public ApiResponse<ProductResponse> current() {
        return ApiResponse.ok(productService.getAdminCurrentProduct());
    }

    /**
     * 发布商品（multipart/form-data）：
     * name（文本）、description（文本）、price（数字，最多两位小数）、image（图片文件，JPG/PNG ≤5MB）。
     * imagePath 字段无需前端提供，由后端保存图片后生成。
     */
    @PostMapping
    public ApiResponse<ProductResponse> publish(
            @RequestParam("name") @NotBlank(message = "商品名称不能为空") @Size(max = 200, message = "商品名称过长") String name,
            @RequestParam("description") @NotBlank(message = "商品描述不能为空") String description,
            @RequestParam("price") @NotNull(message = "价格不能为空") @Positive(message = "价格必须为正数") BigDecimal price,
            @RequestPart("image") List<MultipartFile> images) {
        if (images.size() != 1) {
            throw new BizException("主图必须且只能上传一张");
        }
        String imagePath = imageStorageService.store(images.get(0));
        try {
            return ApiResponse.ok(productService.publish(name, description, imagePath, price));
        } catch (RuntimeException e) {
            try { imageStorageService.deleteStored(imagePath); }
            catch (IOException cleanupError) { log.warn("发布失败后的图片清理失败", cleanupError); }
            throw e;
        }
    }

    /** 历史商品列表，页码从 1 开始（默认第 1 页，每页 10 条） */
    @GetMapping("/history")
    public ApiResponse<PageResponse<ProductResponse>> history(
            @RequestParam(value = "page", defaultValue = "1") int page,
            @RequestParam(value = "size", defaultValue = "10") int size) {
        return ApiResponse.ok(productService.getHistory(page, size));
    }

    /** 历史商品详情 + 该商品全部意向（需求 S-012） */
    @GetMapping("/history/{id}")
    public ApiResponse<ProductHistoryDetail> historyDetail(@PathVariable("id") Long id) {
        return ApiResponse.ok(productService.getHistoryDetail(id));
    }

    @GetMapping("/{id}/records")
    public ApiResponse<ProductHistoryDetail> records(@PathVariable("id") Long id) {
        return ApiResponse.ok(productService.getRecords(id));
    }

    @PostMapping("/current/freeze")
    public ApiResponse<Void> freeze() {
        productService.freezeManually();
        return ApiResponse.ok(null);
    }

    @PostMapping("/current/unfreeze")
    public ApiResponse<Void> unfreeze() {
        productService.unfreezeManually();
        return ApiResponse.ok(null);
    }
}
