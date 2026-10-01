package com.team.shop.controller.admin;

import com.team.shop.exception.GlobalExceptionHandler;
import com.team.shop.service.ImageStorageService;
import com.team.shop.service.ProductService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.math.BigDecimal;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class AdminProductControllerTest {
    private final ProductService products = mock(ProductService.class);
    private final ImageStorageService images = mock(ImageStorageService.class);
    private MockMvc mvc;

    @BeforeEach
    void setUp() {
        mvc = MockMvcBuilders.standaloneSetup(new AdminProductController(products, images))
                .setControllerAdvice(new GlobalExceptionHandler()).build();
    }

    @Test
    void multipleImagePartsAreRejectedBeforeSavingFilesOrProduct() throws Exception {
        mvc.perform(multipart("/api/admin/products")
                        .file(new MockMultipartFile("image", "one.png", "image/png", new byte[]{1}))
                        .file(new MockMultipartFile("image", "two.png", "image/png", new byte[]{2}))
                        .param("name", "商品").param("description", "说明").param("price", "1.00"))
                .andExpect(status().isBadRequest());
        verifyNoInteractions(images, products);
    }

    @Test
    void singleImagePartKeepsExistingMultipartContract() throws Exception {
        MockMultipartFile image = new MockMultipartFile("image", "one.png", "image/png", new byte[]{1});
        when(images.store(any())).thenReturn("/api/images/one.png");
        mvc.perform(multipart("/api/admin/products").file(image)
                        .param("name", "商品").param("description", "说明").param("price", "1.00"))
                .andExpect(status().isOk());
        verify(images).store(image);
        verify(products).publish("商品", "说明", "/api/images/one.png", new BigDecimal("1.00"));
    }
}
