package com.team.shop.domain;

/** 需要请求幂等键的写操作类型，与 operation_receipt.operation_type 一一对应。 */
public enum ReceiptOperationType {
    CART_ADD,
    CHECKOUT,
    MOVE_TO_FAVORITES
}
