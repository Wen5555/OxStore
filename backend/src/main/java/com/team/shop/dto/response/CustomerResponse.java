package com.team.shop.dto.response;

import com.team.shop.entity.Customer;

import java.time.LocalDateTime;

public record CustomerResponse(Long customerId, String username, String phone, String location,
                              LocalDateTime registeredAt) {
    public static CustomerResponse from(Customer customer) {
        return new CustomerResponse(customer.getId(), customer.getUsername(), customer.getPhone(),
                customer.getLocation() == null || customer.getLocation().isBlank()
                        ? "未设置" : customer.getLocation(),
                customer.getRegisteredAt());
    }
}
