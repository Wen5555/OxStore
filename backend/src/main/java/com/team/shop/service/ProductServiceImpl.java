package com.team.shop.service;

import com.team.shop.domain.ProductStatus;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.ProductEventType;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.dto.response.ProductHistoryDetail;
import com.team.shop.dto.response.ProductResponse;
import com.team.shop.entity.Product;
import com.team.shop.entity.ProductStatusEvent;
import com.team.shop.exception.BizException;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.StateConflictException;
import com.team.shop.repository.IntentRepository;
import com.team.shop.repository.ProductRepository;
import com.team.shop.repository.TradeAttemptRepository;
import com.team.shop.repository.ProductStatusEventRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;

@Service
public class ProductServiceImpl implements ProductService {

    private static final List<ProductStatus> ACTIVE_STATUSES =
            List.of(ProductStatus.ONLINE, ProductStatus.RESTORED_ONLINE, ProductStatus.FROZEN);

    private final ProductRepository productRepository;
    private final IntentRepository intentRepository;
    private final TradeAttemptRepository attemptRepository;
    private final ProductStatusEventRepository eventRepository;
    private final String historyCompleteSince;
    public ProductServiceImpl(ProductRepository productRepository, IntentRepository intentRepository,
                              TradeAttemptRepository attemptRepository, ProductStatusEventRepository eventRepository,
                              @Value("${shop.history-complete-since:}") String historyCompleteSince) {
        this.productRepository = productRepository;
        this.intentRepository = intentRepository;
        this.attemptRepository = attemptRepository;
        this.eventRepository = eventRepository;
        this.historyCompleteSince = historyCompleteSince;
    }

    @Override
    @Transactional(readOnly = true)
    public ProductResponse getCurrentProduct() {
        return productRepository.findActive(ACTIVE_STATUSES)
                .map(ProductResponse::from)
                .orElse(null);
    }

    @Override
    @Transactional(readOnly = true)
    public ProductResponse getAdminCurrentProduct() {
        return getCurrentProduct();
    }

    @Override
    @Transactional
    public ProductResponse publish(String name, String description, String imagePath, BigDecimal price) {
        if (name == null || name.isBlank()) {
            throw new BizException("商品名称不能为空");
        }
        if (description == null || description.isBlank()) {
            throw new BizException("商品描述不能为空");
        }
        if (price == null || price.signum() <= 0) {
            throw new BizException("价格必须为正数");
        }
        if (price.scale() > 2) {
            throw new BizException("价格最多两位小数");
        }
        productRepository.findActiveForUpdate(ACTIVE_STATUSES).ifPresent(existing -> {
            throw new StateConflictException("已存在在售或冻结中的商品，不可同时发布第二件");
        });
        Product product = Product.create(name, description, imagePath, price);
        try {
            productRepository.save(product);
            eventRepository.save(new ProductStatusEvent(product, null, ProductEventType.PUBLISHED, null, product.getPublishedAt()));
            return ProductResponse.from(product);
        } catch (DataIntegrityViolationException e) {
            // 无活跃商品时没有行可锁，两个并发发布会同时走到插入；由数据库唯一索引兜底并翻译为 409
            throw new StateConflictException("已存在在售或冻结中的商品，不可同时发布第二件");
        }
    }

    @Override
    @Transactional(readOnly = true)
    public PageResponse<ProductResponse> getHistory(int page, int size) {
        // 页码从 1 开始（架构文档 7.1）
        int safePage = Math.max(page, 1);
        int safeSize = Math.min(Math.max(size, 1), 100);
        List<ProductResponse> all = productRepository.findByStatusOrderBySoldAtDescIdDesc(ProductStatus.SOLD)
                .stream()
                .map(ProductResponse::from)
                .toList();
        int from = (int) Math.min((long) (safePage - 1) * safeSize, all.size());
        int to = Math.min(from + safeSize, all.size());
        return new PageResponse<>(all.subList(from, to), all.size(), safePage, safeSize);
    }

    @Override
    @Transactional(readOnly = true)
    public ProductHistoryDetail getHistoryDetail(Long id) {
        Product product = productRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("商品不存在"));
        if (product.getStatus() != ProductStatus.SOLD) {
            throw new NotFoundException("商品未售出，不在历史记录中");
        }
        return records(product);
    }

    @Override
    @Transactional(readOnly = true)
    public ProductHistoryDetail getRecords(Long id) {
        return records(productRepository.findById(id).orElseThrow(() -> new NotFoundException("商品不存在")));
    }
    private ProductHistoryDetail records(Product product) {
        Long id = product.getId();
        return ProductHistoryDetail.from(product, intentRepository.findAllByProduct(id),
                attemptRepository.findAllByProduct(id), eventRepository.findAllByProduct(id), historyCompleteSince);
    }
    @Override
    @Transactional
    public void freezeManually() {
        Product product = requireActiveForUpdate();
        var before = product.getStatus();
        var now = BusinessTime.now();
        product.freezeManually(now);
        eventRepository.save(new ProductStatusEvent(product, null, ProductEventType.MANUAL_FREEZE, before, now));
    }

    @Override
    @Transactional
    public void unfreezeManually() {
        Product product = requireActiveForUpdate();
        var before = product.getStatus();
        var now = BusinessTime.now();
        product.unfreezeManually(now);
        eventRepository.save(new ProductStatusEvent(product, null, ProductEventType.MANUAL_UNFREEZE, before, now));
    }

    private Product requireActiveForUpdate() {
        return productRepository.findActiveForUpdate(ACTIVE_STATUSES)
                .orElseThrow(() -> new NotFoundException("当前没有在售商品"));
    }
}
