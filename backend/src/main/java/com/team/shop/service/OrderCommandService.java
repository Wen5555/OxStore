package com.team.shop.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.team.shop.domain.OrderStateMachine;
import com.team.shop.domain.OrderStatus;
import com.team.shop.dto.request.ChallengeBRequestParser;
import com.team.shop.dto.response.OrderResponse;
import com.team.shop.exception.*;
import com.team.shop.repository.CustomerRepository;
import com.team.shop.repository.ShopOrderRepository;
import com.team.shop.security.UserIdentity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class OrderCommandService {
    private final CustomerRepository customers;
    private final ShopOrderRepository orders;
    public OrderCommandService(CustomerRepository customers, ShopOrderRepository orders) {
        this.customers = customers; this.orders = orders;
    }
    @Transactional
    public OrderResponse advance(Long id, JsonNode body, UserIdentity identity) {
        if (identity == null || !"SELLER".equals(identity.role()))
            throw new ApiBusinessException(403,40301,"无此权限",null);
        ChallengeBRequestParser.requireObjectWithFields(body,"action","expectedStatus");
        OrderStateMachine.Action action;
        OrderStatus expected;
        try {
            action = OrderStateMachine.Action.valueOf(ChallengeBRequestParser.requireTextField(body,"action"));
            expected = OrderStatus.valueOf(ChallengeBRequestParser.requireTextField(body,"expectedStatus"));
        } catch (IllegalArgumentException e) {
            throw new ApiBusinessException(400,40002,"订单动作或状态格式不正确",null);
        }
        Long customerId = orders.findCustomerIdById(id).orElseThrow(() -> new NotFoundException("订单不存在",40405));
        // Same mutex/order-row order as B-014, so shipping/completion cannot overwrite cancellation.
        customers.findByIdForUpdate(customerId).orElseThrow(() -> new NotFoundException("顾客不存在",40404));
        var order = orders.findByIdForUpdate(id).orElseThrow(() -> new NotFoundException("订单不存在",40405));
        if (!customerId.equals(order.getCustomer().getId())) throw new IllegalStateException("订单归属发生变化");
        order.applyStatus(OrderStateMachine.next(order.getStatus(),expected,action));
        orders.saveAndFlush(order);
        return OrderResponse.from(order,true);
    }
}
