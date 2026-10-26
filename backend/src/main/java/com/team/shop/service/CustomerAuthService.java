package com.team.shop.service;

import com.team.shop.dto.response.CustomerResponse;
import com.team.shop.dto.response.LoginResult;

public interface CustomerAuthService {
    CustomerResponse register(String username, String password, String phone, String location);
    LoginResult login(String username, String password);
}
