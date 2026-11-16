package com.team.shop.dto.request;

import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import com.team.shop.domain.InventoryInput;

@JsonDeserialize(using = ProductUpdateRequest.Deserializer.class)
public record ProductUpdateRequest(String stock,
                                   Long category2Id) {
    public java.math.BigInteger parsedStock() { return stock == null ? null : InventoryInput.parse(stock); }
    public boolean hasChanges() { return stock != null || category2Id != null; }

    public static class Deserializer extends com.fasterxml.jackson.databind.JsonDeserializer<ProductUpdateRequest> {
        @Override public ProductUpdateRequest deserialize(com.fasterxml.jackson.core.JsonParser p,
                com.fasterxml.jackson.databind.DeserializationContext context) throws java.io.IOException {
            com.fasterxml.jackson.databind.JsonNode body = p.getCodec().readTree(p);
            if (!body.isObject()) throw new com.team.shop.exception.BizException("请求体必须为对象");
            var fields = body.fieldNames();
            while (fields.hasNext()) {
                if (!java.util.Set.of("stock", "category2Id").contains(fields.next()))
                    throw new com.team.shop.exception.ApiBusinessException(400, 40002, "发布后只允许修改库存和二级类目", null);
            }
            String stock = null;
            if (body.has("stock")) {
                if (!body.get("stock").isTextual()) throw new com.team.shop.exception.BizException(InventoryInput.ERROR);
                stock = body.get("stock").textValue(); InventoryInput.parse(stock);
            }
            Long category = null;
            if (body.has("category2Id")) {
                var value = body.get("category2Id");
                if (!value.isIntegralNumber() || !value.canConvertToLong() || value.longValue() <= 0)
                    throw new com.team.shop.exception.BizException("必须选择二级类目");
                category = value.longValue();
            }
            return new ProductUpdateRequest(stock, category);
        }
    }
}
