package com.team.shop.repository;

import com.team.shop.entity.Customer;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface CustomerRepository extends JpaRepository<Customer, Long> {

    /** 统一锁顺序的第一把锁：同客户的收藏/车/确认/结算/订单命令先锁客户行。 */
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select c from Customer c where c.id = :id")
    Optional<Customer> findByIdForUpdate(@Param("id") Long id);

    boolean existsByUsername(String username);
    Optional<Customer> findByUsername(String username);
    Page<Customer> findAllByOrderByRegisteredAtDescIdDesc(Pageable pageable);
}
