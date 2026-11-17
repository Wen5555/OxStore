package com.team.shop.entity.converter;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

import java.math.BigDecimal;

/**
 * 订单金额以规范两位小数字符串（LONGTEXT）落库，总额没有列宽或精度上限。
 * 写入时要求本身不多于两位小数，不做舍入。
 */
@Converter
public class MoneyStringConverter implements AttributeConverter<BigDecimal, String> {
    @Override
    public String convertToDatabaseColumn(BigDecimal value) {
        return value == null ? null : value.setScale(2).toPlainString();
    }

    @Override
    public BigDecimal convertToEntityAttribute(String value) {
        return value == null ? null : new BigDecimal(value);
    }
}
