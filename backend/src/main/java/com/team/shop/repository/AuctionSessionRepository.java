package com.team.shop.repository;

import com.team.shop.domain.AuctionStatus;
import com.team.shop.entity.AuctionSession;
import jakarta.persistence.LockModeType;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface AuctionSessionRepository extends JpaRepository<AuctionSession, Long> {

    /** 公开快照：按商品读取场次（一对一） */
    @EntityGraph(attributePaths = {"product", "leader"})
    Optional<AuctionSession> findByProductId(Long productId);

    /** 出价与结拍前锁定场次行（FOR UPDATE），保证当前价、领先者和结拍只被一个事务改写 */
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select a from AuctionSession a where a.product.id = :productId")
    Optional<AuctionSession> findByProductIdForUpdate(@Param("productId") Long productId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select a from AuctionSession a where a.id = :id")
    Optional<AuctionSession> findByIdForUpdate(@Param("id") Long id);

    /** 结拍扫描：已到截止时间仍为 LIVE 的场次，按截止时间先后（走 idx_auction_status_ends） */
    @Query("select a.id from AuctionSession a where a.status = :status and a.endsAt <= :now order by a.endsAt asc, a.id asc")
    List<Long> findDueIds(@Param("status") AuctionStatus status, @Param("now") LocalDateTime now, Pageable pageable);

    /** 卖家拍卖管理列表 */
    @EntityGraph(attributePaths = {"product", "leader"})
    Page<AuctionSession> findAllByOrderByEndsAtDescIdDesc(Pageable pageable);

    @EntityGraph(attributePaths = {"product", "leader"})
    Page<AuctionSession> findAllByStatusOrderByEndsAtDescIdDesc(AuctionStatus status, Pageable pageable);

    /** 列表页批量补充拍卖摘要 */
    @EntityGraph(attributePaths = {"leader"})
    List<AuctionSession> findAllByProductIdIn(Collection<Long> productIds);
}
