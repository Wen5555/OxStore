package com.team.shop.service;

import com.team.shop.dto.response.LoginResult;

/**
 * 卖家认证服务。
 */
public interface AuthService {

    /**
     * 登录。
     * <p>对应 POST /api/admin/auth/login（无需鉴权）。
     *
     * @param username 用户名
     * @param password 明文密码
     * @return JWT + 用户名
     * @throws com.team.shop.exception.UnauthorizedException 用户名不存在或密码错误（401）
     */
    LoginResult login(String username, String password);

    /**
     * 修改密码（需校验旧密码）。
     * <p>对应 PUT /api/admin/auth/password（需 JWT）。
     *
     * @param oldPassword 旧密码
     * @param newPassword 新密码
     * @throws com.team.shop.exception.UnauthorizedException 旧密码错误（401）
     */
    void changePassword(String oldPassword, String newPassword);
}
