package com.team.shop.entity.converter;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

import java.math.BigInteger;

/**
 * 库存/数量以规范十进制字符串（LONGTEXT）落库，没有 int/long 上限。
 * 不能在 SQL 里做数值比较或排序，运算一律在持有行锁后用 BigInteger 完成。
 */
@Converter
public class BigIntegerStringConverter implements AttributeConverter<BigInteger, String> {
    @Override
    public String convertToDatabaseColumn(BigInteger value) {
        return value == null ? null : value.toString();
    }

    @Override
    public BigInteger convertToEntityAttribute(String value) {
        return value == null ? null : new BigInteger(value);
    }
}
