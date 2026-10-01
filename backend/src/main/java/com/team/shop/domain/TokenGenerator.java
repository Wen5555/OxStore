package com.team.shop.domain;

import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

import java.security.SecureRandom;

/**
 * 口令码生成与校验。明文仅首次生成时返回，库中只存 BCrypt 哈希。
 */
public final class TokenGenerator {

    /** 去除易混淆字符（0/O、1/l/I）后的字符集 */
    private static final String ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz";
    private static final int LENGTH = 8;
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final BCryptPasswordEncoder ENCODER = new BCryptPasswordEncoder();

    private TokenGenerator() {
    }

    /** 生成 8 位随机口令码 */
    public static String generate() {
        StringBuilder sb = new StringBuilder(LENGTH);
        for (int i = 0; i < LENGTH; i++) {
            sb.append(ALPHABET.charAt(RANDOM.nextInt(ALPHABET.length())));
        }
        return sb.toString();
    }

    /** 计算口令码的 BCrypt 哈希 */
    public static String hash(String rawToken) {
        return ENCODER.encode(rawToken);
    }

    /** 校验明文口令码是否与哈希匹配 */
    public static boolean verify(String rawToken, String hash) {
        if (rawToken == null || hash == null) {
            return false;
        }
        return ENCODER.matches(rawToken, hash);
    }
}
