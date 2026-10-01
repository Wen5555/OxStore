package com.team.shop.domain;
import java.time.LocalDateTime;
import java.time.ZoneId;
public final class BusinessTime {
    private static final ZoneId ZONE = ZoneId.of("Asia/Shanghai");
    private BusinessTime() { }
    public static LocalDateTime now() { return LocalDateTime.now(ZONE); }
}
