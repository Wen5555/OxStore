package com.team.shop.service;

import com.team.shop.dto.request.FailAction;
import com.team.shop.dto.response.IntentResponse;

/**
 * 交易服务：卖家对队首意向的"开始交易 / 确认成功 / 确认失败"。
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
     * <p><b>事务 + 锁</b>：@Transactional，锁定商品行；在同一事务内原子更新：
     * 该意向→SUCCESS，商品→SOLD，其余 QUEUING 意向→UNSOLD。
     *
     * @param intentId 意向 id
     * @throws com.team.shop.exception.NotFoundException   意向或商品不存在（404）
     * @throws com.team.shop.exception.StateConflictException 该意向非交易中（409）
     */
    void confirmSuccess(Long intentId, Long tradeAttemptId);

    /**
     * 确认交易失败。
     * <p>对应 POST /api/admin/intents/{id}/fail（需 JWT）。
     * <p><b>事务 + 锁</b>：@Transactional，锁定商品行；在同一事务内原子更新：
     * 商品→RESTORED_ONLINE；若队列非空则自动递补队首并再次商品→FROZEN(TRADE)、新队首→IN_TRANSACTION。
     *
     * @param intentId 意向 id
     * @param action   REQUEUE=该意向回到队尾（原口令继续有效）；DISCARD=该意向→FAILED且口令失效
     * @return 递补后新的交易中意向（架构 7.4.2：data.nextIntent）；队列为空时为 null
     * @throws com.team.shop.exception.NotFoundException   意向或商品不存在（404）
     * @throws com.team.shop.exception.StateConflictException 该意向非交易中（409）
     */
    IntentResponse confirmFail(Long intentId, FailAction action, Long tradeAttemptId);
}
