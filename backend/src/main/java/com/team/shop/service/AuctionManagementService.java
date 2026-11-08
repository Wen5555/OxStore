package com.team.shop.service;

import com.team.shop.domain.AuctionStatus;
import com.team.shop.dto.response.AuctionAdminResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.repository.AuctionSessionRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuctionManagementService {
    private static final int MAX_PAGE_SIZE = 100;

    private final AuctionSessionRepository auctions;

    public AuctionManagementService(AuctionSessionRepository auctions) {
        this.auctions = auctions;
    }

    @Transactional(readOnly = true)
    public PageResponse<AuctionAdminResponse> list(AuctionStatus status, int page, int size) {
        if (page < 1 || size < 1 || size > MAX_PAGE_SIZE) {
            throw new com.team.shop.exception.PaginationException("分页参数必须满足 page>=1 且 1<=size<=100");
        }
        Pageable pageable = PageRequest.of(page - 1, size);
        Page<com.team.shop.entity.AuctionSession> result = status == null
                ? auctions.findAllByOrderByEndsAtDescIdDesc(pageable)
                : auctions.findAllByStatusOrderByEndsAtDescIdDesc(status, pageable);
        return new PageResponse<>(result.getContent().stream().map(AuctionAdminResponse::from).toList(),
                result.getNumber() + 1, result.getSize(), result.getTotalElements(), result.getTotalPages());
    }
}
