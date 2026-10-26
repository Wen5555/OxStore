package com.team.shop.service;

import com.team.shop.dto.response.CategoryTreeItem;
import com.team.shop.repository.CategoryRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CategoryServiceImpl implements CategoryService {
    private final CategoryRepository categories;

    public CategoryServiceImpl(CategoryRepository categories) {
        this.categories = categories;
    }

    @Override
    @Transactional(readOnly = true)
    public java.util.List<CategoryTreeItem> getTree() {
        return categories.findByParentIsNullOrderByIdAsc().stream()
                .map(root -> CategoryTreeItem.from(root, categories.findByParentIdOrderByIdAsc(root.getId())))
                .toList();
    }
}
