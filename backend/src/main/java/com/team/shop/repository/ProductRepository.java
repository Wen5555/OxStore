package com.team.shop.repository;

import com.team.shop.domain.ProductStatus;
import com.team.shop.entity.Product;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface ProductRepository extends JpaRepository<Product, Long> {

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select p from Product p where p.id = :id")
    Optional<Product> findByIdForUpdate(@Param("id") Long id);

    @EntityGraph(attributePaths = {"category", "images"})
    Page<Product> findAllByStatusOrderByPublishedAtDescIdDesc(ProductStatus status, Pageable pageable);

    @EntityGraph(attributePaths = {"category", "images"})
    List<Product> findAllByStatusOrderByPublishedAtDescIdDesc(ProductStatus status);

    @EntityGraph(attributePaths = {"category", "images"})
    Page<Product> findAllByOrderByPublishedAtDescIdDesc(Pageable pageable);

    @EntityGraph(attributePaths = {"category", "images"})
    List<Product> findAllByStatusOrderByPublishedAtDescIdDesc(ProductStatus status, org.springframework.data.domain.Sort sort);
}
