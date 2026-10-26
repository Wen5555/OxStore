package com.team.shop.service;

import com.team.shop.dto.request.FailAction;
import com.team.shop.dto.response.IntentResponse;

/**
 * 交易服务：卖家对指定商品的队首意向执行交易操作。
 */
public interface TradeService {

    /**
     * 选择队首意向开始交易。
     * <p>对应 POST /api/admin/intents/{id}/start（需 JWT）。
     * <p><b>事务 + 锁</b>：@Transactional，锁定商品行（串行化点）后锁定队列，
     * 校验"该意向为队首"+"商品在售"+"当前无交易中意向"，随后：意向→IN_TRANSACTION，商品→FROZEN(TRADE)。
     *
     * @param intentId 意向 id
     * @throws com.team.shop.exception.NotFoundException   意向或商品不存在（404）
     * @throws com.team.shop.exception.StateConflictException 非队首 / 商品非在售 / 已有交易中意向（409）
     */
    void startTrade(Long intentId);

    /**
     * 确认交易成功（成交）。
     * <p>对应 POST /api/admin/intents/{id}/success（需 JWT）。
     * <p><b>事务 + 锁</b>：@Transactional，锁定商品行；在同一事务内原子更新意向、库存和历史。
     *
     * @param intentId 意向 id
     * @throws com.team.shop.exception.NotFoundException   意向或商品不存在（404）
     * @throws com.team.shop.exception.StateConflictException 该意向非交易中（409）
     */
    void confirmSuccess(Long intentId);

    /**
     * 确认交易失败。
     * <p>对应 POST /api/admin/intents/{id}/fail（需 JWT）。
     * <p><b>事务 + 锁</b>：@Transactional，锁定商品行；在同一事务内原子更新：
     * 商品恢复在售；下一意向保持排队，不会自动开始交易。
     *
     * @param intentId 意向 id
     * @param action   REQUEUE=该意向回到队尾；DISCARD=该意向终结并记录失败历史
     * @throws com.team.shop.exception.NotFoundException   意向或商品不存在（404）
     * @throws com.team.shop.exception.StateConflictException 该意向非交易中（409）
     */
    void confirmFail(Long intentId, FailAction action);
}
