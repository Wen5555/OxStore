package com.team.shop.dto.response;

/**
 * 提交购买意向的响应：明文口令码 + 当前位次 + 意向状态。
 * 口令码仅在此次响应中返回一次，库中只存哈希。
 */
public record SubmitIntentResult(String code, int position, String status) {
}
