package com.team.shop.service;

import com.team.shop.dto.response.AuctionBidResponse;
import com.team.shop.dto.response.AuctionSnapshotResponse;
import com.team.shop.security.UserIdentity;

import java.math.BigDecimal;

public interface AuctionService {
    AuctionSnapshotResponse snapshot(Long productId, UserIdentity identity);
    AuctionBidResponse placeBid(Long productId, Long customerId, BigDecimal amount);
}
