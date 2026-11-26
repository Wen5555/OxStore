package com.team.shop.repository;

import com.team.shop.entity.ShopOrder;
import jakarta.persistence.LockModeType;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.data.jpa.repository.EntityGraph;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface ShopOrderRepository extends JpaRepository<ShopOrder, Long> {

    Optional<ShopOrder> findByOrderNo(String orderNo);

    @Query("select o.customer.id from ShopOrder o where o.id = :id")
    Optional<Long> findCustomerIdById(@Param("id") Long id);

    /** 锁顺序 customer → operation_receipt → order → product…，调用前应已持有客户锁。 */
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select o from ShopOrder o where o.id = :id")
    Optional<ShopOrder> findByIdForUpdate(@Param("id") Long id);

    /** 客户订单历史，时间倒序、ID 倒序稳定（走 idx_shop_order_customer_time） */
    Page<ShopOrder> findByCustomerIdOrderByCreatedAtDescIdDesc(Long customerId, Pageable pageable);

    /** 商家全站订单（走 idx_shop_order_time） */
    Page<ShopOrder> findAllByOrderByCreatedAtDescIdDesc(Pageable pageable);

    @Query(value = "select o.id from ShopOrder o where o.customer.id = :customerId "
            + "order by o.createdAt desc, o.id desc",
            countQuery = "select count(o) from ShopOrder o where o.customer.id = :customerId")
    Page<Long> findCustomerOrderIds(@Param("customerId") Long customerId, Pageable pageable);

    @Query(value = "select o.id from ShopOrder o order by o.createdAt desc, o.id desc",
            countQuery = "select count(o) from ShopOrder o")
    Page<Long> findAllOrderIds(Pageable pageable);

    @EntityGraph(attributePaths = {"customer", "items", "items.product"})
    @Query("select distinct o from ShopOrder o where o.id in :ids")
    List<ShopOrder> findAllWithItemsByIdIn(@Param("ids") Collection<Long> ids);

    @EntityGraph(attributePaths = {"customer", "items", "items.product"})
    @Query("select distinct o from ShopOrder o where o.id = :id")
    Optional<ShopOrder> findByIdWithItems(@Param("id") Long id);
}
