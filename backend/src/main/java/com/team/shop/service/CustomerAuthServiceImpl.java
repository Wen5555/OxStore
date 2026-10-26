package com.team.shop.service;

import com.team.shop.dto.response.CustomerResponse;
import com.team.shop.dto.response.LoginResult;
import com.team.shop.domain.BusinessTime;
import com.team.shop.entity.Customer;
import com.team.shop.exception.StateConflictException;
import com.team.shop.exception.AuthenticationFailureException;
import com.team.shop.exception.DuplicateUsernameException;
import com.team.shop.exception.UnauthorizedException;
import com.team.shop.repository.CustomerRepository;
import com.team.shop.security.JwtUtil;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;


@Service
public class CustomerAuthServiceImpl implements CustomerAuthService {
    private final CustomerRepository customers;
    private final PasswordEncoder encoder;
    private final JwtUtil jwt;

    public CustomerAuthServiceImpl(CustomerRepository customers, PasswordEncoder encoder, JwtUtil jwt) {
        this.customers = customers;
        this.encoder = encoder;
        this.jwt = jwt;
    }

    @Override
    @Transactional
    public CustomerResponse register(String username, String password, String phone, String location) {
        if (username == null || username.isBlank() || password == null || password.length() < 8
                || phone == null || phone.isBlank()) {
            throw new com.team.shop.exception.BizException("用户名、至少 8 位密码和电话均为必填项");
        }
        if (customers.existsByUsername(username)) {
            throw new DuplicateUsernameException("用户名已存在");
        }
        Customer customer = new Customer(username.trim(), encoder.encode(password), phone.trim(),
                location == null || location.isBlank() ? null : location.trim(), BusinessTime.now());
        try {
            return CustomerResponse.from(customers.saveAndFlush(customer));
        } catch (DataIntegrityViolationException ex) {
            throw new DuplicateUsernameException("用户名已存在");
        }
    }

    @Override
    @Transactional(readOnly = true)
    public LoginResult login(String username, String password) {
        Customer customer = customers.findByUsername(username)
                .orElseThrow(() -> new AuthenticationFailureException("用户名或密码错误"));
        if (!encoder.matches(password, customer.getPasswordHash())) {
            throw new AuthenticationFailureException("用户名或密码错误");
        }
        return new LoginResult(jwt.generate(customer.getId(), "CUSTOMER", customer.getUsername()),
                customer.getId(), "CUSTOMER", customer.getUsername());
    }
}
