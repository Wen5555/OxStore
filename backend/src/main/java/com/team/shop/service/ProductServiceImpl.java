package com.team.shop.service;

import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.IntentStatus;
import com.team.shop.domain.ProductEventType;
import com.team.shop.domain.ProductStatus;
import com.team.shop.domain.SellingMode;
import com.team.shop.dto.response.PageResponse;
import com.team.shop.dto.response.ProductDetailResponse;
import com.team.shop.dto.response.ProductSummaryResponse;
import com.team.shop.entity.Category;
import com.team.shop.entity.OrderHistory;
import com.team.shop.entity.Product;
import com.team.shop.entity.ProductStatusEvent;
import com.team.shop.exception.BizException;
import com.team.shop.exception.NotFoundException;
import com.team.shop.exception.StateConflictException;
import com.team.shop.exception.UnsupportedRichTextException;
import com.team.shop.exception.PaginationException;
import com.team.shop.repository.CategoryRepository;
import com.team.shop.repository.IntentRepository;
import com.team.shop.repository.OrderHistoryRepository;
import com.team.shop.repository.ProductRepository;
import com.team.shop.repository.ProductStatusEventRepository;
import com.team.shop.repository.AuctionSessionRepository;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.nodes.Attribute;
import org.jsoup.safety.Safelist;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;
import java.time.LocalDateTime;
import java.util.Locale;

@Service
public class ProductServiceImpl implements ProductService {
    private static final int MAX_PAGE_SIZE = 100;
    private static final java.util.Set<String> FORBIDDEN_RICH_TEXT_TAGS = java.util.Set.of(
            "script", "iframe", "object", "embed", "form", "input", "button", "video", "audio",
            "svg", "math", "table", "style", "link");
    private static final Safelist DESCRIPTION_TAGS = new Safelist()
            .addTags("p", "br", "strong", "b", "em", "i", "ul", "ol", "li", "img")
            .addAttributes("img", "src", "alt", "title")
            .addProtocols("img", "src", "http", "https");

    private final ProductRepository products;
    private final CategoryRepository categories;
    private final IntentRepository intents;
    private final OrderHistoryRepository orderHistory;
    private final ProductStatusEventRepository events;
    private final ImageStorageService imageStorage;
    private final AuctionSessionRepository auctions;

    public ProductServiceImpl(ProductRepository products, CategoryRepository categories, IntentRepository intents,
                              OrderHistoryRepository orderHistory, ProductStatusEventRepository events,
                              ImageStorageService imageStorage, AuctionSessionRepository auctions) {
        this.products = products;
        this.categories = categories;
        this.intents = intents;
        this.orderHistory = orderHistory;
        this.events = events;
        this.imageStorage = imageStorage;
        this.auctions = auctions;
    }

    @Override
    @Transactional(readOnly = true)
    public PageResponse<ProductSummaryResponse> browse(Long category2Id, String query, int page, int size) {
        return browse(category2Id, query, null, page, size);
    }

    @Override
    @Transactional(readOnly = true)
    public PageResponse<ProductSummaryResponse> browse(Long category2Id, String query, SellingMode sellingMode,
                                                      int page, int size) {
        Pageable pageable = pageable(page, size);
        if (category2Id != null) {
            requireSecondLevelCategory(category2Id);
        }
        List<Product> matches = products.findAllByStatusOrderByPublishedAtDescIdDesc(ProductStatus.ONLINE)
                .stream()
                .filter(product -> category2Id == null || category2Id.equals(product.getCategory().getId()))
                .filter(product -> sellingMode == null || sellingMode == product.getSellingMode())
                .filter(product -> matchesQuery(product, query))
                .toList();
        int start = (int) Math.min((long) (pageable.getPageNumber()) * size, matches.size());
        int end = Math.min(start + size, matches.size());
        Map<Long, com.team.shop.entity.AuctionSession> auctionMap = auctions.findAllByProductIdIn(matches.stream()
                        .map(Product::getId).toList()).stream()
                .collect(Collectors.toMap(a -> a.getProduct().getId(), Function.identity()));
        return new PageResponse<>(matches.subList(start, end).stream()
                .map(product -> ProductSummaryResponse.from(product, auctionMap.get(product.getId()))).toList(),
                page, size, matches.size(), size == 0 ? 0 : (int) Math.ceil((double) matches.size() / size));
    }

    @Override
    @Transactional(readOnly = true)
    public ProductDetailResponse getBuyerProduct(Long productId) {
        Product product = products.findById(productId)
                .orElseThrow(() -> new NotFoundException("商品不存在"));
        com.team.shop.entity.AuctionSession auction = auctions.findByProductId(productId).orElse(null);
        boolean endedAuction = auction != null
                && auction.getStatus() == com.team.shop.domain.AuctionStatus.ENDED_UNSOLD;
        if (product.getStatus() == ProductStatus.OFFLINE && !endedAuction) {
            throw new NotFoundException("商品已下架");
        }
        return ProductDetailResponse.from(product, auction);
    }

    @Override
    @Transactional(readOnly = true)
    public PageResponse<ProductDetailResponse> getSellerProducts(int page, int size) {
        Page<Product> result = products.findAllByOrderByPublishedAtDescIdDesc(pageable(page, size));
        Map<Long, com.team.shop.entity.AuctionSession> auctionMap = auctions.findAllByProductIdIn(result.getContent().stream()
                        .map(Product::getId).toList()).stream()
                .collect(Collectors.toMap(a -> a.getProduct().getId(), Function.identity()));
        return new PageResponse<>(result.getContent().stream()
                .map(product -> ProductDetailResponse.from(product, auctionMap.get(product.getId()))).toList(),
                result.getNumber() + 1, result.getSize(), result.getTotalElements(), result.getTotalPages());
    }

    @Override
    @Transactional
    public ProductDetailResponse publish(String name, BigDecimal price, Long category2Id, int stock,
                                         String descriptionHtml, List<String> imagePaths) {
        return publish(name, price, category2Id, stock, descriptionHtml, imagePaths,
                SellingMode.FIXED_PRICE, null, null, null);
    }

    @Override
    @Transactional
    public ProductDetailResponse publish(String name, BigDecimal price, Long category2Id, int stock,
                                         String descriptionHtml, List<String> imagePaths, SellingMode sellingMode,
                                         BigDecimal startPrice, BigDecimal minIncrement, LocalDateTime endsAt) {
        SellingMode mode = sellingMode == null ? SellingMode.FIXED_PRICE : sellingMode;
        validateProduct(name, mode == SellingMode.AUCTION ? startPrice : price, stock, imagePaths);
        Category category = requireSecondLevelCategory(category2Id);
        String sanitizedDescription = sanitizeDescription(descriptionHtml);
        Product product;
        if (mode == SellingMode.AUCTION) {
            if (startPrice == null || minIncrement == null || endsAt == null) {
                throw new BizException("拍卖必须填写起拍价、最小加价和截止时间");
            }
            if (stock != 1) {
                throw new BizException("拍卖商品库存必须为 1");
            }
            LocalDateTime now = BusinessTime.now();
            if (endsAt.isBefore(now.plusSeconds(60)) || endsAt.isAfter(now.plusDays(30))) {
                throw new BizException("拍卖截止时间须在当前时间 60 秒至 30 天内");
            }
            product = Product.createAuction(name.trim(), sanitizedDescription, startPrice, category);
        } else {
            if (startPrice != null || minIncrement != null || endsAt != null) {
                throw new BizException("普通在售不能填写拍卖参数");
            }
            product = Product.create(name.trim(), sanitizedDescription, price, stock, category);
        }
        for (int index = 0; index < imagePaths.size(); index++) {
            String imagePath = imagePaths.get(index);
            var metadata = imageStorage.metadata(imagePath);
            product.addImage(imagePath, index, metadata.contentType(), metadata.sizeBytes());
        }
        products.saveAndFlush(product);
        if (mode == SellingMode.AUCTION) {
            auctions.saveAndFlush(com.team.shop.entity.AuctionSession.open(product, startPrice, minIncrement,
                    product.getPublishedAt(), endsAt));
        }
        events.save(new ProductStatusEvent(product, null, ProductEventType.PUBLISHED, null, product.getPublishedAt()));
        return ProductDetailResponse.from(product, mode == SellingMode.AUCTION
                ? auctions.findByProductId(product.getId()).orElse(null) : null);
    }

    @Override
    @Transactional
    public ProductDetailResponse update(Long productId, Integer stock, Long category2Id) {
        if (stock == null && category2Id == null) {
            throw new BizException("必须提供库存或二级类目");
        }
        if (stock != null && stock < 0) {
            throw new BizException("库存不能为负数");
        }
        Product product = lockProduct(productId);
        if (product.isAuction() && stock != null) {
            throw new StateConflictException("拍卖商品不能修改库存", 40908);
        }
        if (product.getStatus() == ProductStatus.FROZEN) {
            throw new StateConflictException("交易中的商品不可编辑");
        }
        ProductStatus before = product.getStatus();
        int newStock = stock == null ? product.getStock() : stock;
        Category category = category2Id == null ? product.getCategory() : requireSecondLevelCategory(category2Id);
        product.updateInventoryAndCategory(newStock, category, BusinessTime.now());
        if (before == ProductStatus.ONLINE && newStock == 0) {
            failQueuedIntents(product, BusinessTime.now());
            events.save(new ProductStatusEvent(product, null, ProductEventType.INVENTORY_OFFLINE, before,
                    product.getStatusUpdatedAt()));
        }
        return ProductDetailResponse.from(product);
    }

    @Override
    @Transactional
    public ProductDetailResponse takeOffline(Long productId) {
        Product product = lockProduct(productId);
        if (product.isAuction()) {
            throw new StateConflictException("拍卖商品不能手动下架", 40901);
        }
        if (intents.findByProductIdAndStatus(productId, IntentStatus.IN_TRANSACTION).isPresent()) {
            throw new StateConflictException("交易中的商品不可下架");
        }
        ProductStatus before = product.getStatus();
        product.takeOffline(BusinessTime.now());
        failQueuedIntents(product, product.getStatusUpdatedAt());
        events.save(new ProductStatusEvent(product, null, ProductEventType.MANUAL_OFFLINE, before,
                product.getStatusUpdatedAt()));
        return ProductDetailResponse.from(product);
    }

    @Override
    @Transactional
    public ProductDetailResponse putOnline(Long productId) {
        Product product = lockProduct(productId);
        if (product.isAuction()) {
            throw new StateConflictException("拍卖商品不能手动上架", 40908);
        }
        ProductStatus before = product.getStatus();
        product.putOnline(BusinessTime.now());
        events.save(new ProductStatusEvent(product, null, ProductEventType.MANUAL_ONLINE, before,
                product.getStatusUpdatedAt()));
        return ProductDetailResponse.from(product);
    }

    private boolean matchesQuery(Product product, String query) {
        if (query == null || query.isBlank()) {
            return true;
        }
        String normalized = query.trim().toLowerCase(Locale.ROOT);
        String descriptionText = Jsoup.parse(product.getDescription()).text().toLowerCase(Locale.ROOT);
        return product.getName().toLowerCase(Locale.ROOT).contains(normalized)
                || descriptionText.contains(normalized);
    }

    private String sanitizeDescription(String descriptionHtml) {
        if (descriptionHtml == null || descriptionHtml.isBlank()) {
            return "";
        }
        Document parsed = Jsoup.parseBodyFragment(descriptionHtml);
        for (Element element : parsed.getAllElements()) {
            if (FORBIDDEN_RICH_TEXT_TAGS.contains(element.normalName())) {
                throw new UnsupportedRichTextException("描述包含不支持的脚本或交互内容");
            }
            for (Attribute attribute : element.attributes()) {
                String name = attribute.getKey().toLowerCase(Locale.ROOT);
                String value = attribute.getValue().trim().toLowerCase(Locale.ROOT);
                if (name.startsWith("on") || value.startsWith("javascript:") || value.startsWith("data:text/html")) {
                    throw new UnsupportedRichTextException("描述包含不安全的 HTML 属性");
                }
            }
        }
        return Jsoup.clean(descriptionHtml, DESCRIPTION_TAGS);
    }

    private void validateProduct(String name, BigDecimal price, int stock, List<String> imagePaths) {
        if (name == null || name.isBlank() || name.length() > 200) {
            throw new BizException("商品名称必填且不能超过 200 个字符");
        }
        if (price == null || price.signum() <= 0 || price.scale() > 2
                || price.compareTo(new BigDecimal("99999999.99")) > 0) {
            throw new BizException("价格必须为正数且最多两位小数");
        }
        if (stock < 0) {
            throw new BizException("库存不能为负数");
        }
        if (imagePaths == null || imagePaths.size() > 9) {
            throw new BizException("商品图片最多上传 9 张");
        }
    }

    private Category requireSecondLevelCategory(Long category2Id) {
        if (category2Id == null) {
            throw new BizException("必须选择二级类目");
        }
        Category category = categories.findById(category2Id)
                .orElseThrow(() -> new NotFoundException("类目不存在", 40402));
        if (category.isRoot()) {
            throw new BizException("商品必须选择二级类目");
        }
        return category;
    }

    private Product lockProduct(Long productId) {
        return products.findByIdForUpdate(productId).orElseThrow(() -> new NotFoundException("商品不存在"));
    }

    private void failQueuedIntents(Product product, java.time.LocalDateTime now) {
        for (var intent : intents.findQueueForUpdate(product.getId(), IntentStatus.QUEUING)) {
            intent.markQueuedIntentFailed(now);
            if (intent.getCustomer() != null) {
                orderHistory.save(new OrderHistory(intent.getId(), intent.getCustomer(),
                        intent.getProductNameSnapshot(), intent.getSubmittedAt(), IntentStatus.FAILED, now));
            }
        }
    }

    private Pageable pageable(int page, int size) {
        if (page < 1 || size < 1 || size > MAX_PAGE_SIZE) {
            throw new PaginationException("分页参数必须满足 page>=1 且 1<=size<=100");
        }
        return PageRequest.of(page - 1, size);
    }
}
