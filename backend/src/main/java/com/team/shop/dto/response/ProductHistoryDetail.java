package com.team.shop.dto.response;
import com.team.shop.entity.*;
import java.time.LocalDateTime;
import java.util.List;
/** 卖家专用商品记录；存量截止时间由部署配置标明，不能据空历史推断从未发生。 */
public record ProductHistoryDetail(ProductResponse product, List<IntentResponse> intents,
                                   List<TradeAttemptResponse> tradeAttempts,
                                   List<ProductStatusEventResponse> statusEvents,
                                   boolean legacyRecordsMayBeIncomplete, String historyCompleteSince) {
    public static ProductHistoryDetail from(Product product, List<PurchaseIntent> intents,
                                             List<TradeAttempt> attempts, List<ProductStatusEvent> events,
                                             String completeSince) {
        boolean migrated = completeSince != null && !completeSince.isBlank();
        boolean legacy = migrated && !product.getPublishedAt().isAfter(LocalDateTime.parse(completeSince));
        return new ProductHistoryDetail(ProductResponse.from(product),
                intents.stream().map(i -> IntentResponse.from(i, null)).toList(),
                attempts.stream().map(TradeAttemptResponse::from).toList(),
                events.stream().map(ProductStatusEventResponse::from).toList(),
                legacy, migrated ? completeSince : null);
    }
}
