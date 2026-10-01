package com.team.shop.domain;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * 口令码生成与校验单测。
 */
class TokenGeneratorTest {

    private static final String ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz";

    @Test
    void generate_returnsEightCharsFromAlphabet() {
        for (int i = 0; i < 100; i++) {
            String token = TokenGenerator.generate();
            assertEquals(8, token.length());
            for (char c : token.toCharArray()) {
                assertTrue(ALPHABET.indexOf(c) >= 0, "含易混淆字符: " + c);
            }
        }
    }

    @Test
    void generate_returnsRandomDistinctTokens() {
        assertNotEquals(TokenGenerator.generate(), TokenGenerator.generate());
    }

    @Test
    void hashAndVerify_roundTrip() {
        String token = TokenGenerator.generate();
        String hash = TokenGenerator.hash(token);
        assertNotNull(hash);
        assertNotEquals(token, hash, "库中不应存明文口令码");
        assertTrue(TokenGenerator.verify(token, hash));
    }

    @Test
    void verify_rejectsWrongToken() {
        String hash = TokenGenerator.hash("ABCDEFGH");
        assertFalse(TokenGenerator.verify("ZZZZZZZZ", hash));
    }

    @Test
    void verify_rejectsNullInputs() {
        String hash = TokenGenerator.hash("ABCDEFGH");
        assertFalse(TokenGenerator.verify(null, hash));
        assertFalse(TokenGenerator.verify("ABCDEFGH", null));
        assertFalse(TokenGenerator.verify(null, null));
    }
}
