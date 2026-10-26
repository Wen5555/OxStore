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
import java.util.Map;

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
        return generate(0L, "SELLER", username);
    }

    public String generate(Long userId, String role, String username) {
        Date now = new Date();
        return Jwts.builder()
                .subject(username)
                .claims(Map.of("userId", userId, "role", role))
                .issuedAt(now)
                .expiration(new Date(now.getTime() + expireMs))
                .signWith(key)
                .compact();
    }

    public UserIdentity parseIdentity(String token) {
        Claims claims = Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
        Object userId = claims.get("userId");
        Object role = claims.get("role");
        if (!(userId instanceof Number id) || !(role instanceof String roleName)) {
            return null;
        }
        return new UserIdentity(id.longValue(), claims.getSubject(), roleName);
    }

    /** 解析用户名，无效或过期返回 null */
    public String parseUsername(String token) {
        try {
            return parseIdentity(token).getName();
        } catch (Exception e) {
            return null;
        }
    }
}
