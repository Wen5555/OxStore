package com.team.shop.repository;

import com.team.shop.entity.Category;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface CategoryRepository extends JpaRepository<Category, Long> {
    Optional<Category> findByNameAndParentIsNull(String name);
    Optional<Category> findByNameAndParentId(String name, Long parentId);
    List<Category> findByParentIsNullOrderByIdAsc();
    List<Category> findByParentIdOrderByIdAsc(Long parentId);
}
