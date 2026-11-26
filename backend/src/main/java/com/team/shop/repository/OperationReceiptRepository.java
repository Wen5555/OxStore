package com.team.shop.repository;

import com.team.shop.domain.ReceiptOperationType;
import com.team.shop.entity.OperationReceipt;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface OperationReceiptRepository extends JpaRepository<OperationReceipt, Long> {

    /** Customer lock serializes same-confirmation submissions even when callers change the request key. */
    Optional<OperationReceipt> findFirstByCustomerIdAndOperationTypeAndRequestHash(
            Long customerId, ReceiptOperationType operationType, String requestHash);

    /** 同键重试先查成功回执；调用前应已持有客户锁，并发同键由此串行等待首事务。 */
    Optional<OperationReceipt> findByCustomerIdAndOperationTypeAndRequestKey(
            Long customerId, ReceiptOperationType operationType, String requestKey);
}
