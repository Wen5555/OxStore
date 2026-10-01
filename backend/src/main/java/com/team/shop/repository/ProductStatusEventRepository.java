package com.team.shop.repository;
import com.team.shop.entity.ProductStatusEvent;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.util.List;
public interface ProductStatusEventRepository extends JpaRepository<ProductStatusEvent, Long> {
    @Query("select e from ProductStatusEvent e where e.product.id = :id order by e.occurredAt, e.id")
    List<ProductStatusEvent> findAllByProduct(@Param("id") Long productId);
}
