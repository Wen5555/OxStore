package com.team.shop.security;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class JwtUtilTest {
    @Test void rejectsOldAndPlaceholderSecrets() {
        assertThrows(IllegalArgumentException.class, () -> new JwtUtil("change-me-in-production-please-use-a-long-random-string-0123456789", 1000));
        assertThrows(IllegalArgumentException.class, () -> new JwtUtil("short", 1000));
        assertThrows(IllegalArgumentException.class, () -> new JwtUtil("REPLACE_WITH_RANDOM_SECRET_123456789", 1000));
    }
    @Test void generatedTokensCanBeVerifiedOnlyWithSameKey() {
        var jwt = new JwtUtil("1234567890abcdef1234567890abcdef", 100000);
        String token = jwt.generate("admin");
        assertEquals("admin", jwt.parseUsername(token));
        assertNull(new JwtUtil("fedcba0987654321fedcba0987654321", 100000).parseUsername(token));
    }
}
