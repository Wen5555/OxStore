package com.team.shop.repository;

import com.team.shop.entity.OrderItem;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface OrderItemRepository extends JpaRepository<OrderItem, Long> {

    /** 取消回补按快照量逐条处理，商品按 ID 升序以符合统一锁顺序 */
    List<OrderItem> findByOrderIdOrderByProductIdAsc(Long orderId);
}
