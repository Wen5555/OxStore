package com.team.shop.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.ProductStatus;
import com.team.shop.domain.ReceiptOperationType;
import com.team.shop.domain.SellingMode;
import com.team.shop.dto.response.CartItemResponse;
import com.team.shop.dto.response.CartResponse;
import com.team.shop.entity.CartItem;
import com.team.shop.entity.CartItemTombstone;
import com.team.shop.entity.Customer;
import com.team.shop.entity.OperationReceipt;
import com.team.shop.entity.Product;
import com.team.shop.exception.ApiBusinessException;
import com.team.shop.exception.ForbiddenException;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.StateConflictException;
import com.team.shop.repository.CartItemRepository;
import com.team.shop.repository.CartItemTombstoneRepository;
import com.team.shop.repository.CustomerRepository;
import com.team.shop.repository.OperationReceiptRepository;
import com.team.shop.repository.ProductRepository;
import com.team.shop.security.CustomerAccess;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;
import java.time.temporal.ChronoUnit;

@Service
public class CartService {
    private final CustomerAccess customerAccess;
    private final CustomerRepository customers;
    private final ProductRepository products;
    private final CartItemRepository cartItems;
    private final CartItemTombstoneRepository tombstones;
    private final OperationReceiptRepository receipts;
    private final ObjectMapper objectMapper;

    public CartService(CustomerAccess customerAccess, CustomerRepository customers, ProductRepository products,
                       CartItemRepository cartItems, CartItemTombstoneRepository tombstones,
                       OperationReceiptRepository receipts, ObjectMapper objectMapper) {
        this.customerAccess = customerAccess;
        this.customers = customers;
        this.products = products;
        this.cartItems = cartItems;
        this.tombstones = tombstones;
        this.receipts = receipts;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public CartItemResponse add(Long productId, String requestKey) {
        Long customerId = customerAccess.requireCustomerId();
        Customer customer = lockCustomer(customerId);
        String requestHash = hash(Long.toString(productId));
        Optional<OperationReceipt> prior = receipts.findByCustomerIdAndOperationTypeAndRequestKey(
                customerId, ReceiptOperationType.CART_ADD, requestKey);
        if (prior.isPresent()) {
            OperationReceipt receipt = prior.get();
            if (!receipt.getRequestHash().equals(requestHash)) {
                throw new StateConflictException("同一请求键不能用于不同商品", 40916);
            }
            return deserialize(receipt.getResultPayload());
        }

        Product product = products.findByIdForUpdate(productId)
                .orElseThrow(() -> new NotFoundException("商品不存在"));
        requireAddable(product);
        var now = BusinessTime.now().truncatedTo(ChronoUnit.MICROS);
        CartItem item = cartItems.findByCustomerAndProductForUpdate(customerId, productId).orElse(null);
        if (item == null) {
            item = cartItems.saveAndFlush(new CartItem(customer, product, BigInteger.ONE, now));
        } else {
            item.changeQuantity(item.getQuantity().add(BigInteger.ONE), now);
        }

        CartItemResponse result = CartItemResponse.from(item);
        receipts.saveAndFlush(new OperationReceipt(customer, ReceiptOperationType.CART_ADD, requestKey,
                requestHash, serialize(result), now));
        return result;
    }

    @Transactional
    public CartItemResponse setQuantity(Long cartItemId, BigInteger quantity) {
        Long customerId = customerAccess.requireCustomerId();
        lockCustomer(customerId);
        CartItem item = lockOwnedCartItem(customerId, cartItemId, true);
        if (quantity.signum() == 0) {
            remove(item, customerId);
            return null;
        }
        item.changeQuantity(quantity, BusinessTime.now().truncatedTo(ChronoUnit.MICROS));
        return CartItemResponse.from(item);
    }

    @Transactional
    public void remove(Long cartItemId) {
        Long customerId = customerAccess.requireCustomerId();
        lockCustomer(customerId);
        CartItem item = lockOwnedCartItem(customerId, cartItemId, false);
        if (item != null) {
            remove(item, customerId);
        }
    }

    @Transactional(readOnly = true)
    public CartResponse getCart() {
        Long customerId = customerAccess.requireCustomerId();
        List<CartItemResponse> items = cartItems.findByCustomerIdOrderByIdAsc(customerId).stream()
                .map(CartItemResponse::from).toList();
        return new CartResponse(items);
    }

    @Transactional
    public void clear() {
        Long customerId = customerAccess.requireCustomerId();
        lockCustomer(customerId);
        List<CartItem> located = cartItems.findByCustomerIdOrderByIdAsc(customerId);
        if (located.isEmpty()) {
            return;
        }

        List<Long> productIds = located.stream().map(item -> item.getProduct().getId()).distinct().sorted().toList();
        for (Long productId : productIds) {
            products.findByIdForUpdate(productId)
                    .orElseThrow(() -> new IllegalStateException("购物车行关联的商品不存在"));
        }
        List<Long> itemIds = located.stream().map(CartItem::getId).sorted().toList();
        List<CartItem> locked = cartItems.findAllByIdForUpdate(itemIds);
        if (locked.size() != itemIds.size()
                || locked.stream().anyMatch(item -> !customerId.equals(item.getCustomer().getId()))) {
            throw new IllegalStateException("持有客户锁时购物车行发生非预期变化");
        }
        var now = BusinessTime.now().truncatedTo(ChronoUnit.MICROS);
        tombstones.saveAll(locked.stream()
                .map(item -> new CartItemTombstone(item.getId(), customerId, item.getProduct().getId(), now))
                .toList());
        cartItems.deleteAll(locked);
        cartItems.flush();
    }

    private CartItem lockOwnedCartItem(Long customerId, Long cartItemId, boolean requirePresent) {
        CartItem located = cartItems.findById(cartItemId).orElse(null);
        if (located == null) {
            assertTombstoneOwner(customerId, cartItemId);
            if (requirePresent) {
                throw new StateConflictException("该商品已不在购物车，请刷新页面后查看。", 40912);
            }
            return null;
        }
        if (!customerId.equals(located.getCustomer().getId())) {
            throw new ForbiddenException("无权操作");
        }

        products.findByIdForUpdate(located.getProduct().getId())
                .orElseThrow(() -> new IllegalStateException("购物车行关联的商品不存在"));
        CartItem locked = cartItems.findByIdForUpdate(cartItemId).orElse(null);
        if (locked == null) {
            assertTombstoneOwner(customerId, cartItemId);
            if (requirePresent) {
                throw new StateConflictException("该商品已不在购物车，请刷新页面后查看。", 40912);
            }
            return null;
        }
        if (!customerId.equals(locked.getCustomer().getId())) {
            throw new ForbiddenException("无权操作");
        }
        return locked;
    }

    private void assertTombstoneOwner(Long customerId, Long cartItemId) {
        tombstones.findByCartItemId(cartItemId).ifPresent(tombstone -> {
            if (!customerId.equals(tombstone.getCustomerId())) {
                throw new ForbiddenException("无权操作");
            }
        });
    }

    private void remove(CartItem item, Long customerId) {
        tombstones.saveAndFlush(new CartItemTombstone(item.getId(), customerId,
                item.getProduct().getId(), BusinessTime.now().truncatedTo(ChronoUnit.MICROS)));
        cartItems.delete(item);
        cartItems.flush();
    }

    private Customer lockCustomer(Long customerId) {
        return customers.findByIdForUpdate(customerId)
                .orElseThrow(() -> new ApiBusinessException(401, 40101, "请重新登录", null));
    }

    private void requireAddable(Product product) {
        if (product.getSellingMode() != SellingMode.FIXED_PRICE) {
            throw new StateConflictException("拍卖商品不能加入购物车", 40908);
        }
        if (product.getStatus() != ProductStatus.ONLINE) {
            throw new StateConflictException("商品已下架", 40901);
        }
    }

    private String serialize(CartItemResponse result) {
        try {
            return objectMapper.writeValueAsString(result);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("无法保存加购幂等结果", e);
        }
    }

    private CartItemResponse deserialize(String payload) {
        try {
            return objectMapper.readValue(payload, CartItemResponse.class);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("加购幂等回执内容无效", e);
        }
    }

    private String hash(String content) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(content.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 不可用", e);
        }
    }

}
