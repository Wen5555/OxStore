package com.team.shop.dto.response;

import java.util.List;

public record PageResponse<T>(List<T> items, int page, int size, long total, int pages) {
    public PageResponse(List<T> items, long total, int page, int size) {
        this(items, page, size, total, size == 0 ? 0 : (int) Math.ceil((double) total / size));
    }
}
