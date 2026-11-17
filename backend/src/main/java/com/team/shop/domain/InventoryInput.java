package com.team.shop.domain;

import com.team.shop.exception.BizException;
import java.math.BigInteger;

public final class InventoryInput {
    public static final String ERROR = "库存不能为负数，请输入非负整数。";
    private InventoryInput() { }
    public static BigInteger parse(String value) {
        if (value == null || !value.matches("(?:0|[1-9][0-9]*)")) throw new BizException(ERROR);
        return new BigInteger(value);
    }
}
