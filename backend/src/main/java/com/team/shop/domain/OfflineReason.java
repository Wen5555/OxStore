package com.team.shop.domain;

/** 商品下架原因，仅 OFFLINE 商品有意义；决定取消回补后能否自动恢复在售。 */
public enum OfflineReason {
    /** 库存为 0 自动下架；取消回补到正数时可自动恢复在售 */
    AUTO_ZERO,
    /** 商家手动下架；取消回补不改变下架状态 */
    MANUAL
}
