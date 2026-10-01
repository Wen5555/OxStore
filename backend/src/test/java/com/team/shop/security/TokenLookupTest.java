package com.team.shop.security;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class TokenLookupTest {
    @Test void keyedDigestIsStableAndSecretDependent() {
        var a = new TokenLookup("1234567890abcdef1234567890abcdef");
        var b = new TokenLookup("fedcba0987654321fedcba0987654321");
        assertEquals(64, a.digest("BuyerCode").length());
        assertEquals(a.digest("BuyerCode"), a.digest("BuyerCode"));
        assertNotEquals(a.digest("BuyerCode"), b.digest("BuyerCode"));
        assertThrows(IllegalArgumentException.class, () -> new TokenLookup("short"));
    }
}
