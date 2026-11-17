package com.team.shop.service;

import com.team.shop.domain.SellingMode;
import com.team.shop.dto.response.LegacyRecordResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.entity.PurchaseIntent;
import com.team.shop.exception.PaginationException;
import com.team.shop.repository.IntentRepository;
import com.team.shop.security.CustomerAccess;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class LegacyIntentArchiveService {
    private static final int MAX_PAGE_SIZE = 100;

    private final CustomerAccess customerAccess;
    private final IntentRepository intents;

    public LegacyIntentArchiveService(CustomerAccess customerAccess, IntentRepository intents) {
        this.customerAccess = customerAccess;
        this.intents = intents;
    }

    @Transactional(readOnly = true)
    public PageResponse<LegacyRecordResponse> customerArchive(int page, int size) {
        Long customerId = customerAccess.requireCustomerId();
        return findPage(page, size, null, customerId);
    }

    @Transactional(readOnly = true)
    public PageResponse<LegacyRecordResponse> sellerArchive(int page, int size, Long productId, Long customerId) {
        return findPage(page, size, productId, customerId);
    }

    private PageResponse<LegacyRecordResponse> findPage(int page, int size, Long productId, Long customerId) {
        if (page < 1 || size < 1 || size > MAX_PAGE_SIZE) {
            throw new PaginationException("分页参数必须满足 page>=1 且 1<=size<=100");
        }
        Page<PurchaseIntent> result = intents.findLegacyPage(SellingMode.FIXED_PRICE, productId, customerId,
                PageRequest.of(page - 1, size, Sort.by(Sort.Direction.DESC, "submittedAt")
                        .and(Sort.by(Sort.Direction.DESC, "id"))));
        return new PageResponse<>(result.getContent().stream().map(LegacyRecordResponse::from).toList(),
                page, size, result.getTotalElements(), result.getTotalPages());
    }
}
