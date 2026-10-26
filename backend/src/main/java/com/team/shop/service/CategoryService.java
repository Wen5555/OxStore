package com.team.shop.service;

import com.team.shop.dto.response.CategoryTreeItem;

import java.util.List;

public interface CategoryService {
    List<CategoryTreeItem> getTree();
}
