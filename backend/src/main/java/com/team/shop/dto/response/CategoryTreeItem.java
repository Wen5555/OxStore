package com.team.shop.dto.response;

import com.team.shop.entity.Category;

import java.util.List;

public record CategoryTreeItem(Long id, String name, List<CategoryTreeItem> children) {
    public static CategoryTreeItem from(Category category, List<Category> children) {
        return new CategoryTreeItem(category.getId(), category.getName(),
                children.stream().map(child -> new CategoryTreeItem(child.getId(), child.getName(), List.of())).toList());
    }
}
