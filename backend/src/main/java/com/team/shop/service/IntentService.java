package com.team.shop.service;

import com.team.shop.dto.response.IntentResponse;
import com.team.shop.dto.response.SubmitIntentResult;

import java.util.List;

/**
 * 购买意向服务（买家侧提交/查询/修改/撤销 + 后台队列视图）。
 */
public interface IntentService {

    /**
     * 提交购买意向。
     * <p>对应 POST /api/intents（无需鉴权）。
     * <p><b>事务 + 锁</b>：@Transactional，锁定商品行校验"可接收意向"后插入意向并返回明文口令码。
     *
     * @param buyerName  买家姓名
     * @param buyerPhone 买家电话
     * @return 明文口令码（仅此一次）、位次、状态
     * @throws com.team.shop.exception.NotFoundException  无当前商品（404）
     * @throws com.team.shop.exception.StateConflictException 商品不可接收意向（409，已冻结/已售/交易中）
     */
    SubmitIntentResult submit(String buyerName, String buyerPhone);

    /**
     * 凭口令码查询本人意向与位次。
     * <p>对应 GET /api/intents/{code}（无需鉴权）。
     *
     * @param rawToken 明文口令码
     * @return 意向信息（position 为当前位次，仅 QUEUING 时有意义）
     * @throws com.team.shop.exception.ForbiddenException 口令码无效或已失效（403）
     */
    IntentResponse queryByToken(String rawToken);

    /**
     * 凭口令码修改姓名/电话（传 null 的字段保持原值，需求 B-006）。
     * <p>对应 PUT /api/intents/{code}（无需鉴权）。
     * <p><b>事务 + 锁</b>：@Transactional，锁定意向行。
     *
     * @throws com.team.shop.exception.ForbiddenException   口令码无效或已失效（403）
     * @throws com.team.shop.exception.StateConflictException 非排队中状态（409）
     * @throws com.team.shop.exception.BizException           姓名与电话均未提供（400）
     */
    IntentResponse modifyByToken(String rawToken, String newName, String newPhone);

    /**
     * 凭口令码撤销排队意向。
     * <p>对应 DELETE /api/intents/{code}（无需鉴权）。
     * <p><b>事务 + 锁</b>：@Transactional，锁定意向行。
     *
     * @throws com.team.shop.exception.ForbiddenException   口令码无效或已失效（403）
     * @throws com.team.shop.exception.StateConflictException 非排队中状态（409）
     */
    void cancelByToken(String rawToken);

    /**
     * 查看当前商品的意向队列（后台，需求 S-007：显示所有意向的姓名、电话、提交时间、状态、队列顺序）。
     * <p>对应 GET /api/admin/intents（需 JWT）。
     * <p>返回交易中意向（若有，排第一位）+ 全部 QUEUING 意向（按 (submittedAt, id) 升序）；
     * 排队意向的 position 为位次（交易中意向计为位次 0 占位，前端按 status 区分展示）。
     */
    List<IntentResponse> getQueue();
}
