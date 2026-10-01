package com.team.shop.repository;
import com.team.shop.entity.TradeAttempt;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.util.List;
import java.util.Optional;
public interface TradeAttemptRepository extends JpaRepository<TradeAttempt, Long> {
    @Query("select a from TradeAttempt a where a.intent.id = :id and a.finishedAt is null")
    Optional<TradeAttempt> findOpen(@Param("id") Long intentId);
    @Query("select a from TradeAttempt a where a.intent.product.id = :id order by a.startedAt, a.id")
    List<TradeAttempt> findAllByProduct(@Param("id") Long productId);
}
