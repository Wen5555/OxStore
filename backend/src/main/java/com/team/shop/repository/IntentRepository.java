package com.team.shop.repository;

import com.team.shop.domain.IntentStatus;
import com.team.shop.entity.PurchaseIntent;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface IntentRepository extends JpaRepository<PurchaseIntent, Long> {

    /** 某商品的排队队列，按 (queueSeq, id) 升序，队首在第一个 */
    @Query("select i from PurchaseIntent i where i.product.id = :productId and i.status = :status order by i.queueSeq asc, i.id asc")
    List<PurchaseIntent> findQueue(@Param("productId") Long productId, @Param("status") IntentStatus status);

    /** 某商品的交易中意向（至多一条） */
    @Query("select i from PurchaseIntent i where i.product.id = :productId and i.status = :status")
    Optional<PurchaseIntent> findByProductIdAndStatus(@Param("productId") Long productId, @Param("status") IntentStatus status);

    /** 某商品的全部意向（历史详情），按提交顺序 */
    @Query("select i from PurchaseIntent i where i.product.id = :productId order by i.submittedAt asc, i.id asc")
    List<PurchaseIntent> findAllByProduct(@Param("productId") Long productId);

    /** 锁定某商品的排队队列（FOR UPDATE），用于开始交易/递补 */
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select i from PurchaseIntent i where i.product.id = :productId and i.status = :status order by i.queueSeq asc, i.id asc")
    List<PurchaseIntent> findQueueForUpdate(@Param("productId") Long productId, @Param("status") IntentStatus status);

    @Query("select coalesce(max(i.queueSeq), 0) from PurchaseIntent i where i.product.id = :productId")
    long maxQueueSeq(@Param("productId") Long productId);
    Optional<PurchaseIntent> findByTokenLookup(String tokenLookup);
    /** 只有升级前仍有效的口令无索引；逐条 BCrypt 校验保留兼容。 */
    @Query("select i from PurchaseIntent i where i.tokenHash is not null and i.tokenLookup is null")
    List<PurchaseIntent> findLegacyTokens();

    /** 按 id 锁定意向行（FOR UPDATE），用于买家修改/撤销 */
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select i from PurchaseIntent i where i.id = :id")
    Optional<PurchaseIntent> findByIdForUpdate(@Param("id") Long id);
}
