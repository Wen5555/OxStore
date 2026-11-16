package com.team.shop.repository;

import com.team.shop.entity.CartItem;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface CartItemRepository extends JpaRepository<CartItem, Long> {

    /** 整车行集合（不分页），按行 ID 升序（走 idx_cart_customer） */
    @EntityGraph(attributePaths = {"product"})
    List<CartItem> findByCustomerIdOrderByIdAsc(Long customerId);

    Optional<CartItem> findByCustomerIdAndProductId(Long customerId, Long productId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select c from CartItem c where c.id = :id")
    Optional<CartItem> findByIdForUpdate(@Param("id") Long id);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select c from CartItem c where c.customer.id = :customerId and c.product.id = :productId")
    Optional<CartItem> findByCustomerAndProductForUpdate(@Param("customerId") Long customerId,
                                                         @Param("productId") Long productId);

    /** 按行 ID 升序加锁；调用方须在锁后重验归属，不能凭 ID 推断属于本人。 */
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select c from CartItem c where c.id in :ids order by c.id asc")
    List<CartItem> findAllByIdForUpdate(@Param("ids") Collection<Long> ids);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select c from CartItem c where c.customer.id = :customerId order by c.id asc")
    List<CartItem> findAllByCustomerForUpdate(@Param("customerId") Long customerId);
}
