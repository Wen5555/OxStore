package com.team.shop.service;

import com.team.shop.dto.response.OrderHistoryResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.entity.Customer;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.UnauthorizedException;
import com.team.shop.repository.CustomerRepository;
import com.team.shop.repository.OrderHistoryRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.team.shop.exception.PaginationException;

@Service
public class OrderHistoryServiceImpl implements OrderHistoryService {
    private static final int MAX_PAGE_SIZE = 100;
    private final CustomerRepository customers;
    private final OrderHistoryRepository histories;

    public OrderHistoryServiceImpl(CustomerRepository customers, OrderHistoryRepository histories) {
        this.customers = customers;
        this.histories = histories;
    }

    @Override
    @Transactional(readOnly = true)
    public PageResponse<OrderHistoryResponse> getCustomerHistory(Long customerId, int page, int size) {
        if (!customers.existsById(customerId)) {
            throw new UnauthorizedException("顾客登录已失效");
        }
        return getHistory(customerId, page, size);
    }

    @Override
    @Transactional(readOnly = true)
    public PageResponse<OrderHistoryResponse> getSellerCustomerHistory(Long customerId, int page, int size) {
        if (!customers.existsById(customerId)) {
            throw new NotFoundException("顾客不存在", 40404);
        }
        return getHistory(customerId, page, size);
    }

    private PageResponse<OrderHistoryResponse> getHistory(Long customerId, int page, int size) {
        if (page < 1 || size < 1 || size > MAX_PAGE_SIZE) {
            throw new PaginationException("分页参数必须满足 page>=1 且 1<=size<=100");
        }
        Pageable pageable = PageRequest.of(page - 1, size);
        Page<com.team.shop.entity.OrderHistory> result =
                histories.findByCustomerIdOrderByTransactedAtDescIdDesc(customerId, pageable);
        return new PageResponse<>(result.getContent().stream().map(OrderHistoryResponse::from).toList(),
                page, size, result.getTotalElements(), result.getTotalPages());
    }
}
