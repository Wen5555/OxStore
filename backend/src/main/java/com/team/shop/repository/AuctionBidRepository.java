package com.team.shop.repository;

import com.team.shop.entity.AuctionBid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;

public interface AuctionBidRepository extends JpaRepository<AuctionBid, Long> {

    /** 场次出价记录，最新在前（走 uk_bid_auction_seq） */
    @EntityGraph(attributePaths = {"customer"})
    Page<AuctionBid> findByAuctionIdOrderByBidSeqDesc(Long auctionId, Pageable pageable);

    @EntityGraph(attributePaths = {"customer"})
    List<AuctionBid> findTop10ByAuctionIdOrderByBidSeqDesc(Long auctionId);

    /** 判断当前顾客是否参与过该场次，用于 OUTBID/LOST 展示 */
    boolean existsByAuctionIdAndCustomerId(Long auctionId, Long customerId);
}
