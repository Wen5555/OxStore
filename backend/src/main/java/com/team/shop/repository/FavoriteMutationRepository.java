package com.team.shop.repository;

import com.team.shop.entity.FavoriteMutation;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Optional;

public interface FavoriteMutationRepository extends JpaRepository<FavoriteMutation, FavoriteMutation.Key> {

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select m from FavoriteMutation m where m.id.customerId = :customerId and m.id.productId = :productId")
    Optional<FavoriteMutation> findForUpdate(@Param("customerId") Long customerId,
                                             @Param("productId") Long productId);
}
