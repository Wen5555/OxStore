package com.team.shop.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;
import java.util.Locale;

/** 新口令的数据库索引键；与 BCrypt 密码校验分离，密钥不得随 JWT 轮换。 */
@Component
public class TokenLookup {
    private final SecretKeySpec key;
    public TokenLookup(@Value("${shop.token-lookup-key}") String secret) {
        String lower = secret == null ? "" : secret.toLowerCase(Locale.ROOT);
        if (secret == null || secret.getBytes(StandardCharsets.UTF_8).length < 32
                || lower.contains("replace_") || lower.contains("example") || lower.contains("change-me")) {
            throw new IllegalArgumentException("TOKEN_LOOKUP_KEY 须为至少 32 字节的随机密钥，且不得使用示例值");
        }
        key = new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256");
    }
    public String digest(String rawToken) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(key);
            return HexFormat.of().formatHex(mac.doFinal(rawToken.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new IllegalStateException("口令索引计算失败", e);
        }
    }
}
