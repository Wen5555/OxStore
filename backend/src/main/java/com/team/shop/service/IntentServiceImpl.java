package com.team.shop.service;

import com.team.shop.domain.IntentStatus;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.ProductStatus;
import com.team.shop.domain.ProductStateMachine;
import com.team.shop.domain.TokenGenerator;
import com.team.shop.dto.response.IntentResponse;
import com.team.shop.dto.response.SubmitIntentResult;
import com.team.shop.entity.Product;
import com.team.shop.entity.PurchaseIntent;
import com.team.shop.exception.BizException;
import com.team.shop.exception.ForbiddenException;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.StateConflictException;
import com.team.shop.repository.IntentRepository;
import com.team.shop.repository.ProductRepository;
import com.team.shop.repository.TradeAttemptRepository;
import com.team.shop.security.TokenLookup;
import jakarta.persistence.EntityManager;
import jakarta.persistence.LockModeType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Service
public class IntentServiceImpl implements IntentService {

    private static final List<ProductStatus> ACTIVE_STATUSES =
            List.of(ProductStatus.ONLINE, ProductStatus.RESTORED_ONLINE, ProductStatus.FROZEN);

    private final IntentRepository intentRepository;
    private final ProductRepository productRepository;
    private final TradeAttemptRepository attemptRepository;
    private final EntityManager entityManager;
    private final TokenLookup tokenLookup;
    public IntentServiceImpl(IntentRepository intentRepository, ProductRepository productRepository,
                             TradeAttemptRepository attemptRepository, EntityManager entityManager, TokenLookup tokenLookup) {
        this.intentRepository = intentRepository;
        this.productRepository = productRepository;
        this.attemptRepository = attemptRepository;
        this.entityManager = entityManager;
        this.tokenLookup = tokenLookup;
    }

    @Override
    @Transactional
    public SubmitIntentResult submit(String buyerName, String buyerPhone) {
        Product product = productRepository.findActiveForUpdate(ACTIVE_STATUSES)
                .orElseThrow(() -> new NotFoundException("当前没有在售商品"));
        if (!ProductStateMachine.isAcceptingIntent(product.getStatus())) {
            throw new StateConflictException("商品已冻结或已售出，暂不能提交购买意向");
        }
        String rawToken = TokenGenerator.generate();
        PurchaseIntent intent = intentRepository.save(
                PurchaseIntent.submit(product, buyerName, buyerPhone, TokenGenerator.hash(rawToken),
                        tokenLookup.digest(rawToken), intentRepository.maxQueueSeq(product.getId()) + 1));
        int position = intentRepository.findQueue(product.getId(), IntentStatus.QUEUING).size();
        return new SubmitIntentResult(rawToken, position, intent.getStatus().name());
    }

    @Override
    @Transactional(readOnly = true)
    public IntentResponse queryByToken(String rawToken) {
        PurchaseIntent intent = resolveToken(rawToken);
        Integer position = intent.getStatus() == IntentStatus.QUEUING ? positionOf(intent) : null;
        return IntentResponse.from(intent, position);
    }

    @Override
    @Transactional
    public IntentResponse modifyByToken(String rawToken, String newName, String newPhone) {
        if (newName != null && newName.isBlank()) {
            throw new BizException("姓名不能为空");
        }
        if (newName == null && newPhone == null) {
            throw new BizException("请至少提供要修改的姓名或电话");
        }
        PurchaseIntent intent = lockVerifiedIntent(rawToken);
        intent.modifyInfo(newName, newPhone);
        return IntentResponse.from(intent, positionOf(intent));
    }

    @Override
    @Transactional
    public void cancelByToken(String rawToken) {
        lockVerifiedIntent(rawToken).cancel(BusinessTime.now());
    }

    @Override
    @Transactional(readOnly = true)
    public List<IntentResponse> getQueue() {
        Product product = productRepository.findActive(ACTIVE_STATUSES)
                .orElseThrow(() -> new NotFoundException("当前没有在售商品"));
        List<IntentResponse> result = new ArrayList<>();
        intentRepository.findByProductIdAndStatus(product.getId(), IntentStatus.IN_TRANSACTION)
                .ifPresent(trading -> result.add(IntentResponse.from(trading, 0, attemptRepository.findOpen(trading.getId())
                        .orElseThrow(() -> new StateConflictException("交易中意向缺少当前交易尝试")).getId())));
        List<PurchaseIntent> queue = intentRepository.findQueue(product.getId(), IntentStatus.QUEUING);
        for (int i = 0; i < queue.size(); i++) {
            result.add(IntentResponse.from(queue.get(i), i + 1));
        }
        return result;
    }

    private PurchaseIntent lockVerifiedIntent(String rawToken) {
        Long id = resolveToken(rawToken).getId();
        PurchaseIntent intent = intentRepository.findByIdForUpdate(id)
                .orElseThrow(() -> new ForbiddenException("口令码无效或已失效"));
        entityManager.refresh(intent, LockModeType.PESSIMISTIC_WRITE);
        // 锁定期间意向可能已被撤销、作废或成交，锁内需再校验一次
        if (!TokenGenerator.verify(rawToken, intent.getTokenHash())) {
            throw new ForbiddenException("口令码无效或已失效");
        }
        return intent;
    }

    private PurchaseIntent resolveToken(String rawToken) {
        if (rawToken == null || rawToken.isBlank()) throw new ForbiddenException("口令码无效或已失效");
        var indexed = intentRepository.findByTokenLookup(tokenLookup.digest(rawToken));
        if (indexed.isPresent() && TokenGenerator.verify(rawToken, indexed.get().getTokenHash())) {
            return indexed.get();
        }
        return intentRepository.findLegacyTokens().stream()
                .filter(i -> TokenGenerator.verify(rawToken, i.getTokenHash()))
                .findFirst()
                .orElseThrow(() -> new ForbiddenException("口令码无效或已失效"));
    }

    private Integer positionOf(PurchaseIntent intent) {
        List<PurchaseIntent> queue = intentRepository.findQueue(intent.getProduct().getId(), IntentStatus.QUEUING);
        for (int i = 0; i < queue.size(); i++) {
            if (queue.get(i).getId().equals(intent.getId())) {
                return i + 1;
            }
        }
        return null;
    }
}
