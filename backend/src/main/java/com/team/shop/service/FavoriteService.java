package com.team.shop.service;

import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.ProductStatus;
import com.team.shop.domain.SellingMode;
import com.team.shop.dto.response.FavoriteItemResponse;
import com.team.shop.dto.response.FavoriteStateResponse;
import com.team.shop.dto.response.FavoriteWriteResponse;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.entity.Customer;
import com.team.shop.entity.Favorite;
import com.team.shop.entity.FavoriteMutation;
import com.team.shop.entity.Product;
import com.team.shop.exception.ApiBusinessException;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.PaginationException;
import com.team.shop.exception.StateConflictException;
import com.team.shop.repository.CustomerRepository;
import com.team.shop.repository.FavoriteMutationRepository;
import com.team.shop.repository.FavoriteRepository;
import com.team.shop.repository.ProductRepository;
import com.team.shop.security.CustomerAccess;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Optional;
import java.time.temporal.ChronoUnit;

@Service
public class FavoriteService {
    private static final int PAGE_SIZE = 10;

    private final CustomerAccess customerAccess;
    private final CustomerRepository customers;
    private final ProductRepository products;
    private final FavoriteRepository favorites;
    private final FavoriteMutationRepository mutations;

    public FavoriteService(CustomerAccess customerAccess, CustomerRepository customers,
                           ProductRepository products, FavoriteRepository favorites,
                           FavoriteMutationRepository mutations) {
        this.customerAccess = customerAccess;
        this.customers = customers;
        this.products = products;
        this.favorites = favorites;
        this.mutations = mutations;
    }

    @Transactional
    public FavoriteWriteResponse add(Long productId) {
        Long customerId = customerAccess.requireCustomerId();
        Customer customer = lockCustomer(customerId);
        Product product = products.findByIdForUpdate(productId)
                .orElseThrow(() -> new NotFoundException("商品不存在"));
        requireFixedPrice(product, "收藏");
        if (product.getStatus() != ProductStatus.ONLINE) {
            throw new StateConflictException("商品已下架", 40901);
        }

        Favorite favorite = favorites.findForUpdate(customerId, productId).orElse(null);
        FavoriteMutation mutation = getOrCreateMutation(customerId, productId);
        if (favorite == null) {
            favorite = favorites.saveAndFlush(new Favorite(customer, product,
                    BusinessTime.now().truncatedTo(ChronoUnit.MICROS)));
            mutation.recordWrite();
        }
        return FavoriteWriteResponse.from(favorite);
    }

    @Transactional
    public String remove(Long productId) {
        Long customerId = customerAccess.requireCustomerId();
        lockCustomer(customerId);
        Optional<Favorite> existing = favorites.findByCustomerIdAndProductId(customerId, productId);
        if (existing.isEmpty()) {
            return "未收藏";
        }

        products.findByIdForUpdate(productId)
                .orElseThrow(() -> new IllegalStateException("收藏记录关联的商品不存在"));
        Favorite favorite = favorites.findForUpdate(customerId, productId).orElse(null);
        if (favorite == null) {
            return "未收藏";
        }
        getOrCreateMutation(customerId, productId).recordCancel();
        favorites.delete(favorite);
        return "已取消收藏";
    }

    @Transactional(readOnly = true)
    public PageResponse<FavoriteItemResponse> list(int page, int size) {
        if (page < 1 || size != PAGE_SIZE) {
            throw new PaginationException("收藏列表 page>=1 且 size 必须为 10");
        }
        Long customerId = customerAccess.requireCustomerId();
        Page<Favorite> result = favorites.findByCustomerIdOrderByCreatedAtDescIdDesc(
                customerId, PageRequest.of(page - 1, PAGE_SIZE));
        return new PageResponse<>(result.getContent().stream().map(FavoriteItemResponse::from).toList(),
                page, PAGE_SIZE, result.getTotalElements(), result.getTotalPages());
    }

    @Transactional(readOnly = true)
    public FavoriteStateResponse state(Long productId) {
        Long customerId = customerAccess.requireCustomerId();
        return FavoriteStateResponse.from(favorites.findByCustomerIdAndProductId(customerId, productId));
    }

    private Customer lockCustomer(Long customerId) {
        return customers.findByIdForUpdate(customerId)
                .orElseThrow(() -> new ApiBusinessException(401, 40101, "请重新登录", null));
    }

    private FavoriteMutation getOrCreateMutation(Long customerId, Long productId) {
        return mutations.findForUpdate(customerId, productId)
                .orElseGet(() -> mutations.save(new FavoriteMutation(customerId, productId)));
    }

    private void requireFixedPrice(Product product, String operation) {
        if (product.getSellingMode() != SellingMode.FIXED_PRICE) {
            throw new StateConflictException("拍卖商品不能" + operation, 40908);
        }
    }
}
