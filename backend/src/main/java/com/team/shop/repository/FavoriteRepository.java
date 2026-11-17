package com.team.shop.repository;

import com.team.shop.entity.Favorite;
import jakarta.persistence.LockModeType;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface FavoriteRepository extends JpaRepository<Favorite, Long> {

    Optional<Favorite> findByCustomerIdAndProductId(Long customerId, Long productId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select f from Favorite f where f.customer.id = :customerId and f.product.id = :productId")
    Optional<Favorite> findForUpdate(@Param("customerId") Long customerId, @Param("productId") Long productId);

    /** 转收藏批量锁定，按商品 ID 升序以符合统一锁顺序 */
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select f from Favorite f where f.customer.id = :customerId and f.product.id in :productIds "
            + "order by f.product.id asc")
    List<Favorite> findAllForUpdate(@Param("customerId") Long customerId,
                                    @Param("productIds") Collection<Long> productIds);

    /** 收藏列表：时间倒序、ID 倒序，每页 10 条（走 idx_favorite_customer_time） */
    @EntityGraph(attributePaths = {"product"})
    Page<Favorite> findByCustomerIdOrderByCreatedAtDescIdDesc(Long customerId, Pageable pageable);

    long deleteByCustomerIdAndProductId(Long customerId, Long productId);
}
