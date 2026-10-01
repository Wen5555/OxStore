package com.team.shop.service;

import com.team.shop.dto.response.PageResponse;
import com.team.shop.dto.response.ProductHistoryDetail;
import com.team.shop.dto.response.ProductResponse;

import java.math.BigDecimal;

/**
 * 商品服务。
 */
public interface ProductService {

    /**
     * 获取当前商品（在售/冻结），无商品返回 null。
     * <p>对应 GET /api/products/current（无需鉴权，买家可见）。
     * <p>不返回买家姓名/电话等敏感字段（商品本身不含）。
     */
    ProductResponse getCurrentProduct();

    /**
     * 获取当前商品（后台，含冻结来源等管理视图；与买家视图同构）。
     * <p>对应 GET /api/admin/products/current（需 JWT）。
     */
    ProductResponse getAdminCurrentProduct();

    /**
     * 发布新商品。
     * <p>对应 POST /api/admin/products（multipart，需 JWT）。
     * <p><b>事务 + 锁</b>：@Transactional，先 SELECT ... FOR UPDATE 锁定活跃商品行，
     * 校验"至多一件活跃商品"不变量后插入。
     *
     * @param name        商品名
     * @param description 描述
     * @param imagePath   已上传的图片路径
     * @param price       价格
     * @return 新商品
     * @throws com.team.shop.exception.StateConflictException 已存在 ONLINE/FROZEN/RESTORED_ONLINE 商品（409）
     */
    ProductResponse publish(String name, String description, String imagePath, BigDecimal price);

    /**
     * 历史商品列表（已售出），分页。
     * <p>对应 GET /api/admin/products/history（需 JWT）。页码从 1 开始。
     */
    PageResponse<ProductResponse> getHistory(int page, int size);

    /**
     * 历史商品详情 + 该商品全部意向（含成交/失败/撤销/未成交，需求 S-012）。
     * <p>对应 GET /api/admin/products/history/{id}（需 JWT）。
     *
     * @throws com.team.shop.exception.NotFoundException 商品不存在或未售出（404）
     */
    ProductHistoryDetail getHistoryDetail(Long id);
    ProductHistoryDetail getRecords(Long id);

    /**
     * 手动冻结当前商品。
     * <p>对应 POST /api/admin/products/current/freeze（需 JWT）。
     * <p><b>事务 + 锁</b>：@Transactional，锁定商品行。
     *
     * @throws com.team.shop.exception.NotFoundException  无当前商品（404）
     * @throws com.team.shop.exception.StateConflictException 非在售状态（409）
     */
    void freezeManually();

    /**
     * 手动解冻当前商品。
     * <p>对应 POST /api/admin/products/current/unfreeze（需 JWT）。
     * <p><b>事务 + 锁</b>：@Transactional，锁定商品行。
     *
     * @throws com.team.shop.exception.NotFoundException  无当前商品（404）
     * @throws com.team.shop.exception.StateConflictException 非"手动冻结"状态（409，交易中禁止解冻）
     */
    void unfreezeManually();
}
