package com.team.shop.repository;

import com.team.shop.entity.CheckoutConfirmation;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface CheckoutConfirmationRepository extends JpaRepository<CheckoutConfirmation, Long> {

    @EntityGraph(attributePaths = {"items"})
    Optional<CheckoutConfirmation> findByToken(String token);
}
