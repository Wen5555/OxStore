package com.team.shop.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.ProductStatus;
import com.team.shop.domain.ReceiptOperationType;
import com.team.shop.dto.request.ChallengeBRequestParser;
import com.team.shop.dto.response.CheckoutConfirmationResponse;
import com.team.shop.dto.response.OrderResponse;
import com.team.shop.entity.*;
import com.team.shop.exception.*;
import com.team.shop.repository.*;
import com.team.shop.security.CustomerAccess;
import jakarta.persistence.EntityManager;
import jakarta.persistence.LockModeType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.temporal.ChronoUnit;
import java.util.*;

/** One transaction owns order creation, stock deduction, remainder cleanup and the success receipt. */
@Service
public class CheckoutService {
    private final CustomerAccess access;
    private final CustomerRepository customers;
    private final ProductRepository products;
    private final CartItemRepository cart;
    private final CartItemTombstoneRepository tombstones;
    private final CheckoutConfirmationRepository confirmations;
    private final ShopOrderRepository orders;
    private final OperationReceiptRepository receipts;
    private final ObjectMapper json;
    private final EntityManager entityManager;

    public CheckoutService(CustomerAccess access, CustomerRepository customers, ProductRepository products,
                           CartItemRepository cart, CartItemTombstoneRepository tombstones,
                           CheckoutConfirmationRepository confirmations, ShopOrderRepository orders,
                           OperationReceiptRepository receipts, ObjectMapper json, EntityManager entityManager) {
        this.access = access; this.customers = customers; this.products = products; this.cart = cart;
        this.tombstones = tombstones; this.confirmations = confirmations; this.orders = orders;
        this.receipts = receipts; this.json = json; this.entityManager = entityManager;
    }

    @Transactional
    public CheckoutConfirmationResponse confirm(JsonNode body) {
        Long customerId = access.requireCustomerId();
        ChallengeBRequestParser.requireObjectWithFields(body, "cartItemIds");
        List<Long> ids = selectedIds(body.get("cartItemIds"));
        Customer customer = lockCustomer(customerId);
        List<CartItem> selected = lockSelection(customerId, ids);
        validateProducts(ids, selected);
        var now = BusinessTime.now().truncatedTo(ChronoUnit.MICROS);
        CheckoutConfirmation confirmation = new CheckoutConfirmation(UUID.randomUUID().toString(), customer,
                total(selected), digest(selected), now);
        selected.forEach(i -> confirmation.addItem(i.getId(), i.getProduct(), price(i), i.getQuantity()));
        confirmations.saveAndFlush(confirmation);
        return CheckoutConfirmationResponse.from(confirmation);
    }

    @Transactional
    public OrderResponse submit(JsonNode body, String key) {
        Long customerId = access.requireCustomerId();
        ChallengeBRequestParser.requireObjectWithFields(body, "confirmationToken");
        String token = ChallengeBRequestParser.requireTextField(body, "confirmationToken");
        if (!token.matches("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"))
            throw failure(40913, "确认信息无效，请重新确认", null);
        token = UUID.fromString(token).toString();
        key = ChallengeBRequestParser.requireIdempotencyKey(key);
        Customer customer = lockCustomer(customerId);
        String requestHash = hash(token);
        var prior = receipts.findByCustomerIdAndOperationTypeAndRequestKey(customerId, ReceiptOperationType.CHECKOUT, key);
        if (prior.isPresent()) {
            if (!requestHash.equals(prior.get().getRequestHash()))
                throw failure(40916, "同一请求键不能用于不同结算请求", null);
            throw duplicate(prior.get());
        }
        // A new key does not turn an already submitted confirmation into a new purchase intent.
        var used = receipts.findFirstByCustomerIdAndOperationTypeAndRequestHash(customerId, ReceiptOperationType.CHECKOUT, requestHash);
        if (used.isPresent()) throw duplicate(used.get());
        CheckoutConfirmation confirmation = confirmations.findByToken(token)
                .orElseThrow(() -> failure(40913, "确认信息不存在，请重新确认", null));
        access.requireOwner(confirmation.getCustomer().getId());
        List<Long> ids = confirmation.getItems().stream().map(CheckoutConfirmationItem::getCartItemId).toList();
        List<CartItem> selected = lockSelection(customerId, ids);
        validateProducts(ids, selected);
        if (!confirmation.getDigest().equals(digest(selected))) {
            List<Map<String,Object>> changed = selected.stream().map(i -> itemError(i.getId(), i,
                    "CONFIRMATION_CHANGED", "商品「" + i.getProduct().getName() + "」的确认信息已变化，请重新确认")).toList();
            throw failure(40913, "确认信息已变化，请重新确认", Map.of("errors", changed));
        }
        var now = BusinessTime.now().truncatedTo(ChronoUnit.MICROS);
        ShopOrder order = new ShopOrder(UUID.randomUUID().toString(), customer, total(selected), now);
        Map<Long,BigInteger> quantities = new LinkedHashMap<>();
        for (var item : confirmation.getItems()) quantities.put(item.getCartItemId(), item.getQuantity());
        for (CartItem item : selected) {
            BigInteger quantity = quantities.get(item.getId());
            order.addItem(item.getProduct(), item.getProduct().getName(), price(item), quantity,
                    price(item).multiply(new BigDecimal(quantity)));
        }
        orders.saveAndFlush(order);
        for (CartItem item : selected) {
            BigInteger quantity = quantities.get(item.getId());
            item.getProduct().deductForOrder(quantity, now);
            BigInteger remainder = item.getQuantity().subtract(quantity);
            if (remainder.signum() > 0) {
                item.changeQuantity(remainder, now);
            } else {
                tombstones.save(new CartItemTombstone(item.getId(), customerId, item.getProduct().getId(), now));
                cart.delete(item);
            }
        }
        // Force all three business writes before recording success. A later failure still rolls all back.
        entityManager.flush();
        receipts.saveAndFlush(new OperationReceipt(customer, ReceiptOperationType.CHECKOUT, key, requestHash,
                encode(Map.of("orderId", order.getId().toString(), "orderNo", order.getOrderNo())), now));
        return OrderResponse.from(order, false);
    }

    private List<Long> selectedIds(JsonNode value) {
        if (value == null || !value.isArray()) throw new ApiBusinessException(400,40002,"cartItemIds必须为数组",null);
        Set<Long> ids = new LinkedHashSet<>();
        for (JsonNode id : value) {
            if (!id.isTextual()) throw new ApiBusinessException(400,40002,"购物车行ID必须为字符串",null);
            ids.add(ChallengeBRequestParser.parseId(id.textValue(), "购物车行"));
        }
        if (ids.isEmpty()) throw new ApiBusinessException(400,40005,"请选择商品",null);
        return List.copyOf(ids);
    }

    private Customer lockCustomer(Long customerId) {
        return customers.findByIdForUpdate(customerId).orElseThrow(() -> new UnauthorizedException("请重新登录"));
    }

    private List<CartItem> lockSelection(Long customerId, List<Long> ids) {
        Map<Long,CartItem> located = new LinkedHashMap<>();
        for (Long id : ids) {
            var item = cart.findById(id).orElse(null);
            if (item != null) {
                access.requireOwner(item.getCustomer().getId());
                located.put(id, item);
            } else {
                tombstones.findByCartItemId(id).ifPresent(t -> access.requireOwner(t.getCustomerId()));
            }
        }
        // Do not expose product errors or make any writes until the entire batch passes ownership.
        located.values().stream().map(i -> i.getProduct().getId()).distinct().sorted().forEach(id -> {
            Product product = products.findByIdForUpdate(id).orElseThrow(() -> new NotFoundException("商品不存在"));
            // The persistence context may contain a proxy/snapshot read before waiting on another buyer.
            entityManager.refresh(product, LockModeType.PESSIMISTIC_WRITE);
        });
        Map<Long,CartItem> locked = new HashMap<>();
        if (!located.isEmpty()) {
            for (CartItem item : cart.findAllByIdForUpdate(located.keySet())) {
                entityManager.refresh(item, LockModeType.PESSIMISTIC_WRITE);
                access.requireOwner(item.getCustomer().getId());
                locked.put(item.getId(), item);
            }
        }
        return ids.stream().map(locked::get).filter(Objects::nonNull).toList();
    }

    private void validateProducts(List<Long> ids, List<CartItem> selected) {
        Map<Long,CartItem> items = new HashMap<>();
        selected.forEach(i -> items.put(i.getId(), i));
        List<Map<String,Object>> errors = new ArrayList<>();
        for (Long id : ids) {
            CartItem item = items.get(id);
            if (item == null) {
                errors.add(itemError(id,null,"CART_ITEM_REMOVED","该商品已不在购物车，请刷新页面后查看。"));
            } else if (item.getProduct().isAuction()) {
                throw new StateConflictException("拍卖商品不能经购物车下单",40908);
            } else if (item.getProduct().getStatus() != ProductStatus.ONLINE) {
                errors.add(itemError(id,item,"OFFLINE","商品「"+item.getProduct().getName()+"」已下架，请从购物车移除后重试。"));
            } else if (item.getProduct().getStock().compareTo(item.getQuantity()) < 0) {
                var error = itemError(id,item,"INSUFFICIENT_STOCK", "商品「"+item.getProduct().getName()+"」库存不足：当前可售 "
                        +item.getProduct().getStock()+" 件，您选购了 "+item.getQuantity()+" 件，请减少数量或移除后重试。");
                error.put("availableStock",item.getProduct().getStock().toString());
                error.put("requestedQuantity",item.getQuantity().toString());
                errors.add(error);
            }
        }
        if (!errors.isEmpty()) throw failure(40910,"所选商品无法下单",Map.of("errors",errors));
    }

    private Map<String,Object> itemError(Long id, CartItem item, String reason, String message) {
        Map<String,Object> error = new LinkedHashMap<>();
        error.put("cartItemId",id.toString());
        if (item != null) { error.put("productId",item.getProduct().getId().toString()); error.put("productName",item.getProduct().getName()); }
        error.put("reason",reason); error.put("message",message);
        return error;
    }
    private BigDecimal price(CartItem item) { return item.getProduct().getPrice().setScale(2); }
    private BigDecimal total(List<CartItem> items) {
        return items.stream().map(i -> price(i).multiply(new BigDecimal(i.getQuantity())))
                .reduce(new BigDecimal("0.00"),BigDecimal::add);
    }
    private String digest(List<CartItem> items) {
        return hash(encode(items.stream().map(i -> List.of(i.getId().toString(),i.getProduct().getId().toString(),
                i.getProduct().getName(),price(i).toPlainString(),i.getQuantity().toString())).toList()));
    }
    private String hash(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch (NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
    private String encode(Object value) {
        try { return json.writeValueAsString(value); }
        catch (JsonProcessingException e) { throw new IllegalStateException("结算结果无法序列化",e); }
    }
    private ApiBusinessException duplicate(OperationReceipt receipt) {
        try { return failure(40909,"订单已提交，请勿重复下单",json.readTree(receipt.getResultPayload())); }
        catch (JsonProcessingException e) { throw new IllegalStateException("结算回执损坏",e); }
    }
    private ApiBusinessException failure(int code,String message,Object data) { return new ApiBusinessException(409,code,message,data); }
}
