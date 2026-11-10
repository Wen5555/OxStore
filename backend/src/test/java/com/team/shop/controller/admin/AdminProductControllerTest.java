package com.team.shop.controller.admin;

import com.team.shop.domain.SellingMode;
import com.team.shop.dto.response.ProductDetailResponse;
import com.team.shop.exception.BizException;
import com.team.shop.exception.GlobalExceptionHandler;
import com.team.shop.service.ImageStorageService;
import com.team.shop.service.ProductService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.ArgumentMatchers.nullable;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class AdminProductControllerTest {
    private final ProductService products = mock(ProductService.class);
    private final ImageStorageService images = mock(ImageStorageService.class);
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.standaloneSetup(new AdminProductController(products, images))
                .setControllerAdvice(new GlobalExceptionHandler()).build();
        when(products.publish(anyString(), any(BigDecimal.class), any(), anyInt(), nullable(String.class),
                anyList(), any(SellingMode.class), nullable(BigDecimal.class), nullable(BigDecimal.class),
                nullable(LocalDateTime.class)))
                .thenReturn(new ProductDetailResponse(1L, "测试", BigDecimal.ONE, 2L, "leaf", 1,
                        "", List.of("/api/images/one.jpg"), "/api/images/one.jpg",
                        com.team.shop.domain.ProductStatus.ONLINE, true, LocalDateTime.now(), LocalDateTime.now()));
    }

    @Test
    void rejectsMoreThanNineImagesBeforeWritingAnyFiles() throws Exception {
        var request = multipart("/api/admin/products");
        request.param("name", "商品")
                .param("price", "1.00")
                .param("category2Id", "2")
                .param("stock", "1");
        for (int i = 0; i < 10; i++) {
            request.file(new MockMultipartFile("images", i + ".jpg", "image/jpeg", new byte[]{1}));
        }
        mvc.perform(request).andExpect(status().isBadRequest());
        verifyNoInteractions(images, products);
    }

    @Test
    void acceptsMultipleImagesAndPassesTheirOrderToTheService() throws Exception {
        MockMultipartFile first = new MockMultipartFile("images", "first.jpg", "image/jpeg", new byte[]{1});
        MockMultipartFile second = new MockMultipartFile("images", "second.jpg", "image/jpeg", new byte[]{2});
        when(images.store(any())).thenReturn("/api/images/first.jpg", "/api/images/second.jpg");

        mvc.perform(multipart("/api/admin/products")
                        .file(first)
                        .file(second)
                        .param("name", "商品")
                        .param("price", "1.00")
                        .param("category2Id", "2")
                        .param("stock", "1")
                        .param("descriptionHtml", "<p>说明</p>"))
                .andExpect(status().isCreated());

        verify(products).publish("商品", new BigDecimal("1.00"), 2L, 1, "<p>说明</p>",
                List.of("/api/images/first.jpg", "/api/images/second.jpg"),
                SellingMode.FIXED_PRICE, null, null, null);
    }

    @Test
    void publishesWithoutImages() throws Exception {
        mvc.perform(multipart("/api/admin/products")
                        .param("name", "商品")
                        .param("price", "1.00")
                        .param("category2Id", "2")
                        .param("stock", "0"))
                .andExpect(status().isCreated());

        verify(products).publish(eq("商品"), eq(new BigDecimal("1.00")), eq(2L), eq(0),
                isNull(), eq(List.of()), eq(SellingMode.FIXED_PRICE), isNull(), isNull(), isNull());
    }

    @Test
    void rejectsFixedPricePublishThatCarriesAuctionFields() throws Exception {
        when(products.publish(eq("一口价"), eq(new BigDecimal("12.50")), eq(2L), eq(1),
                isNull(), eq(List.of()), eq(SellingMode.FIXED_PRICE),
                eq(new BigDecimal("10.00")), eq(new BigDecimal("1.00")), any(LocalDateTime.class)))
                .thenThrow(new BizException("普通在售不能填写拍卖参数"));

        mvc.perform(multipart("/api/admin/products")
                        .param("name", "一口价")
                        .param("price", "12.50")
                        .param("category2Id", "2")
                        .param("stock", "1")
                        .param("sellingMode", "FIXED_PRICE")
                        .param("startPrice", "10.00")
                        .param("minIncrement", "1.00")
                        .param("endsAt", "2026-11-10T13:30:00"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(40001));

        verify(products).publish(eq("一口价"), eq(new BigDecimal("12.50")), eq(2L), eq(1),
                isNull(), eq(List.of()), eq(SellingMode.FIXED_PRICE),
                eq(new BigDecimal("10.00")), eq(new BigDecimal("1.00")), any(LocalDateTime.class));
    }
}
