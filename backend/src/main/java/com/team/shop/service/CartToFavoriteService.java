package com.team.shop.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.ProductStatus;
import com.team.shop.domain.ReceiptOperationType;
import com.team.shop.domain.SellingMode;
import com.team.shop.dto.request.ChallengeBRequestParser;
import com.team.shop.dto.response.MoveToFavoritesResponse;
import com.team.shop.entity.CartItem;
import com.team.shop.entity.CartItemTombstone;
import com.team.shop.entity.Customer;
import com.team.shop.entity.Favorite;
import com.team.shop.entity.FavoriteMutation;
import com.team.shop.entity.OperationReceipt;
import com.team.shop.entity.Product;
import com.team.shop.exception.ApiBusinessException;
import com.team.shop.exception.ForbiddenException;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.StateConflictException;
import com.team.shop.exception.UnauthorizedException;
import com.team.shop.repository.CartItemRepository;
import com.team.shop.repository.CartItemTombstoneRepository;
import com.team.shop.repository.CustomerRepository;
import com.team.shop.repository.FavoriteMutationRepository;
import com.team.shop.repository.FavoriteRepository;
import com.team.shop.repository.OperationReceiptRepository;
import com.team.shop.repository.ProductRepository;
import com.team.shop.security.CustomerAccess;
import jakarta.persistence.EntityManager;
import jakarta.persistence.LockModeType;
import jakarta.persistence.PersistenceException;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

@Service
public class CartToFavoriteService {
    private final CustomerAccess access;
    private final CustomerRepository customers;
    private final OperationReceiptRepository receipts;
    private final ProductRepository products;
    private final CartItemRepository cart;
    private final CartItemTombstoneRepository tombstones;
    private final FavoriteRepository favorites;
    private final FavoriteMutationRepository mutations;
    private final ObjectMapper json;
    private final EntityManager entityManager;

    public CartToFavoriteService(CustomerAccess access, CustomerRepository customers,
                                 OperationReceiptRepository receipts, ProductRepository products,
                                 CartItemRepository cart, CartItemTombstoneRepository tombstones,
                                 FavoriteRepository favorites, FavoriteMutationRepository mutations,
                                 ObjectMapper json, EntityManager entityManager) {
        this.access = access;
        this.customers = customers;
        this.receipts = receipts;
        this.products = products;
        this.cart = cart;
        this.tombstones = tombstones;
        this.favorites = favorites;
        this.mutations = mutations;
        this.json = json;
        this.entityManager = entityManager;
    }

    @Transactional
    public MoveToFavoritesResponse move(JsonNode body, String idempotencyKey) {
        Long customerId = access.requireCustomerId();
        ChallengeBRequestParser.requireObjectWithFields(body, "cartItemIds");
        List<Long> selectedIds = selectedIds(body.get("cartItemIds"));
        String requestKey = ChallengeBRequestParser.requireIdempotencyKey(idempotencyKey);
        Customer customer = customers.findByIdForUpdate(customerId)
                .orElseThrow(() -> new UnauthorizedException("请重新登录"));
        // Selection is a set; request order only determines the first response/error ordering.
        String requestHash = hash(encode(selectedIds.stream().sorted().map(String::valueOf).toList()));

        Optional<OperationReceipt> prior = receipts.findByCustomerIdAndOperationTypeAndRequestKey(
                customerId, ReceiptOperationType.MOVE_TO_FAVORITES, requestKey);
        if (prior.isPresent()) {
            return retry(prior.get(), requestHash, customerId, selectedIds);
        }

        Map<Long, CartItem> initiallyLocated = new HashMap<>();
        for (CartItem item : cart.findAllByIdIn(selectedIds)) {
            initiallyLocated.put(item.getId(), item);
        }
        Map<Long, CartItemTombstone> initiallyDeleted = tombstoneMap(selectedIds);
        validateBatchOwnership(customerId, selectedIds, initiallyLocated, initiallyDeleted);

        List<CartItem> located = selectedIds.stream().map(initiallyLocated::get)
                .filter(item -> item != null)
                .toList();
        List<Long> productIds = located.stream().map(item -> item.getProduct().getId())
                .distinct().sorted().toList();

        Map<Long, Product> lockedProducts = new LinkedHashMap<>();
        for (Long productId : productIds) {
            Product product = products.findByIdForUpdate(productId).orElse(null);
            if (product != null) {
                entityManager.refresh(product, LockModeType.PESSIMISTIC_WRITE);
            }
            lockedProducts.put(productId, product);
        }

        Map<Long, CartItem> lockedById = new HashMap<>();
        if (!located.isEmpty()) {
            for (CartItem item : cart.findAllByIdForUpdate(located.stream().map(CartItem::getId).toList())) {
                entityManager.refresh(item, LockModeType.PESSIMISTIC_WRITE);
                access.requireOwner(item.getCustomer().getId());
                lockedById.put(item.getId(), item);
            }
        }
        Map<Long, CartItemTombstone> currentTombstones = tombstoneMap(selectedIds);
        List<CartItem> active = new ArrayList<>();
        List<String> skipped = new ArrayList<>();
        for (Long id : selectedIds) {
            CartItem item = lockedById.get(id);
            if (item != null) {
                active.add(item);
            } else {
                CartItemTombstone tombstone = currentTombstones.get(id);
                if (tombstone != null && !customerId.equals(tombstone.getCustomerId())) {
                    throw new ForbiddenException("无权操作");
                }
                skipped.add(id.toString());
            }
        }
        if (active.isEmpty()) {
            throw new ApiBusinessException(400, 40005, "请选择商品", null);
        }

        List<Map<String, Object>> errors = validateProducts(active, lockedProducts);
        if (!errors.isEmpty()) {
            throw new ApiBusinessException(409, 40914, "所选商品无法加入收藏", Map.of("errors", errors));
        }

        List<Long> activeProductIds = active.stream().map(item -> item.getProduct().getId())
                .distinct().sorted().toList();
        Map<Long, Favorite> favoriteByProduct = new HashMap<>();
        for (Favorite favorite : favorites.findAllForUpdate(customerId, activeProductIds)) {
            favoriteByProduct.put(favorite.getProduct().getId(), favorite);
        }
        Map<Long, FavoriteMutation> mutationByProduct = new LinkedHashMap<>();
        for (Long productId : activeProductIds) {
            mutationByProduct.put(productId, mutations.findForUpdate(customerId, productId).orElse(null));
        }

        var now = BusinessTime.now().truncatedTo(ChronoUnit.MICROS);
        MoveToFavoritesResponse result = new MoveToFavoritesResponse(
                active.size(),
                active.stream().map(item -> item.getId().toString()).toList(),
                skipped);
        try {
            Map<String, Long> writeSequences = new LinkedHashMap<>();
            List<Favorite> newFavorites = new ArrayList<>();
            for (CartItem item : active) {
                Long productId = item.getProduct().getId();
                FavoriteMutation mutation = mutationByProduct.get(productId);
                if (mutation == null) {
                    mutation = mutations.save(new FavoriteMutation(customerId, productId));
                    mutationByProduct.put(productId, mutation);
                }
                long sequence = mutation.recordWrite();
                writeSequences.put(productId.toString(), sequence);
                if (!favoriteByProduct.containsKey(productId)) {
                    Favorite favorite = new Favorite(customer, lockedProducts.get(productId), now);
                    favoriteByProduct.put(productId, favorite);
                    newFavorites.add(favorite);
                }
            }
            favorites.saveAll(newFavorites);
            tombstones.saveAll(active.stream()
                    .map(item -> new CartItemTombstone(item.getId(), customerId,
                            item.getProduct().getId(), now))
                    .toList());
            cart.deleteAll(active);
            entityManager.flush();
            receipts.saveAndFlush(new OperationReceipt(customer, ReceiptOperationType.MOVE_TO_FAVORITES,
                    requestKey, requestHash, encode(new StoredMoveResult(result, writeSequences)), now));
        } catch (DataAccessException | PersistenceException e) {
            throw new ApiBusinessException(500, 50001, "操作失败，请重试", null);
        }
        return result;
    }

    private MoveToFavoritesResponse retry(OperationReceipt receipt, String requestHash, Long customerId,
                                          List<Long> selectedIds) {
        StoredMoveResult stored = decode(receipt.getResultPayload());
        if (!receipt.getRequestHash().equals(requestHash) && !sameStoredSelection(stored.result(), selectedIds)) {
            throw new StateConflictException("同一请求键不能用于不同转收藏请求", 40916);
        }
        boolean independentlyCancelled = stored.writeSequences().entrySet().stream()
                .sorted(Map.Entry.comparingByKey(Comparator.comparingLong(Long::parseLong))).anyMatch(entry -> {
            Long productId = ChallengeBRequestParser.parseId(entry.getKey(), "商品");
            FavoriteMutation mutation = mutations.findForUpdate(customerId, productId)
                    .orElseThrow(() -> new IllegalStateException("转收藏幂等记录缺少收藏操作代次"));
            return mutation.getLastCancelSeq() > entry.getValue();
        });
        if (!independentlyCancelled) {
            throw new StateConflictException("请勿重复操作", 40915);
        }
        return stored.result();
    }

    /** B-025 receipts hashed the input order. Their result still contains the full original selection. */
    private boolean sameStoredSelection(MoveToFavoritesResponse result, List<Long> selectedIds) {
        Set<Long> original = new LinkedHashSet<>();
        result.movedCartItemIds().forEach(id -> original.add(Long.valueOf(id)));
        result.skippedDeletedCartItemIds().forEach(id -> original.add(Long.valueOf(id)));
        return original.equals(new LinkedHashSet<>(selectedIds));
    }

    private List<Long> selectedIds(JsonNode value) {
        if (value == null || !value.isArray()) {
            throw new ApiBusinessException(400, 40002, "cartItemIds必须为数组", null);
        }
        Set<Long> ids = new LinkedHashSet<>();
        for (JsonNode id : value) {
            if (!id.isTextual()) {
                throw new ApiBusinessException(400, 40002, "购物车行ID必须为字符串", null);
            }
            ids.add(ChallengeBRequestParser.parseId(id.textValue(), "购物车行"));
        }
        if (ids.isEmpty()) {
            throw new ApiBusinessException(400, 40005, "请选择商品", null);
        }
        return List.copyOf(ids);
    }

    private Map<Long, CartItemTombstone> tombstoneMap(List<Long> ids) {
        Map<Long, CartItemTombstone> result = new HashMap<>();
        for (CartItemTombstone tombstone : tombstones.findByCartItemIdIn(ids)) {
            result.put(tombstone.getCartItemId(), tombstone);
        }
        return result;
    }

    private void validateBatchOwnership(Long customerId, List<Long> ids, Map<Long, CartItem> located,
                                        Map<Long, CartItemTombstone> deleted) {
        for (Long id : ids) {
            CartItem item = located.get(id);
            if (item != null) {
                if (!customerId.equals(item.getCustomer().getId())) {
                    throw new ForbiddenException("无权操作");
                }
            } else {
                CartItemTombstone tombstone = deleted.get(id);
                if (tombstone != null && !customerId.equals(tombstone.getCustomerId())) {
                    throw new ForbiddenException("无权操作");
                }
            }
        }
    }

    private List<Map<String, Object>> validateProducts(List<CartItem> items, Map<Long, Product> lockedProducts) {
        List<Map<String, Object>> errors = new ArrayList<>();
        for (CartItem item : items) {
            Long productId = item.getProduct().getId();
            Product product = lockedProducts.get(productId);
            if (product == null) {
                errors.add(itemError(item, productId, null, "NOT_FOUND", "商品不存在"));
            } else if (product.getSellingMode() != SellingMode.FIXED_PRICE) {
                throw new StateConflictException("拍卖商品不能转为收藏", 40908);
            } else if (product.getStatus() != ProductStatus.ONLINE) {
                errors.add(itemError(item, productId, product.getName(), "OFFLINE",
                        "商品已下架"));
            }
        }
        return errors;
    }

    private Map<String, Object> itemError(CartItem item, Long productId, String productName,
                                          String reason, String message) {
        Map<String, Object> error = new LinkedHashMap<>();
        error.put("cartItemId", item.getId().toString());
        error.put("productId", productId.toString());
        if (productName != null) {
            error.put("productName", productName);
        }
        error.put("reason", reason);
        error.put("message", message);
        return error;
    }

    private String encode(Object value) {
        try {
            return json.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("转收藏回执无法序列化", e);
        }
    }

    private StoredMoveResult decode(String payload) {
        try {
            return json.readValue(payload, StoredMoveResult.class);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("转收藏回执内容无效", e);
        }
    }

    private String hash(String content) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(content.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256不可用", e);
        }
    }

    private String encode(List<String> value) {
        try {
            return json.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("转收藏请求无法规范化", e);
        }
    }

    private record StoredMoveResult(MoveToFavoritesResponse result, Map<String, Long> writeSequences) {
    }
}
