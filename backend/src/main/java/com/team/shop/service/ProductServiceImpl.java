package com.team.shop.service;

import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.IntentStatus;
import com.team.shop.domain.ProductEventType;
import com.team.shop.domain.ProductStatus;
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

    public ProductServiceImpl(ProductRepository products, CategoryRepository categories, IntentRepository intents,
                              OrderHistoryRepository orderHistory, ProductStatusEventRepository events) {
        this.products = products;
        this.categories = categories;
        this.intents = intents;
        this.orderHistory = orderHistory;
        this.events = events;
    }

    @Override
    @Transactional(readOnly = true)
    public PageResponse<ProductSummaryResponse> browse(Long category2Id, String query, int page, int size) {
        Pageable pageable = pageable(page, size);
        if (category2Id != null) {
            requireSecondLevelCategory(category2Id);
        }
        List<Product> matches = products.findAllByStatusOrderByPublishedAtDescIdDesc(ProductStatus.ONLINE)
                .stream()
                .filter(product -> category2Id == null || category2Id.equals(product.getCategory().getId()))
                .filter(product -> matchesQuery(product, query))
                .toList();
        int start = (int) Math.min((long) (pageable.getPageNumber()) * size, matches.size());
        int end = Math.min(start + size, matches.size());
        return new PageResponse<>(matches.subList(start, end).stream().map(ProductSummaryResponse::from).toList(),
                page, size, matches.size(), size == 0 ? 0 : (int) Math.ceil((double) matches.size() / size));
    }

    @Override
    @Transactional(readOnly = true)
    public ProductDetailResponse getBuyerProduct(Long productId) {
        Product product = products.findById(productId)
                .orElseThrow(() -> new NotFoundException("商品不存在"));
        if (product.getStatus() == ProductStatus.OFFLINE) {
            throw new NotFoundException("商品已下架");
        }
        return ProductDetailResponse.from(product);
    }

    @Override
    @Transactional(readOnly = true)
    public PageResponse<ProductDetailResponse> getSellerProducts(int page, int size) {
        Page<Product> result = products.findAllByOrderByPublishedAtDescIdDesc(pageable(page, size));
        return new PageResponse<>(result.getContent().stream().map(ProductDetailResponse::from).toList(),
                result.getNumber() + 1, result.getSize(), result.getTotalElements(), result.getTotalPages());
    }

    @Override
    @Transactional
    public ProductDetailResponse publish(String name, BigDecimal price, Long category2Id, int stock,
                                         String descriptionHtml, List<String> imagePaths) {
        validateProduct(name, price, stock, imagePaths);
        Category category = requireSecondLevelCategory(category2Id);
        String sanitizedDescription = sanitizeDescription(descriptionHtml);
        Product product = Product.create(name.trim(), sanitizedDescription, price, stock, category);
        for (int index = 0; index < imagePaths.size(); index++) {
            product.addImage(imagePaths.get(index), index);
        }
        products.saveAndFlush(product);
        events.save(new ProductStatusEvent(product, null, ProductEventType.PUBLISHED, null, product.getPublishedAt()));
        return ProductDetailResponse.from(product);
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
        if (price == null || price.signum() <= 0 || price.scale() > 2) {
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
