package com.team.shop.repository;

import com.team.shop.entity.CartItemTombstone;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface CartItemTombstoneRepository extends JpaRepository<CartItemTombstone, Long> {

    Optional<CartItemTombstone> findByCartItemId(Long cartItemId);

    /** 判定一批旧行 ID 中哪些已被删除及其归属 */
    List<CartItemTombstone> findByCartItemIdIn(Collection<Long> cartItemIds);
}
