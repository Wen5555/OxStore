package com.team.shop.service;

import com.team.shop.dto.response.OrderResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.entity.ShopOrder;
import com.team.shop.exception.ApiBusinessException;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.PaginationException;
import com.team.shop.repository.ShopOrderRepository;
import com.team.shop.security.CustomerAccess;
import com.team.shop.security.UserIdentity;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
public class OrderQueryService {
    private static final int MAX_PAGE_SIZE = 100;

    private final CustomerAccess customerAccess;
    private final ShopOrderRepository orders;

    public OrderQueryService(CustomerAccess customerAccess, ShopOrderRepository orders) {
        this.customerAccess = customerAccess;
        this.orders = orders;
    }

    @Transactional(readOnly = true)
    public PageResponse<OrderResponse> listMine(int page, int size) {
        validatePagination(page, size);
        Long customerId = customerAccess.requireCustomerId();
        return orderPage(orders.findCustomerOrderIds(customerId, PageRequest.of(page - 1, size)), false);
    }

    @Transactional(readOnly = true)
    public OrderResponse getMine(Long orderId) {
        customerAccess.requireCustomerId();
        Long ownerId = orders.findCustomerIdById(orderId)
                .orElseThrow(() -> new NotFoundException("订单不存在", 40405));
        customerAccess.requireOrderOwner(ownerId);
        return orders.findByIdWithItems(orderId)
                .map(order -> OrderResponse.from(order, false))
                .orElseThrow(() -> new NotFoundException("订单不存在", 40405));
    }

    @Transactional(readOnly = true)
    public PageResponse<OrderResponse> listAll(int page, int size, UserIdentity identity) {
        requireSeller(identity);
        validatePagination(page, size);
        return orderPage(orders.findAllOrderIds(PageRequest.of(page - 1, size)), true);
    }

    @Transactional(readOnly = true)
    public OrderResponse getAny(Long orderId, UserIdentity identity) {
        requireSeller(identity);
        return orders.findByIdWithItems(orderId)
                .map(order -> OrderResponse.from(order, true))
                .orElseThrow(() -> new NotFoundException("订单不存在", 40405));
    }

    private PageResponse<OrderResponse> orderPage(Page<Long> ids, boolean sellerView) {
        List<Long> orderIds = ids.getContent();
        Map<Long, ShopOrder> ordersById = orderIds.isEmpty()
                ? Map.of()
                : this.orders.findAllWithItemsByIdIn(orderIds).stream()
                .collect(Collectors.toMap(ShopOrder::getId, Function.identity()));
        List<OrderResponse> items = orderIds.stream().map(id -> {
            ShopOrder order = ordersById.get(id);
            if (order == null) {
                throw new IllegalStateException("订单分页数据在查询期间发生变化");
            }
            return OrderResponse.from(order, sellerView);
        }).toList();
        return new PageResponse<>(items, ids.getNumber() + 1, ids.getSize(),
                ids.getTotalElements(), ids.getTotalPages());
    }

    private void validatePagination(int page, int size) {
        if (page < 1 || size < 1 || size > MAX_PAGE_SIZE) {
            throw new PaginationException("分页参数必须满足 page>=1 且 1<=size<=100");
        }
    }

    private void requireSeller(UserIdentity identity) {
        if (identity == null || !"SELLER".equals(identity.role())) {
            throw new ApiBusinessException(403, 40301, "无此权限", null);
        }
    }
}
