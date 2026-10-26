package com.team.shop.controller;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.response.CategoryTreeItem;
import com.team.shop.service.CategoryService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/categories")
public class CategoryController {
    private final CategoryService categories;

    public CategoryController(CategoryService categories) {
        this.categories = categories;
    }

    @GetMapping("/tree")
    public ApiResponse<List<CategoryTreeItem>> tree() {
        return ApiResponse.ok(categories.getTree());
    }
}
