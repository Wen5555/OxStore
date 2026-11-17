package com.team.shop.domain;

import com.team.shop.exception.StateConflictException;

/** Fixed-price whole-order transitions; never touches inventory or legacy intent states. */
public final class OrderStateMachine {
    public enum Action { CONFIRM, PREPARE, SHIP, COMPLETE }
    private OrderStateMachine() { }
    public static OrderStatus next(OrderStatus actual, OrderStatus expected, Action action) {
        if (actual == OrderStatus.CANCELLED)
            throw new StateConflictException(action == Action.SHIP ? "订单已取消，不可发货" : "订单已取消，不可推进",40911);
        if (actual == OrderStatus.COMPLETED) throw new StateConflictException("订单已完成，不可推进",40911);
        if (actual != expected) throw new StateConflictException("订单状态已变化，请刷新后重试",40904);
        boolean allowed = switch (actual) {
            case PLACED -> action == Action.CONFIRM;
            case CONFIRMED -> action == Action.PREPARE;
            case PREPARED -> action == Action.SHIP;
            case SHIPPED -> action == Action.COMPLETE;
            default -> false;
        };
        if (!allowed) throw new StateConflictException("订单不允许跳步、回退或重复推进",40911);
        return switch (action) {
            case CONFIRM -> OrderStatus.CONFIRMED;
            case PREPARE -> OrderStatus.PREPARED;
            case SHIP -> OrderStatus.SHIPPED;
            case COMPLETE -> OrderStatus.COMPLETED;
        };
    }
}
