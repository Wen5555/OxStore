package com.team.shop.controller;

import com.team.shop.dto.ApiResponse;
import com.team.shop.dto.request.CustomerLoginRequest;
import com.team.shop.dto.request.RegisterRequest;
import com.team.shop.dto.response.CustomerResponse;
import com.team.shop.dto.response.LoginResult;
import com.team.shop.service.CustomerAuthService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class CustomerAuthController {
    private final CustomerAuthService customers;

    public CustomerAuthController(CustomerAuthService customers) {
        this.customers = customers;
    }

    @PostMapping("/register")
    public ResponseEntity<ApiResponse<CustomerResponse>> register(@Valid @RequestBody RegisterRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(
                ApiResponse.ok(customers.register(request.username(), request.password(),
                        request.phone(), request.location())));
    }

    @PostMapping("/login")
    public ApiResponse<LoginResult> login(@Valid @RequestBody CustomerLoginRequest request) {
        return ApiResponse.ok(customers.login(request.username(), request.password()));
    }
}
