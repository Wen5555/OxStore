package com.team.shop.repository;

import com.team.shop.domain.ProductStatus;
import com.team.shop.entity.Product;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface ProductRepository extends JpaRepository<Product, Long> {

    /**
     * 当前活跃商品（ONLINE / RESTORED_ONLINE / FROZEN，至多一件）。
     * 数据库唯一索引 uk_product_active 保证至多一条结果。
     */
    @Query("select p from Product p where p.status in :statuses")
    Optional<Product> findActive(@Param("statuses") Collection<ProductStatus> statuses);

    /**
     * 锁定当前活跃商品行（SELECT ... FOR UPDATE），用作并发串行化点。
     */
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select p from Product p where p.status in :statuses")
    Optional<Product> findActiveForUpdate(@Param("statuses") Collection<ProductStatus> statuses);

    /** 历史商品（已售出），按发布时间倒序 */
    List<Product> findByStatusOrderBySoldAtDescIdDesc(ProductStatus status);
}
