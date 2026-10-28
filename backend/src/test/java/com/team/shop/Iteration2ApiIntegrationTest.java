package com.team.shop;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "spring.datasource.url=jdbc:h2:mem:oxstore_it;MODE=MySQL;DB_CLOSE_DELAY=-1",
        "spring.datasource.username=sa",
        "spring.datasource.password=",
        "spring.datasource.driver-class-name=org.h2.Driver",
        "spring.jpa.hibernate.ddl-auto=create-drop",
        "shop.jwt.secret=oxstore-integration-secret-0123456789abcdef",
        "shop.upload-dir=target/integration-uploads",
        "shop.admin.initial-password=Test-Pass-9931!"
})
class Iteration2ApiIntegrationTest {
    @Autowired
    private TestRestTemplate http;

    @Test
    void buyerSellerCatalogQueueInventoryAndHistoryFlow() {
        ResponseEntity<JsonNode> registration = http.postForEntity("/api/auth/register",
                Map.of("username", "buyer1", "password", "customer-pass-8",
                        "phone", "13800000000"), JsonNode.class);
        assertEquals(201, registration.getStatusCode().value());
        assertNotNull(registration.getBody().path("data").path("customerId").asLong());

        String buyerToken = login("/api/auth/login", Map.of("username", "buyer1", "password", "customer-pass-8"));
        String sellerToken = login("/api/admin/auth/login",
                Map.of("username", "admin", "password", "Test-Pass-9931!"));
        JsonNode categoryTree = http.getForObject("/api/categories/tree", JsonNode.class).path("data");
        assertTrue(categoryTree.size() >= 1);
        long category2Id = categoryTree.get(0).path("children").get(0).path("id").asLong();
        assertUnsafeDescriptionRejected(sellerToken, category2Id);

        JsonNode product = publish(sellerToken, "终态历史商品", 2, category2Id,
                "<p><strong>SearchPhrase</strong><br><em>rich description</em></p>");
        long productId = product.path("productId").asLong();
        JsonNode listed = http.getForObject("/api/products?category2Id=" + category2Id + "&q=SearchPhrase",
                JsonNode.class).path("data").path("items").get(0);
        assertEquals(productId, listed.path("productId").asLong());
        assertFalse(listed.has("descriptionHtml"));
        assertFalse(listed.has("stock"));

        assertEquals(401, http.getForEntity("/api/me/order-history", JsonNode.class).getStatusCode().value());
        JsonNode detail = http.getForObject("/api/products/" + productId, JsonNode.class).path("data");
        assertTrue(detail.path("canPurchase").asBoolean());
        assertTrue(detail.path("descriptionHtml").asText().contains("<strong>"));

        long firstIntent = submitIntent(productId, buyerToken);
        assertEquals(firstIntent, queueHead(productId, sellerToken));
        startTrade(firstIntent, sellerToken);
        confirmSuccess(firstIntent, sellerToken);
        assertEquals(1, http.getForObject("/api/products/" + productId, JsonNode.class)
                .path("data").path("stock").asInt());

        long discardedIntent = submitIntent(productId, buyerToken);
        startTrade(discardedIntent, sellerToken);
        post("/api/admin/intents/" + discardedIntent + "/fail",
                Map.of("action", "DISCARD"), sellerToken, 200);

        long finalSale = submitIntent(productId, buyerToken);
        long queuedAtZero = submitIntent(productId, buyerToken);
        startTrade(finalSale, sellerToken);
        confirmSuccess(finalSale, sellerToken);
        assertEquals(404, http.getForEntity("/api/products/" + productId, JsonNode.class)
                .getStatusCode().value());

        JsonNode buyerHistory = get("/api/me/order-history?page=1&size=10", buyerToken).path("data");
        assertEquals(4, buyerHistory.path("total").asInt());
        assertTrue(hasHistoryStatus(buyerHistory, "SUCCESS"));
        assertTrue(hasHistoryStatus(buyerHistory, "FAILED"));

        JsonNode queueAfterOffline = get("/api/admin/intents?productId=" + productId, sellerToken).path("data");
        assertEquals(0, queueAfterOffline.path("total").asInt());
        assertNotNull(queuedAtZero);

        JsonNode customers = get("/api/admin/customers?page=1&size=10", sellerToken).path("data");
        assertTrue(customers.path("total").asInt() >= 1);
        JsonNode firstCustomer = null;
        for (JsonNode item : customers.path("items")) {
            if ("buyer1".equals(item.path("username").asText())) {
                firstCustomer = item;
                break;
            }
        }
        assertNotNull(firstCustomer);
        assertEquals("未设置", firstCustomer.path("location").asText());
        long customerId = firstCustomer.path("customerId").asLong();
        JsonNode sellerHistory = get(
                "/api/admin/customers/" + customerId + "/order-history?page=1&size=10", sellerToken).path("data");
        assertEquals(4, sellerHistory.path("total").asInt());
        assertEquals(403, http.exchange("/api/admin/customers", HttpMethod.GET,
                new HttpEntity<>(headers(buyerToken)), JsonNode.class).getStatusCode().value());

        JsonNode manuallyManaged = publish(sellerToken, "手动上下架商品", 1, category2Id, "");
        long manualProductId = manuallyManaged.path("productId").asLong();
        post("/api/admin/products/" + manualProductId + "/offline", null, sellerToken, 200);
        assertEquals(404, http.getForEntity("/api/products/" + manualProductId, JsonNode.class)
                .getStatusCode().value());
        post("/api/admin/products/" + manualProductId + "/online", null, sellerToken, 200);
        assertEquals("ONLINE", http.getForObject("/api/products/" + manualProductId,
                JsonNode.class).path("data").path("status").asText());
    }

    @Test
    void customerAuthUsesContractCodeAndRoleGuards() {
        String suffix = Long.toString(System.nanoTime());
        String username = "r1-auth-" + suffix;
        ResponseEntity<JsonNode> first = http.postForEntity("/api/auth/register",
                Map.of("username", username, "password", "customer-pass-8", "phone", "13800000001"),
                JsonNode.class);
        assertEquals(201, first.getStatusCode().value());

        ResponseEntity<JsonNode> duplicate = http.postForEntity("/api/auth/register",
                Map.of("username", username, "password", "customer-pass-8", "phone", "13800000001"),
                JsonNode.class);
        assertEquals(409, duplicate.getStatusCode().value());
        assertEquals(40903, duplicate.getBody().path("code").asInt());

        String customerToken = login("/api/auth/login",
                Map.of("username", username, "password", "customer-pass-8"));
        assertEquals(403, http.exchange("/api/admin/products", HttpMethod.GET,
                new HttpEntity<>(headers(customerToken)), JsonNode.class).getStatusCode().value());
        assertEquals(401, http.getForEntity("/api/me/order-history", JsonNode.class)
                .getStatusCode().value());
    }

    @Test
    void independentProductQueuesCanEnterTradeAtTheSameTime() {
        String suffix = Long.toString(System.nanoTime());
        String customerA = "r1-queue-a-" + suffix;
        String customerB = "r1-queue-b-" + suffix;
        register(customerA, "13800000002");
        register(customerB, "13800000003");
        String buyerTokenA = login("/api/auth/login",
                Map.of("username", customerA, "password", "customer-pass-8"));
        String buyerTokenB = login("/api/auth/login",
                Map.of("username", customerB, "password", "customer-pass-8"));
        String sellerToken = login("/api/admin/auth/login",
                Map.of("username", "admin", "password", "Test-Pass-9931!"));
        JsonNode categories = http.getForObject("/api/categories/tree", JsonNode.class).path("data");
        long category2Id = categories.get(0).path("children").get(0).path("id").asLong();

        long productA = publish(sellerToken, "R1独立队列A-" + suffix, 2, category2Id, "")
                .path("productId").asLong();
        long productB = publish(sellerToken, "R1独立队列B-" + suffix, 2, category2Id, "")
                .path("productId").asLong();
        long intentA = submitIntent(productA, buyerTokenA);
        long intentB = submitIntent(productB, buyerTokenB);

        startTrade(intentA, sellerToken);
        startTrade(intentB, sellerToken);

        JsonNode queueA = get("/api/admin/intents?productId=" + productA, sellerToken)
                .path("data").path("items");
        JsonNode queueB = get("/api/admin/intents?productId=" + productB, sellerToken)
                .path("data").path("items");
        assertEquals("IN_TRANSACTION", queueA.get(0).path("status").asText());
        assertEquals("IN_TRANSACTION", queueB.get(0).path("status").asText());

        post("/api/admin/intents/" + intentA + "/fail", Map.of("action", "DISCARD"), sellerToken, 200);
        post("/api/admin/intents/" + intentB + "/fail", Map.of("action", "DISCARD"), sellerToken, 200);
    }

    private JsonNode publish(String sellerToken, String name, int stock, long category2Id,
                             String descriptionHtml) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("name", name);
        form.add("price", "12.50");
        form.add("category2Id", Long.toString(category2Id));
        form.add("stock", Integer.toString(stock));
        form.add("descriptionHtml", descriptionHtml);
        HttpHeaders headers = headers(sellerToken);
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        ResponseEntity<JsonNode> response = http.postForEntity("/api/admin/products",
                new HttpEntity<>(form, headers), JsonNode.class);
        assertEquals(201, response.getStatusCode().value());
        return response.getBody().path("data");
    }

    private void assertUnsafeDescriptionRejected(String sellerToken, long category2Id) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("name", "不安全描述");
        form.add("price", "12.50");
        form.add("category2Id", Long.toString(category2Id));
        form.add("stock", "1");
        form.add("descriptionHtml", "<script>alert(1)</script>");
        HttpHeaders headers = headers(sellerToken);
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        ResponseEntity<JsonNode> response = http.postForEntity("/api/admin/products",
                new HttpEntity<>(form, headers), JsonNode.class);
        assertEquals(422, response.getStatusCode().value());
    }

    private String login(String path, Map<String, String> credentials) {
        ResponseEntity<JsonNode> response = http.postForEntity(path, credentials, JsonNode.class);
        assertEquals(200, response.getStatusCode().value());
        return response.getBody().path("data").path("token").asText();
    }

    private void register(String username, String phone) {
        ResponseEntity<JsonNode> response = http.postForEntity("/api/auth/register",
                Map.of("username", username, "password", "customer-pass-8", "phone", phone),
                JsonNode.class);
        assertEquals(201, response.getStatusCode().value());
    }

    private long submitIntent(long productId, String buyerToken) {
        ResponseEntity<JsonNode> response = http.postForEntity(
                "/api/products/" + productId + "/intents", new HttpEntity<>(headers(buyerToken)), JsonNode.class);
        assertEquals(200, response.getStatusCode().value());
        return response.getBody().path("data").path("intentId").asLong();
    }

    private long queueHead(long productId, String sellerToken) {
        JsonNode items = get("/api/admin/intents?productId=" + productId, sellerToken)
                .path("data").path("items");
        assertTrue(items.size() > 0);
        return items.get(0).path("intentId").asLong();
    }

    private void startTrade(long intentId, String sellerToken) {
        post("/api/admin/intents/" + intentId + "/start", null, sellerToken, 200);
    }

    private void confirmSuccess(long intentId, String sellerToken) {
        post("/api/admin/intents/" + intentId + "/success", null, sellerToken, 200);
    }

    private void post(String path, Object body, String token, int expectedStatus) {
        ResponseEntity<JsonNode> response = http.exchange(path, HttpMethod.POST,
                new HttpEntity<>(body, headers(token)), JsonNode.class);
        assertEquals(expectedStatus, response.getStatusCode().value());
    }

    private HttpHeaders headers(String token) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);
        return headers;
    }

    private JsonNode get(String path, String token) {
        return http.exchange(path, HttpMethod.GET, new HttpEntity<>(headers(token)), JsonNode.class).getBody();
    }

    private boolean hasHistoryStatus(JsonNode history, String status) {
        for (JsonNode item : history.path("items")) {
            if (status.equals(item.path("status").asText())) {
                return true;
            }
        }
        return false;
    }
}
