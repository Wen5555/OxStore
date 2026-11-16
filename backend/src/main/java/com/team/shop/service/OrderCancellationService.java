package com.team.shop.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.OrderCancelledBy;
import com.team.shop.domain.OrderStatus;
import com.team.shop.dto.request.CancelOrderRequest;
import com.team.shop.dto.response.OrderResponse;
import com.team.shop.entity.OrderItem;
import com.team.shop.entity.Product;
import com.team.shop.entity.ShopOrder;
import com.team.shop.exception.ApiBusinessException;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.StateConflictException;
import com.team.shop.exception.UnauthorizedException;
import com.team.shop.repository.CustomerRepository;
import com.team.shop.repository.OrderItemRepository;
import com.team.shop.repository.ProductRepository;
import com.team.shop.repository.ShopOrderRepository;
import com.team.shop.security.CustomerAccess;
import com.team.shop.security.UserIdentity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class OrderCancellationService {
    private final CustomerAccess customerAccess;
    private final CustomerRepository customers;
    private final ShopOrderRepository orders;
    private final OrderItemRepository orderItems;
    private final ProductRepository products;

    public OrderCancellationService(CustomerAccess customerAccess, CustomerRepository customers,
                                    ShopOrderRepository orders, OrderItemRepository orderItems,
                                    ProductRepository products) {
        this.customerAccess = customerAccess;
        this.customers = customers;
        this.orders = orders;
        this.orderItems = orderItems;
        this.products = products;
    }

    @Transactional
    public OrderResponse cancelForCustomer(Long orderId, JsonNode body) {
        Long customerId = customerAccess.requireCustomerId();
        Long ownerId = findOrderOwnerId(orderId);
        customerAccess.requireOrderOwner(ownerId);
        return cancelLocked(orderId, body, customerId, OrderCancelledBy.CUSTOMER);
    }

    @Transactional
    public OrderResponse cancelForSeller(Long orderId, JsonNode body, UserIdentity identity) {
        if (identity == null || !"SELLER".equals(identity.role())) {
            throw new ApiBusinessException(403, 40301, "无此权限", null);
        }
        Long ownerId = findOrderOwnerId(orderId);
        return cancelLocked(orderId, body, ownerId, OrderCancelledBy.SELLER);
    }

    private OrderResponse cancelLocked(Long orderId, JsonNode body, Long ownerId, OrderCancelledBy cancelledBy) {
        customers.findByIdForUpdate(ownerId)
                .orElseThrow(() -> new UnauthorizedException("请重新登录"));
        ShopOrder order = orders.findByIdForUpdate(orderId)
                .orElseThrow(() -> new NotFoundException("订单不存在"));
        if (!ownerId.equals(order.getCustomer().getId())) {
            throw new IllegalStateException("订单归属在持有客户锁后发生变化");
        }
        if (cancelledBy == OrderCancelledBy.CUSTOMER) {
            customerAccess.requireOrderOwner(order.getCustomer().getId());
        }

        CancelOrderRequest request = CancelOrderRequest.parse(body);
        validateCancellation(order.getStatus(), request.expectedStatus(), cancelledBy);
        List<OrderItem> items = orderItems.findByOrderIdOrderByProductIdAsc(orderId);
        if (items.isEmpty()) {
            throw new IllegalStateException("订单缺少明细，无法执行库存回补");
        }

        Map<Long, Product> lockedProducts = new LinkedHashMap<>();
        for (OrderItem item : items) {
            Long productId = item.getProduct().getId();
            if (!lockedProducts.containsKey(productId)) {
                Product product = products.findByIdForUpdate(productId)
                        .orElseThrow(() -> new IllegalStateException("订单明细关联的商品不存在"));
                lockedProducts.put(productId, product);
            }
        }

        var now = BusinessTime.now().truncatedTo(ChronoUnit.MICROS);
        order.markCancelled(cancelledBy, request.reason(), now);
        orders.saveAndFlush(order);
        for (OrderItem item : items) {
            lockedProducts.get(item.getProduct().getId())
                    .restoreForCancelledOrder(item.getQuantitySnapshot(), now);
        }
        return OrderResponse.from(order, cancelledBy == OrderCancelledBy.SELLER);
    }

    private Long findOrderOwnerId(Long orderId) {
        return orders.findCustomerIdById(orderId).orElseThrow(() -> new NotFoundException("订单不存在"));
    }

    private void validateCancellation(OrderStatus actual, OrderStatus expected, OrderCancelledBy actor) {
        if (actual == OrderStatus.CANCELLED) {
            throw new StateConflictException("订单已取消", 40911);
        }
        if (actual == OrderStatus.COMPLETED) {
            throw new StateConflictException("订单已完成，不可取消", 40911);
        }
        if (actual == OrderStatus.SHIPPED && actor == OrderCancelledBy.CUSTOMER) {
            throw new StateConflictException("订单已开始发货，不可取消", 40911);
        }
        if (actual != expected) {
            throw new StateConflictException("订单状态已变化，请刷新后重试", 40904);
        }
    }
}
