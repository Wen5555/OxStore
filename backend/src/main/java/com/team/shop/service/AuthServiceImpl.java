package com.team.shop.service;

import com.team.shop.dto.response.LoginResult;
import com.team.shop.entity.Seller;
import com.team.shop.exception.UnauthorizedException;
import com.team.shop.repository.SellerRepository;
import com.team.shop.security.JwtUtil;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthServiceImpl implements AuthService {

    private final SellerRepository sellerRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtUtil jwtUtil;

    public AuthServiceImpl(SellerRepository sellerRepository, PasswordEncoder passwordEncoder, JwtUtil jwtUtil) {
        this.sellerRepository = sellerRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtUtil = jwtUtil;
    }

    @Override
    @Transactional(readOnly = true)
    public LoginResult login(String username, String password) {
        Seller seller = sellerRepository.findByUsername(username)
                .orElseThrow(() -> new UnauthorizedException("用户名或密码错误"));
        if (!passwordEncoder.matches(password, seller.getPasswordHash())) {
            throw new UnauthorizedException("用户名或密码错误");
        }
        return new LoginResult(jwtUtil.generate(seller.getUsername()), seller.getUsername());
    }

    @Override
    @Transactional
    public void changePassword(String oldPassword, String newPassword) {
        String username = SecurityContextHolder.getContext().getAuthentication().getName();
        Seller seller = sellerRepository.findByUsername(username)
                .orElseThrow(() -> new UnauthorizedException("登录已失效，请重新登录"));
        if (!passwordEncoder.matches(oldPassword, seller.getPasswordHash())) {
            throw new UnauthorizedException("旧密码错误");
        }
        seller.changePassword(passwordEncoder.encode(newPassword));
    }
}
