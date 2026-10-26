package com.team.shop.service;

import com.team.shop.dto.response.CustomerResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.repository.CustomerRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import com.team.shop.exception.PaginationException;

@Service
public class CustomerReadServiceImpl implements CustomerReadService {
    private final CustomerRepository customers;

    public CustomerReadServiceImpl(CustomerRepository customers) {
        this.customers = customers;
    }

    @Override
    @Transactional(readOnly = true)
    public PageResponse<CustomerResponse> list(int page, int size) {
        if (page < 1 || size < 1 || size > 100) {
            throw new PaginationException("分页参数必须满足 page>=1 且 1<=size<=100");
        }
        Page<com.team.shop.entity.Customer> result =
                customers.findAllByOrderByRegisteredAtDescIdDesc(PageRequest.of(page - 1, size));
        return new PageResponse<>(result.getContent().stream().map(CustomerResponse::from).toList(),
                page, size, result.getTotalElements(), result.getTotalPages());
    }
}
