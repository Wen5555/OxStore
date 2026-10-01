package com.team.shop.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.Locale;

/**
 * JWT 生成与解析。用于卖家后台认证。
 */
@Component
public class JwtUtil {

    private final SecretKey key;
    private final long expireMs;

    public JwtUtil(@Value("${shop.jwt.secret}") String secret,
                   @Value("${shop.jwt.expire-ms}") long expireMs) {
        String lower = secret == null ? "" : secret.toLowerCase(Locale.ROOT);
        if (secret == null || secret.getBytes(StandardCharsets.UTF_8).length < 32
                || lower.contains("change-me") || lower.contains("replace_")
                || lower.contains("example") || lower.contains("your-secret")
                || lower.contains("test-secret")) {
            throw new IllegalArgumentException("JWT_SECRET 必须为至少 32 字节的随机密钥，且不能使用公开或示例值");
        }
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.expireMs = expireMs;
    }

    public String generate(String username) {
        Date now = new Date();
        return Jwts.builder()
                .subject(username)
                .issuedAt(now)
                .expiration(new Date(now.getTime() + expireMs))
                .signWith(key)
                .compact();
    }

    /** 解析用户名，无效或过期返回 null */
    public String parseUsername(String token) {
        try {
            Claims claims = Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
            return claims.getSubject();
        } catch (Exception e) {
            return null;
        }
    }
}
