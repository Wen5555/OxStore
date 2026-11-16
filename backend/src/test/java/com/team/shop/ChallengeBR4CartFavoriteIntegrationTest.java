package com.team.shop;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.OrderStatus;
import com.team.shop.entity.Customer;
import com.team.shop.entity.Product;
import com.team.shop.entity.PurchaseIntent;
import com.team.shop.entity.ShopOrder;
import com.team.shop.repository.CategoryRepository;
import com.team.shop.repository.CustomerRepository;
import com.team.shop.repository.IntentRepository;
import com.team.shop.repository.ProductRepository;
import com.team.shop.repository.ShopOrderRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "spring.datasource.url=jdbc:h2:mem:challengeb_r4;MODE=MySQL;DB_CLOSE_DELAY=-1",
        "spring.datasource.username=sa",
        "spring.datasource.password=",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.jpa.hibernate.ddl-auto=create-drop",
        "shop.jwt.secret=challenge-b-r4-secret-0123456789abcdef",
        "shop.upload-dir=target/challenge-b-r4-uploads",
        "shop.admin.initial-password=Test-Pass-9931!"
})
class ChallengeBR4CartFavoriteIntegrationTest {
    @Autowired
    private TestRestTemplate http;

    @Autowired
    private CategoryRepository categories;

    @Autowired
    private CustomerRepository customers;

    @Autowired
    private ProductRepository products;

    @Autowired
    private IntentRepository intents;

    @Autowired
    private ShopOrderRepository orders;

    @Autowired
    private JdbcTemplate jdbc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void favoritesAreIdempotentAndKeepOfflineProductsAsReadOnlyItems() {
        String suffix = Long.toString(System.nanoTime());
        String buyer = "r4-favorite-" + suffix;
        String buyerToken = registerAndLogin(buyer, phone());
        String sellerToken = sellerToken();
        Customer customer = customers.findByUsername(buyer).orElseThrow();
        Product product = fixedProduct("收藏商品-" + suffix, 2);

        JsonNode first = exchange(HttpMethod.PUT, "/api/me/favorites/" + product.getId(), null, buyerToken, null);
        assertEquals(0, first.path("code").asInt());
        assertEquals("已收藏", first.path("message").asText());
        String favoriteId = first.path("data").path("favoriteId").asText();
        String createdAt = first.path("data").path("createdAt").asText();

        JsonNode duplicate = exchange(HttpMethod.PUT, "/api/me/favorites/" + product.getId(), null, buyerToken, null);
        assertEquals(favoriteId, duplicate.path("data").path("favoriteId").asText());
        assertEquals(createdAt, duplicate.path("data").path("createdAt").asText());
        assertTrue(exchange(HttpMethod.GET, "/api/me/favorites/" + product.getId(), null, buyerToken, null)
                .path("data").path("favorited").asBoolean());

        assertEquals(200, status(HttpMethod.POST, "/api/admin/products/" + product.getId() + "/offline",
                null, sellerToken, null));
        JsonNode favorites = exchange(HttpMethod.GET, "/api/me/favorites?page=1&size=10", null, buyerToken, null)
                .path("data");
        assertEquals(1, favorites.path("total").asInt());
        assertFalse(favorites.path("items").get(0).path("valid").asBoolean());
        assertFalse(favorites.path("items").get(0).path("canOpenDetail").asBoolean());
        assertEquals("已下架", favorites.path("items").get(0).path("invalidLabel").asText());

        JsonNode removed = exchange(HttpMethod.DELETE, "/api/me/favorites/" + product.getId(),
                null, buyerToken, null);
        assertEquals("已取消收藏", removed.path("message").asText());
        assertEquals("未收藏", exchange(HttpMethod.DELETE, "/api/me/favorites/" + product.getId(),
                null, buyerToken, null).path("message").asText());
        assertFalse(exchange(HttpMethod.GET, "/api/me/favorites/" + product.getId(), null, buyerToken, null)
                .path("data").path("favorited").asBoolean());
        assertTrue(customer.getId() > 0);
    }

    @Test
    void cartSupportsExactQuantitiesIdempotencyAndTombstones() {
        String suffix = Long.toString(System.nanoTime());
        String buyer = "r4-cart-" + suffix;
        String buyerToken = registerAndLogin(buyer, phone());
        Product firstProduct = fixedProduct("购物车商品A-" + suffix, 2);
        Product secondProduct = fixedProduct("购物车商品B-" + suffix, 5);

        String firstKey = UUID.randomUUID().toString();
        JsonNode first = addCart(buyerToken, firstProduct.getId(), firstKey);
        String firstItemId = first.path("data").path("cartItemId").asText();
        assertEquals("1", first.path("data").path("quantity").asText());
        JsonNode retry = addCart(buyerToken, firstProduct.getId(), firstKey);
        assertEquals(firstItemId, retry.path("data").path("cartItemId").asText());
        assertEquals("1", retry.path("data").path("quantity").asText());

        JsonNode differentBody = addCart(buyerToken, secondProduct.getId(), firstKey);
        assertEquals(409, status(differentBody));
        assertEquals(40916, differentBody.path("code").asInt());

        JsonNode updated = exchange(HttpMethod.PATCH, "/api/me/cart/items/" + firstItemId,
                Map.of("quantity", "9007199254740993"), buyerToken, null);
        assertEquals("9007199254740993", updated.path("data").path("quantity").asText());
        assertFalse(updated.path("data").path("defaultCheckoutSelected").asBoolean());

        JsonNode zeroed = exchange(HttpMethod.PATCH, "/api/me/cart/items/" + firstItemId,
                Map.of("quantity", "0"), buyerToken, null);
        assertTrue(zeroed.path("data").isNull());
        assertEquals(40912, exchange(HttpMethod.PATCH, "/api/me/cart/items/" + firstItemId,
                Map.of("quantity", "1"), buyerToken, null).path("code").asInt());
        assertEquals("已移除", exchange(HttpMethod.DELETE, "/api/me/cart/items/" + firstItemId,
                null, buyerToken, null).path("message").asText());

        JsonNode readded = addCart(buyerToken, firstProduct.getId(), UUID.randomUUID().toString());
        assertNotEquals(firstItemId, readded.path("data").path("cartItemId").asText());
        addCart(buyerToken, secondProduct.getId(), UUID.randomUUID().toString());
        assertEquals(2, exchange(HttpMethod.GET, "/api/me/cart", null, buyerToken, null)
                .path("data").path("items").size());
        assertEquals(200, status(HttpMethod.DELETE, "/api/me/cart", null, buyerToken, null));
        assertEquals(0, exchange(HttpMethod.GET, "/api/me/cart", null, buyerToken, null)
                .path("data").path("items").size());
    }

    @Test
    void cartRejectsOfflineAuctionAndNonCustomerRequests() {
        String suffix = Long.toString(System.nanoTime());
        String buyerToken = registerAndLogin("r4-cart-guard-" + suffix, phone());
        String sellerToken = sellerToken();
        Product offline = fixedProduct("下架商品-" + suffix, 1);
        offline.takeOffline(BusinessTime.now());
        products.saveAndFlush(offline);
        Product auction = auctionProduct("拍卖商品-" + suffix);

        JsonNode offlineResponse = addCart(buyerToken, offline.getId(), UUID.randomUUID().toString());
        assertEquals(40901, offlineResponse.path("code").asInt());
        JsonNode auctionResponse = addCart(buyerToken, auction.getId(), UUID.randomUUID().toString());
        assertEquals(40908, auctionResponse.path("code").asInt());
        assertEquals(401, status(HttpMethod.GET, "/api/me/cart", null, null, null));
        assertEquals(403, status(HttpMethod.GET, "/api/me/cart", null, sellerToken, null));
        assertEquals(403, status(HttpMethod.GET, "/api/me/favorites?page=1", null, sellerToken, null));
    }

    @Test
    void fixedPriceIntentActionsAreClosedAndLegacyArchiveIsReadOnly() {
        String suffix = Long.toString(System.nanoTime());
        String buyer = "r4-legacy-" + suffix;
        String buyerToken = registerAndLogin(buyer, phone());
        String sellerToken = sellerToken();
        Customer customer = customers.findByUsername(buyer).orElseThrow();
        Product product = fixedProduct("归档商品-" + suffix, 1);

        JsonNode submit = exchange(HttpMethod.POST, "/api/products/" + product.getId() + "/intents",
                null, buyerToken, null);
        assertEquals(40917, submit.path("code").asInt());
        JsonNode queue = exchange(HttpMethod.GET, "/api/admin/intents?productId=" + product.getId(),
                null, sellerToken, null);
        assertEquals(40917, queue.path("code").asInt());

        PurchaseIntent intent = intents.saveAndFlush(PurchaseIntent.submit(product, customer, 1));
        jdbc.update("update purchase_intent set legacy_closed_at = ?, legacy_close_reason = ? where id = ?",
                BusinessTime.now(), "FIXED_PRICE_CHALLENGE_B", intent.getId());

        JsonNode customerArchive = exchange(HttpMethod.GET, "/api/me/legacy-intents?page=1&size=10",
                null, buyerToken, null).path("data");
        assertEquals(1, customerArchive.path("total").asInt());
        JsonNode record = customerArchive.path("items").get(0);
        assertEquals(Long.toString(intent.getId()), record.path("legacyIntentId").asText());
        assertEquals("QUEUING", record.path("originalStatus").asText());
        assertEquals("CLOSED", record.path("displayStatus").asText());
        assertTrue(record.path("readOnly").asBoolean());
        assertFalse(record.path("closedAt").isNull());

        JsonNode sellerArchive = exchange(HttpMethod.GET,
                "/api/admin/legacy-intents?page=1&size=10&productId=" + product.getId()
                        + "&customerId=" + customer.getId(), null, sellerToken, null).path("data");
        assertEquals(1, sellerArchive.path("total").asInt());
    }

    @Test
    void customerCancellationRestoresSnapshotInventoryOnlyOnce() {
        String suffix = Long.toString(System.nanoTime());
        String buyer = "r4-order-cancel-" + suffix;
        String buyerToken = registerAndLogin(buyer, phone());
        Customer customer = customers.findByUsername(buyer).orElseThrow();
        Product product = fixedProduct("取消回补商品-" + suffix, 1);
        product.deductForOrder(BigInteger.ONE, BusinessTime.now());
        products.saveAndFlush(product);
        ShopOrder order = order(customer, product, BigInteger.ONE, OrderStatus.PLACED);
        String orderPath = "/api/me/orders/" + order.getId() + "/cancel";

        assertEquals(0, product.getStock().intValue());
        JsonNode partial = exchange(HttpMethod.POST, orderPath,
                Map.of("expectedStatus", "PLACED", "itemIds", java.util.List.of("1")), buyerToken, null);
        assertEquals(40004, partial.path("code").asInt());
        assertEquals(0, products.findById(product.getId()).orElseThrow().getStock().intValue());

        ResponseEntity<JsonNode> cancelled = request(HttpMethod.POST, orderPath,
                Map.of("expectedStatus", "PLACED", "reason", "客户取消"), buyerToken, null);
        assertEquals(200, cancelled.getStatusCode().value());
        assertEquals("CANCELLED", cancelled.getBody().path("data").path("status").asText());
        assertEquals("CUSTOMER", cancelled.getBody().path("data").path("cancelledBy").asText());
        assertEquals(0, cancelled.getBody().path("data").path("allowedActions").size());
        assertEquals(1, products.findById(product.getId()).orElseThrow().getStock().intValue());
        assertEquals("ONLINE", products.findById(product.getId()).orElseThrow().getStatus().name());

        ResponseEntity<JsonNode> duplicate = request(HttpMethod.POST, orderPath,
                Map.of("expectedStatus", "CANCELLED"), buyerToken, null);
        assertEquals(409, duplicate.getStatusCode().value());
        assertEquals(40911, duplicate.getBody().path("code").asInt());
        assertEquals(1, products.findById(product.getId()).orElseThrow().getStock().intValue());
    }

    @Test
    void cancellationChecksOwnershipAndExpectedStatusBeforeRestocking() {
        String suffix = Long.toString(System.nanoTime());
        String buyer = "r4-order-owner-" + suffix;
        String otherBuyer = "r4-order-other-" + suffix;
        String buyerToken = registerAndLogin(buyer, phone());
        String otherBuyerToken = registerAndLogin(otherBuyer, phone());
        String sellerToken = sellerToken();
        Customer customer = customers.findByUsername(buyer).orElseThrow();
        Product product = fixedProduct("商家取消商品-" + suffix, 3);
        product.deductForOrder(BigInteger.ONE, BusinessTime.now());
        products.saveAndFlush(product);
        ShopOrder order = order(customer, product, BigInteger.ONE, OrderStatus.SHIPPED);
        String orderPath = "/api/me/orders/" + order.getId() + "/cancel";

        JsonNode wrongOwner = exchange(HttpMethod.POST, orderPath,
                Map.of("expectedStatus", "SHIPPED", "items", java.util.List.of()), otherBuyerToken, null);
        assertEquals(40302, wrongOwner.path("code").asInt());
        assertEquals(40911, exchange(HttpMethod.POST, orderPath,
                Map.of("expectedStatus", "SHIPPED"), buyerToken, null).path("code").asInt());
        assertEquals(2, products.findById(product.getId()).orElseThrow().getStock().intValue());

        String sellerPath = "/api/admin/orders/" + order.getId() + "/cancel";
        assertEquals(40904, exchange(HttpMethod.POST, sellerPath,
                Map.of("expectedStatus", "PREPARED"), sellerToken, null).path("code").asInt());
        assertEquals(2, products.findById(product.getId()).orElseThrow().getStock().intValue());
        JsonNode cancelled = exchange(HttpMethod.POST, sellerPath,
                Map.of("expectedStatus", "SHIPPED"), sellerToken, null);
        assertEquals("CANCELLED", cancelled.path("data").path("status").asText());
        assertEquals("SELLER", cancelled.path("data").path("cancelledBy").asText());
        assertEquals(3, products.findById(product.getId()).orElseThrow().getStock().intValue());
    }

    @Test
    void concurrentDuplicateCancellationRestoresInventoryOnce() throws Exception {
        String suffix = Long.toString(System.nanoTime());
        String buyer = "r4-order-race-" + suffix;
        String buyerToken = registerAndLogin(buyer, phone());
        Customer customer = customers.findByUsername(buyer).orElseThrow();
        Product product = fixedProduct("并发取消商品-" + suffix, 1);
        product.deductForOrder(BigInteger.ONE, BusinessTime.now());
        products.saveAndFlush(product);
        ShopOrder order = order(customer, product, BigInteger.ONE, OrderStatus.PLACED);
        String path = "/api/me/orders/" + order.getId() + "/cancel";

        ExecutorService workers = Executors.newFixedThreadPool(2);
        CountDownLatch ready = new CountDownLatch(2);
        CountDownLatch start = new CountDownLatch(1);
        try {
            Future<ResponseEntity<JsonNode>> first = workers.submit(() -> {
                ready.countDown();
                if (!start.await(5, TimeUnit.SECONDS)) throw new IllegalStateException("cancel start timed out");
                return request(HttpMethod.POST, path, Map.of("expectedStatus", "PLACED"), buyerToken, null);
            });
            Future<ResponseEntity<JsonNode>> second = workers.submit(() -> {
                ready.countDown();
                if (!start.await(5, TimeUnit.SECONDS)) throw new IllegalStateException("cancel start timed out");
                return request(HttpMethod.POST, path, Map.of("expectedStatus", "PLACED"), buyerToken, null);
            });
            assertTrue(ready.await(5, TimeUnit.SECONDS));
            start.countDown();
            ResponseEntity<JsonNode> firstResponse = first.get(10, TimeUnit.SECONDS);
            ResponseEntity<JsonNode> secondResponse = second.get(10, TimeUnit.SECONDS);
            assertTrue((firstResponse.getStatusCode().value() == 200
                    && secondResponse.getStatusCode().value() == 409
                    || firstResponse.getStatusCode().value() == 409
                    && secondResponse.getStatusCode().value() == 200));
            ResponseEntity<JsonNode> rejected = firstResponse.getStatusCode().value() == 409
                    ? firstResponse : secondResponse;
            assertEquals(409, rejected.getStatusCode().value());
            assertEquals(40911, rejected.getBody().path("code").asInt());
        } finally {
            start.countDown();
            workers.shutdownNow();
        }
        assertEquals(1, products.findById(product.getId()).orElseThrow().getStock().intValue());
        assertEquals(OrderStatus.CANCELLED, orders.findById(order.getId()).orElseThrow().getStatus());
    }

    private ShopOrder order(Customer customer, Product product, BigInteger quantity, OrderStatus status) {
        BigDecimal lineAmount = product.getPrice().multiply(new BigDecimal(quantity));
        ShopOrder order = new ShopOrder(UUID.randomUUID().toString(), customer, lineAmount, BusinessTime.now());
        order.addItem(product, product.getName(), product.getPrice(), quantity, lineAmount);
        order.applyStatus(status);
        return orders.saveAndFlush(order);
    }

    private JsonNode addCart(String token, Long productId, String requestKey) {
        return exchange(HttpMethod.POST, "/api/me/cart/items", Map.of("productId", Long.toString(productId)),
                token, requestKey);
    }

    private String registerAndLogin(String username, String phone) {
        ResponseEntity<JsonNode> registered = http.postForEntity("/api/auth/register",
                Map.of("username", username, "password", "customer-pass-8", "phone", phone), JsonNode.class);
        assertEquals(201, registered.getStatusCode().value());
        return login("/api/auth/login", Map.of("username", username, "password", "customer-pass-8"));
    }

    private String sellerToken() {
        return login("/api/admin/auth/login",
                Map.of("username", "admin", "password", "Test-Pass-9931!"));
    }

    private String phone() {
        return "13" + String.format("%09d", Math.floorMod(System.nanoTime(), 1_000_000_000L));
    }

    private String login(String path, Map<String, String> credentials) {
        ResponseEntity<JsonNode> response = http.postForEntity(path, credentials, JsonNode.class);
        assertEquals(200, response.getStatusCode().value());
        return response.getBody().path("data").path("token").asText();
    }

    private Product fixedProduct(String name, int stock) {
        var root = categories.findByNameAndParentIsNull("数码电器").orElseThrow();
        var category = categories.findByNameAndParentId("手机数码", root.getId()).orElseThrow();
        return products.saveAndFlush(Product.create(name, "", new BigDecimal("12.50"),
                BigInteger.valueOf(stock), category));
    }

    private Product auctionProduct(String name) {
        var root = categories.findByNameAndParentIsNull("数码电器").orElseThrow();
        var category = categories.findByNameAndParentId("手机数码", root.getId()).orElseThrow();
        return products.saveAndFlush(Product.createAuction(name, "", new BigDecimal("12.50"), category));
    }

    private JsonNode exchange(HttpMethod method, String path, Object body, String token, String requestKey) {
        return request(method, path, body, token, requestKey).getBody();
    }

    private int status(HttpMethod method, String path, Object body, String token, String requestKey) {
        return request(method, path, body, token, requestKey).getStatusCode().value();
    }

    private ResponseEntity<JsonNode> request(HttpMethod method, String path, Object body,
                                             String token, String requestKey) {
        HttpHeaders headers = new HttpHeaders();
        if (token != null) {
            headers.setBearerAuth(token);
        }
        if (requestKey != null) {
            headers.set("Idempotency-Key", requestKey);
        }
        if (method != HttpMethod.PATCH) {
            return http.exchange(path, method, new HttpEntity<>(body, headers), JsonNode.class);
        }
        try {
            HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(http.getRootUri() + path))
                    .header("Accept", "application/json")
                    .header("Content-Type", "application/json");
            if (token != null) {
                request.header(HttpHeaders.AUTHORIZATION, "Bearer " + token);
            }
            if (requestKey != null) {
                request.header("Idempotency-Key", requestKey);
            }
            String json = body == null ? "" : objectMapper.writeValueAsString(body);
            HttpRequest.BodyPublisher publisher = body == null
                    ? HttpRequest.BodyPublishers.noBody()
                    : HttpRequest.BodyPublishers.ofString(json);
            HttpResponse<String> response = HttpClient.newHttpClient().send(
                    request.method("PATCH", publisher).build(), HttpResponse.BodyHandlers.ofString());
            JsonNode responseBody = response.body().isEmpty() ? null : objectMapper.readTree(response.body());
            return new ResponseEntity<>(responseBody, HttpStatusCode.valueOf(response.statusCode()));
        } catch (IOException e) {
            throw new IllegalStateException("Could not send PATCH request", e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("PATCH request interrupted", e);
        }
    }

    private int status(JsonNode body) {
        return body.path("code").asInt() == 0 ? 200 : body.path("code").asInt() == 40916 ? 409 : 400;
    }
}
