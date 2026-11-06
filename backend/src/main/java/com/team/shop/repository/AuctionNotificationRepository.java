package com.team.shop.repository;

import com.team.shop.domain.AuctionNotificationType;
import com.team.shop.domain.NotificationRecipientRole;
import com.team.shop.entity.AuctionNotification;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface AuctionNotificationRepository extends JpaRepository<AuctionNotification, Long> {

    /** 顾客本人的提醒，最新在前 */
    Page<AuctionNotification> findByRecipientCustomerIdOrderByCreatedAtDescIdDesc(Long customerId, Pageable pageable);

    /** 卖家后台提醒，最新在前 */
    Page<AuctionNotification> findByRecipientRoleOrderByCreatedAtDescIdDesc(NotificationRecipientRole role, Pageable pageable);

    long countByRecipientCustomerIdAndReadAtIsNull(Long customerId);

    long countByRecipientRoleAndReadAtIsNull(NotificationRecipientRole role);

    /** 结拍重入时先查再插；并发插入由 uk_notification_auction_type 兜底 */
    boolean existsByAuctionIdAndType(Long auctionId, AuctionNotificationType type);

    Optional<AuctionNotification> findByIdAndRecipientCustomerId(Long id, Long customerId);
}
