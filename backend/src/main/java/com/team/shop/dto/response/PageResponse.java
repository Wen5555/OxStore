package com.team.shop.dto.response;

import java.util.List;

/**
 * 分页响应。
 */
public record PageResponse<T>(List<T> list, long total, int page, int size) {
}
