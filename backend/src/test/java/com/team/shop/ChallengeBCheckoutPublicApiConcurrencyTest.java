package com.team.shop;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.team.shop.domain.BusinessTime;
import com.team.shop.entity.Customer;
import com.team.shop.entity.Product;
import com.team.shop.entity.ShopOrder;
import com.team.shop.repository.CategoryRepository;
import com.team.shop.repository.CustomerRepository;
import com.team.shop.repository.ProductRepository;
import com.team.shop.repository.ShopOrderRepository;
import com.team.shop.security.JwtUtil;
import com.team.shop.service.CartService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.SpyBean;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.doAnswer;

/** D-001: two real HTTP sessions; the pause lives only in this test's Mockito spy. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "shop.jwt.secret=checkout-http-concurrency-0123456789abcdef",
        "shop.admin.initial-password=Checkout-Http-Password8"
})
class ChallengeBCheckoutPublicApiConcurrencyTest {
    @DynamicPropertySource static void database(DynamicPropertyRegistry p) {
        boolean mysql = System.getProperty("challengeb.jdbc.url") != null;
        p.add("spring.datasource.url", () -> System.getProperty("challengeb.jdbc.url",
                "jdbc:h2:mem:b011_http;MODE=MySQL;DB_CLOSE_DELAY=-1"));
        p.add("spring.datasource.driver-class-name", () -> mysql ? "com.mysql.cj.jdbc.Driver" : "org.h2.Driver");
        p.add("spring.datasource.username", () -> mysql ? "root" : "sa");
        p.add("spring.datasource.password", () -> System.getProperty("challengeb.jdbc.password", ""));
        p.add("spring.jpa.hibernate.ddl-auto", () -> mysql ? "none" : "create-drop");
    }

    @LocalServerPort int port;
    @Autowired ObjectMapper json;
    @Autowired CustomerRepository customers;
    @Autowired CategoryRepository categories;
    @Autowired ProductRepository products;
    @Autowired JwtUtil jwt;
    @SpyBean ShopOrderRepository orders;
    @SpyBean CartService cartService;
    private final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();

    record Reply(int status, JsonNode body) {
        JsonNode data() { return body.path("data"); }
    }
    record Fixture(Customer buyer, Product product, String token, String row, String confirmation) {}

    private Reply request(String method, String path, String token, Object body, String key) throws Exception {
        HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + path))
                .timeout(Duration.ofSeconds(30)).header("Authorization", "Bearer " + token)
                .header("Content-Type", "application/json");
        if (key != null) builder.header("Idempotency-Key", key);
        var response = client.send(builder.method(method, body == null ? HttpRequest.BodyPublishers.noBody()
                : HttpRequest.BodyPublishers.ofString(json.writeValueAsString(body))).build(),
                HttpResponse.BodyHandlers.ofString());
        return new Reply(response.statusCode(), json.readTree(response.body()));
    }
    private Reply add(Fixture f) throws Exception {
        return request("POST", "/api/me/cart/items", f.token(),
                Map.of("productId", f.product().getId().toString()), UUID.randomUUID().toString());
    }
    private Reply submit(Fixture f, String key) throws Exception {
        return request("POST", "/api/me/orders", f.token(), Map.of("confirmationToken", f.confirmation()), key);
    }
    private Fixture fixture() throws Exception {
        Customer c = customers.saveAndFlush(new Customer("http-" + UUID.randomUUID(), "hash", "13800000000",
                null, BusinessTime.now()));
        var category = categories.findAll().stream().filter(v -> !v.isRoot()).findFirst().orElseThrow();
        Product p = products.saveAndFlush(Product.create("http-" + UUID.randomUUID(), "",
                new BigDecimal("1.25"), BigInteger.valueOf(5), category));
        String token = jwt.generate(c.getId(), "CUSTOMER", c.getUsername());
        Reply added = request("POST", "/api/me/cart/items", token,
                Map.of("productId", p.getId().toString()), UUID.randomUUID().toString());
        assertEquals(200, added.status(), added.body().toString());
        String row = added.data().path("cartItemId").asText();
        Reply quantity = request("PATCH", "/api/me/cart/items/" + row, token, Map.of("quantity", "2"), null);
        assertEquals(200, quantity.status());
        Reply confirmed = request("POST", "/api/me/checkout/confirmations", token,
                Map.of("cartItemIds", List.of(row)), null);
        assertEquals(200, confirmed.status());
        return new Fixture(c, p, token, row, confirmed.data().path("confirmationToken").asText());
    }
    private static void await(CountDownLatch latch) throws InterruptedException {
        assertTrue(latch.await(15, TimeUnit.SECONDS), "HTTP request did not reach its checkpoint");
    }
    private JsonNode cart(Fixture f) throws Exception {
        Reply r = request("GET", "/api/me/cart", f.token(), null, null);
        assertEquals(200, r.status());
        return r.data().path("items");
    }
    private void evidence(String name, Map<String, Object> data) throws Exception {
        var target = java.nio.file.Path.of("target", name + ".json");
        java.nio.file.Files.createDirectories(target.getParent());
        json.writerWithDefaultPrettyPrinter().writeValue(target.toFile(), data);
    }

    @Test void addAfterCheckoutLocksLeavesOneWhileOrderContainsTwo() throws Exception {
        Fixture f = fixture();
        CountDownLatch locked = new CountDownLatch(1), release = new CountDownLatch(1), addEntered = new CountDownLatch(1);
        // submit() has checked the confirmation and holds customer/product/cart locks before this call.
        doAnswer(invocation -> {
            ShopOrder order = invocation.getArgument(0);
            if (order.getCustomer().getId().equals(f.buyer().getId())) {
                locked.countDown(); await(release);
            }
            // Repository methods are abstract: save+flush keeps the actual persistence operation.
            ShopOrder saved = orders.save(order);
            orders.flush();
            return saved;
        }).when(orders).saveAndFlush(any(ShopOrder.class));
        doAnswer(invocation -> {
            if (f.product().getId().equals(invocation.getArgument(0))) addEntered.countDown();
            return invocation.callRealMethod();
        }).when(cartService).add(anyLong(), anyString());

        ExecutorService pool = Executors.newFixedThreadPool(2);
        String key = UUID.randomUUID().toString();
        try {
            Future<Reply> checkout = pool.submit(() -> submit(f, key));
            await(locked);
            Future<Reply> adding = pool.submit(() -> add(f));
            await(addEntered); // The second HTTP request reached the real service, beyond network dispatch.
            assertThrows(TimeoutException.class, () -> adding.get(250, TimeUnit.MILLISECONDS),
                    "the add must wait behind the customer's checkout transaction");
            assertEquals("2", cart(f).get(0).path("quantity").asText());
            release.countDown();
            Reply placed = checkout.get(20, TimeUnit.SECONDS), added = adding.get(20, TimeUnit.SECONDS);
            assertEquals(201, placed.status(), placed.body().toString());
            assertEquals(200, added.status(), added.body().toString());
            String orderId = placed.data().path("orderId").asText();
            Reply detail = request("GET", "/api/me/orders/" + orderId, f.token(), null, null);
            assertEquals(200, detail.status());
            assertEquals(1, detail.data().path("items").size());
            assertEquals("2", detail.data().path("items").get(0).path("quantity").asText());
            assertEquals("2.50", detail.data().path("totalAmount").asText());
            JsonNode remaining = cart(f);
            assertEquals(1, remaining.size());
            assertEquals("1", remaining.get(0).path("quantity").asText());
            assertEquals(f.product().getId().toString(), remaining.get(0).path("productId").asText());
            assertNotEquals(f.row(), remaining.get(0).path("cartItemId").asText());
            assertEquals(BigInteger.valueOf(3), products.findById(f.product().getId()).orElseThrow().getStock());
            assertEquals(40909, submit(f, key).body().path("code").asInt());
            assertEquals(remaining, cart(f));
            evidence("d001-locked-add", Map.of("checkoutHttp", placed.status(), "addHttp", added.status(),
                    "addReachedServiceBeforeRelease", true, "addWaitedForCheckout", true,
                    "order", detail.data(), "cartAfter", remaining,
                    "stockAfter", products.findById(f.product().getId()).orElseThrow().getStock().toString(),
                    "originalCartItemId", f.row(), "duplicateCheckoutCode", 40909));
        } finally { release.countDown(); pool.shutdownNow(); }
    }

    @Test void quantityChangedBeforeSubmitStillRequiresReconfirmation() throws Exception {
        Fixture f = fixture();
        Reply changed = request("PATCH", "/api/me/cart/items/" + f.row(), f.token(), Map.of("quantity", "3"), null);
        assertEquals(200, changed.status());
        Reply rejected = submit(f, UUID.randomUUID().toString());
        assertEquals(409, rejected.status());
        assertEquals(40913, rejected.body().path("code").asInt());
        assertEquals("3", cart(f).get(0).path("quantity").asText());
        assertEquals(BigInteger.valueOf(5), products.findById(f.product().getId()).orElseThrow().getStock());
        Reply history = request("GET", "/api/me/orders?page=1&size=10", f.token(), null, null);
        assertEquals(200, history.status()); assertTrue(history.data().path("items").isEmpty());
        evidence("d001-before-lock-change", Map.of("submitHttp", rejected.status(),
                "response", rejected.body(), "cartAfter", cart(f), "stockAfter", "5", "orderCount", 0));
    }
}
