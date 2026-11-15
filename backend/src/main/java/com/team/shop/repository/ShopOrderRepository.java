package com.team.shop.repository;

import com.team.shop.entity.ShopOrder;
import jakarta.persistence.LockModeType;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface ShopOrderRepository extends JpaRepository<ShopOrder, Long> {

    Optional<ShopOrder> findByOrderNo(String orderNo);

    /** 锁顺序 customer → operation_receipt → order → product…，调用前应已持有客户锁。 */
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select o from ShopOrder o where o.id = :id")
    Optional<ShopOrder> findByIdForUpdate(@Param("id") Long id);

    /** 客户订单历史，时间倒序、ID 倒序稳定（走 idx_shop_order_customer_time） */
    Page<ShopOrder> findByCustomerIdOrderByCreatedAtDescIdDesc(Long customerId, Pageable pageable);

    /** 商家全站订单（走 idx_shop_order_time） */
    Page<ShopOrder> findAllByOrderByCreatedAtDescIdDesc(Pageable pageable);
}
