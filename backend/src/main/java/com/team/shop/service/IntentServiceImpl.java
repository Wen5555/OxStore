package com.team.shop.service;

import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.IntentStatus;
import com.team.shop.domain.ProductStateMachine;
import com.team.shop.domain.ProductStatus;
import com.team.shop.dto.response.IntentCreatedResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.dto.response.QueueItemResponse;
import com.team.shop.entity.Product;
import com.team.shop.entity.PurchaseIntent;
import com.team.shop.exception.BizException;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.StateConflictException;
import com.team.shop.exception.UnauthorizedException;
import com.team.shop.exception.PaginationException;
import com.team.shop.repository.CustomerRepository;
import com.team.shop.repository.IntentRepository;
import com.team.shop.repository.ProductRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Service
public class IntentServiceImpl implements IntentService {
    private static final int MAX_PAGE_SIZE = 100;
    private final IntentRepository intents;
    private final ProductRepository products;
    private final CustomerRepository customers;

    public IntentServiceImpl(IntentRepository intents, ProductRepository products, CustomerRepository customers) {
        this.intents = intents;
        this.products = products;
        this.customers = customers;
    }

    @Override
    @Transactional
    public IntentCreatedResponse submit(Long productId, Long customerId) {
        Product product = products.findByIdForUpdate(productId)
                .orElseThrow(() -> new NotFoundException("商品不存在"));
        if (!ProductStateMachine.isAcceptingIntent(product.getStatus())) {
            throw new StateConflictException("商品当前不可提交购买意向");
        }
        var customer = customers.findById(customerId)
                .orElseThrow(() -> new UnauthorizedException("顾客登录已失效"));
        PurchaseIntent intent = intents.saveAndFlush(PurchaseIntent.submit(
                product, customer, intents.maxQueueSeq(productId) + 1));
        return IntentCreatedResponse.from(intent);
    }

    @Override
    @Transactional(readOnly = true)
    public PageResponse<QueueItemResponse> getQueue(Long productId, int page, int size) {
        if (page < 1 || size < 1 || size > MAX_PAGE_SIZE) {
            throw new PaginationException("分页参数必须满足 page>=1 且 1<=size<=100");
        }
        products.findById(productId).orElseThrow(() -> new NotFoundException("商品不存在"));
        List<PurchaseIntent> ordered = new ArrayList<>();
        intents.findByProductIdAndStatus(productId, IntentStatus.IN_TRANSACTION).ifPresent(ordered::add);
        ordered.addAll(intents.findQueue(productId, IntentStatus.QUEUING));
        int from = (int) Math.min((long) (page - 1) * size, ordered.size());
        int to = Math.min(from + size, ordered.size());
        List<QueueItemResponse> items = new ArrayList<>();
        for (int index = from; index < to; index++) {
            PurchaseIntent intent = ordered.get(index);
            int position = intent.getStatus() == IntentStatus.IN_TRANSACTION
                    ? 0 : intents.findQueue(productId, IntentStatus.QUEUING).indexOf(intent) + 1;
            items.add(QueueItemResponse.from(intent, position));
        }
        return new PageResponse<>(items, page, size, ordered.size(),
                ordered.isEmpty() ? 0 : (int) Math.ceil((double) ordered.size() / size));
    }
}
