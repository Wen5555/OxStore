package com.team.shop;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.team.shop.domain.BusinessTime;
import com.team.shop.entity.AuctionSession;
import com.team.shop.repository.AuctionSessionRepository;
import com.team.shop.service.AuctionSettlementService;
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

import org.springframework.jdbc.core.JdbcTemplate;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

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

    @Autowired
    private AuctionSessionRepository auctions;

    @Autowired
    private AuctionSettlementService auctionSettlement;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JdbcTemplate jdbc;

    @Test
    void buyerSellerCatalogQueueInventoryAndHistoryFlow() throws Exception {
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
        long waitingIntent = submitIntent(productId, buyerToken);
        assertEquals(firstIntent, queueHead(productId, sellerToken));
        startTrade(firstIntent, sellerToken);
        confirmSuccess(firstIntent, sellerToken);
        JsonNode afterFirstSuccess = http.getForObject("/api/products/" + productId, JsonNode.class).path("data");
        assertEquals(1, afterFirstSuccess.path("stock").asInt());
        assertEquals("ONLINE", afterFirstSuccess.path("status").asText());
        JsonNode waitingQueue = get("/api/admin/intents?productId=" + productId, sellerToken).path("data");
        assertEquals(1, waitingQueue.path("total").asInt());
        assertEquals(waitingIntent, waitingQueue.path("items").get(0).path("intentId").asLong());
        assertEquals("QUEUING", waitingQueue.path("items").get(0).path("status").asText());

        startTrade(waitingIntent, sellerToken);
        long discardedIntent = waitingIntent;
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
        submitIntent(manualProductId, buyerToken);
        post("/api/admin/products/" + manualProductId + "/offline", null, sellerToken, 200);
        assertEquals(404, http.getForEntity("/api/products/" + manualProductId, JsonNode.class)
                .getStatusCode().value());
        assertEquals(0, get("/api/admin/intents?productId=" + manualProductId, sellerToken)
                .path("data").path("total").asInt());
        JsonNode historyAfterManualOffline = get("/api/me/order-history?page=1&size=10", buyerToken).path("data");
        assertEquals(5, historyAfterManualOffline.path("total").asInt());
        HttpRequest inventoryRequest = HttpRequest.newBuilder(URI.create(
                        http.getRootUri() + "/api/admin/products/" + manualProductId))
                .header("Authorization", "Bearer " + sellerToken)
                .header("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                .method("PATCH", HttpRequest.BodyPublishers.ofString(
                        objectMapper.writeValueAsString(Map.of("stock", 2, "category2Id", category2Id))))
                .build();
        HttpResponse<String> inventoryResponse = HttpClient.newHttpClient().send(inventoryRequest,
                HttpResponse.BodyHandlers.ofString());
        assertEquals(200, inventoryResponse.statusCode());
        assertEquals(2, objectMapper.readTree(inventoryResponse.body()).path("data").path("stock").asInt());
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

    @Test
    void sellerCanListLiveAuctionsAndCustomerIsDenied() {
        String suffix = Long.toString(System.nanoTime());
        String sellerToken = login("/api/admin/auth/login",
                Map.of("username", "admin", "password", "Test-Pass-9931!"));
        String buyerName = "auction-list-buyer-" + suffix;
        register(buyerName, "13800000004");
        String buyerToken = login("/api/auth/login",
                Map.of("username", buyerName, "password", "customer-pass-8"));
        long category2Id = http.getForObject("/api/categories/tree", JsonNode.class)
                .path("data").get(0).path("children").get(0).path("id").asLong();

        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("name", "管理列表拍卖-" + suffix);
        form.add("category2Id", Long.toString(category2Id));
        form.add("sellingMode", "AUCTION");
        form.add("startPrice", "10.00");
        form.add("minIncrement", "1.00");
        form.add("endsAt", BusinessTime.now().plusMinutes(2).withNano(0).toString());
        HttpHeaders headers = headers(sellerToken);
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        ResponseEntity<JsonNode> created = http.postForEntity("/api/admin/products",
                new HttpEntity<>(form, headers), JsonNode.class);
        assertEquals(201, created.getStatusCode().value());
        long productId = created.getBody().path("data").path("productId").asLong();

        JsonNode auctions = get("/api/admin/auctions?status=LIVE&page=1&size=10", sellerToken).path("data");
        assertTrue(auctions.path("items").toString().contains(Long.toString(productId)));
        assertEquals(403, http.exchange("/api/admin/auctions", HttpMethod.GET,
                new HttpEntity<>(headers(buyerToken)), JsonNode.class).getStatusCode().value());
    }

    @Test
    void fixedPriceProductsKeepTheIntentFlowAndRejectAuctionOperations() {
        String suffix = Long.toString(System.nanoTime());
        String buyerName = "r4-fixed-" + suffix;
        register(buyerName, "13800000005");
        String buyerToken = login("/api/auth/login",
                Map.of("username", buyerName, "password", "customer-pass-8"));
        String sellerToken = login("/api/admin/auth/login",
                Map.of("username", "admin", "password", "Test-Pass-9931!"));
        long category2Id = http.getForObject("/api/categories/tree", JsonNode.class)
                .path("data").get(0).path("children").get(0).path("id").asLong();

        JsonNode product = publish(sellerToken, "R4一口价回归-" + suffix, 2, category2Id, "");
        long productId = product.path("productId").asLong();
        assertEquals("FIXED_PRICE", product.path("sellingMode").asText());
        assertTrue(product.path("canPurchase").asBoolean());
        assertEquals(409, http.getForEntity("/api/products/" + productId + "/auction",
                JsonNode.class).getStatusCode().value());

        ResponseEntity<JsonNode> bidResponse = http.exchange("/api/products/" + productId + "/auction/bids",
                HttpMethod.POST, new HttpEntity<>(Map.of("amount", 13.00), headers(buyerToken)), JsonNode.class);
        assertEquals(409, bidResponse.getStatusCode().value());
        assertEquals(40908, bidResponse.getBody().path("code").asInt());

        long intentId = submitIntent(productId, buyerToken);
        startTrade(intentId, sellerToken);
        confirmSuccess(intentId, sellerToken);
        JsonNode history = get("/api/me/order-history?page=1&size=10", buyerToken).path("data");
        assertEquals(1, history.path("total").asInt());
        assertEquals("SUCCESS", history.path("items").get(0).path("status").asText());
    }

    @Test
    void auctionBidsSettleThroughExistingTradeAndPublishSseNotifications() throws Exception {
        String suffix = Long.toString(System.nanoTime());
        String firstBuyer = "r4-auction-first-" + suffix;
        String winner = "r4-auction-winner-" + suffix;
        register(firstBuyer, "13800000006");
        register(winner, "13800000007");
        String firstBuyerToken = login("/api/auth/login",
                Map.of("username", firstBuyer, "password", "customer-pass-8"));
        String winnerToken = login("/api/auth/login",
                Map.of("username", winner, "password", "customer-pass-8"));
        String sellerToken = login("/api/admin/auth/login",
                Map.of("username", "admin", "password", "Test-Pass-9931!"));
        long category2Id = http.getForObject("/api/categories/tree", JsonNode.class)
                .path("data").get(0).path("children").get(0).path("id").asLong();
        LocalDateTime endsAt = BusinessTime.now().plusMinutes(2).withNano(0);
        long productId = publishAuction(sellerToken, "R4拍卖闭环-" + suffix, category2Id, endsAt);

        ResponseEntity<JsonNode> intentResponse = http.exchange(
                "/api/products/" + productId + "/intents", HttpMethod.POST,
                new HttpEntity<>(headers(firstBuyerToken)), JsonNode.class);
        assertEquals(409, intentResponse.getStatusCode().value());
        assertEquals(40908, intentResponse.getBody().path("code").asInt());

        HttpResponse<InputStream> productStream = openSse(
                "/api/products/" + productId + "/auction/stream", firstBuyerToken);
        try {
            assertEquals(200, productStream.statusCode());
            BufferedReader productReader = reader(productStream.body());
            assertTrue(readSseEvent(productReader, "snapshot").contains("\"canBid\":true"));

            CompletableFuture<String> firstBidEvent = readSseEventAsync(productReader, "bid");
            ResponseEntity<JsonNode> firstBid = placeBid(productId, firstBuyerToken, 10.00);
            assertEquals(201, firstBid.getStatusCode().value());
            assertTrue(firstBidEvent.get(5, TimeUnit.SECONDS).contains("\"youAreLeading\":true"));

            CompletableFuture<String> outbidEvent = readSseEventAsync(productReader, "bid");
            ResponseEntity<JsonNode> winningBid = placeBid(productId, winnerToken, 12.00);
            assertEquals(201, winningBid.getStatusCode().value());
            assertTrue(outbidEvent.get(5, TimeUnit.SECONDS).contains("\"youAreLeading\":false"));

            CompletableFuture<String> settledEvent = readSseEventAsync(productReader, "settled");
            AuctionSession auction = auctions.findByProductId(productId).orElseThrow();
            auctionSettlement.settleOne(auction.getId(), endsAt.plusSeconds(1));

            assertTrue(settledEvent.get(5, TimeUnit.SECONDS).contains("\"youWon\":false"));

            JsonNode adminAuction = get("/api/admin/auctions?status=ENDED_SOLD&page=1&size=10", sellerToken)
                    .path("data").path("items").get(0);
            assertEquals(productId, adminAuction.path("productId").asLong());
            long winnerIntentId = adminAuction.path("winnerIntentId").asLong();
            assertTrue(winnerIntentId > 0);

            JsonNode buyerAlerts = get("/api/me/auction-notifications?page=1&size=10", winnerToken).path("data");
            assertEquals(1, buyerAlerts.path("total").asInt());
            assertEquals("AUCTION_WON", buyerAlerts.path("items").get(0).path("type").asText());
            JsonNode sellerAlerts = get("/api/admin/auction-notifications?page=1&size=10", sellerToken)
                    .path("data");
            assertEquals("AUCTION_SOLD", sellerAlerts.path("items").get(0).path("type").asText());

            confirmSuccess(winnerIntentId, sellerToken);
            JsonNode winnerHistory = get("/api/me/order-history?page=1&size=10", winnerToken).path("data");
            assertEquals(1, winnerHistory.path("total").asInt());
            assertEquals("SUCCESS", winnerHistory.path("items").get(0).path("status").asText());
            assertEquals("WON", get("/api/products/" + productId + "/auction", winnerToken)
                    .path("data").path("myStatus").asText());
        } finally {
            productStream.body().close();
        }
    }

    @Test
    void failedAuctionFulfillmentCannotBeRequeuedAndLeavesFailedHistory() {
        String suffix = Long.toString(System.nanoTime());
        String buyerName = "r4-auction-failed-" + suffix;
        register(buyerName, "13800000008");
        String buyerToken = login("/api/auth/login",
                Map.of("username", buyerName, "password", "customer-pass-8"));
        String sellerToken = login("/api/admin/auth/login",
                Map.of("username", "admin", "password", "Test-Pass-9931!"));
        long category2Id = http.getForObject("/api/categories/tree", JsonNode.class)
                .path("data").get(0).path("children").get(0).path("id").asLong();
        LocalDateTime endsAt = BusinessTime.now().plusMinutes(2).withNano(0);
        long productId = publishAuction(sellerToken, "R4拍卖失败履约-" + suffix, category2Id, endsAt);

        assertEquals(201, placeBid(productId, buyerToken, 10.00).getStatusCode().value());
        AuctionSession auction = auctions.findByProductId(productId).orElseThrow();
        auctionSettlement.settleOne(auction.getId(), endsAt.plusSeconds(1));

        JsonNode endedAuctions = get("/api/admin/auctions?status=ENDED_SOLD&page=1&size=100", sellerToken)
                .path("data").path("items");
        long winnerIntentId = 0;
        for (JsonNode item : endedAuctions) {
            if (item.path("productId").asLong() == productId) {
                winnerIntentId = item.path("winnerIntentId").asLong();
                break;
            }
        }
        assertTrue(winnerIntentId > 0);

        ResponseEntity<JsonNode> requeue = http.exchange("/api/admin/intents/" + winnerIntentId + "/fail",
                HttpMethod.POST, new HttpEntity<>(Map.of("action", "REQUEUE"), headers(sellerToken)), JsonNode.class);
        assertEquals(409, requeue.getStatusCode().value());
        assertEquals(40908, requeue.getBody().path("code").asInt());

        post("/api/admin/intents/" + winnerIntentId + "/fail",
                Map.of("action", "DISCARD"), sellerToken, 200);

        JsonNode history = get("/api/me/order-history?page=1&size=10", buyerToken).path("data");
        assertEquals(1, history.path("total").asInt());
        assertEquals("FAILED", history.path("items").get(0).path("status").asText());
        assertEquals(404, http.getForEntity("/api/products/" + productId, JsonNode.class)
                .getStatusCode().value());

        JsonNode sellerProducts = get("/api/admin/products?page=1&size=100", sellerToken).path("data").path("items");
        for (JsonNode item : sellerProducts) {
            if (item.path("productId").asLong() == productId) {
                assertEquals(1, item.path("stock").asInt());
                assertEquals("OFFLINE", item.path("status").asText());
                assertEquals("AUCTION", item.path("sellingMode").asText());
                return;
            }
        }
        throw new AssertionError("Failed auction product was not present in the seller product list");
    }

    @Test
    void auctionApiRejectsUnauthorizedSellerSelfBidAmountScaleAndLowBid() throws Exception {
        String suffix = Long.toString(System.nanoTime());
        String buyerName = "r2-bid-guard-" + suffix;
        register(buyerName, "13800000011");
        String buyerToken = login("/api/auth/login",
                Map.of("username", buyerName, "password", "customer-pass-8"));
        String sellerToken = login("/api/admin/auth/login",
                Map.of("username", "admin", "password", "Test-Pass-9931!"));
        long category2Id = http.getForObject("/api/categories/tree", JsonNode.class)
                .path("data").get(0).path("children").get(0).path("id").asLong();
        long productId = publishAuction(sellerToken, "R2出价边界-" + suffix, category2Id,
                BusinessTime.now().plusMinutes(2).withNano(0));

        HttpResponse<String> anonymous = HttpClient.newHttpClient().send(
                HttpRequest.newBuilder(URI.create(http.getRootUri() + "/api/products/" + productId + "/auction/bids"))
                        .header("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                        .POST(HttpRequest.BodyPublishers.ofString("{\"amount\":10.00}"))
                        .build(),
                HttpResponse.BodyHandlers.ofString());
        assertEquals(401, anonymous.statusCode());
        assertEquals(40101, objectMapper.readTree(anonymous.body()).path("code").asInt());

        ResponseEntity<JsonNode> sellerBid = placeBid(productId, sellerToken, 10.00);
        assertEquals(403, sellerBid.getStatusCode().value());
        assertEquals(40301, sellerBid.getBody().path("code").asInt());

        ResponseEntity<JsonNode> scale = postJson("/api/products/" + productId + "/auction/bids",
                "{\"amount\":10.001}", buyerToken);
        assertEquals(400, scale.getStatusCode().value());
        assertEquals(40001, scale.getBody().path("code").asInt());

        ResponseEntity<JsonNode> tooLow = placeBid(productId, buyerToken, 9.99);
        assertEquals(409, tooLow.getStatusCode().value());
        assertEquals(40907, tooLow.getBody().path("code").asInt());

        JsonNode publicSnapshot = http.getForObject("/api/products/" + productId + "/auction", JsonNode.class)
                .path("data");
        assertEquals("LIVE", publicSnapshot.path("auctionStatus").asText());
        assertFalse(publicSnapshot.path("canBid").asBoolean());
        assertTrue(publicSnapshot.path("myStatus").isNull() || publicSnapshot.path("myStatus").isMissingNode());

        assertEquals(403, http.exchange("/api/admin/auction-notifications", HttpMethod.GET,
                new HttpEntity<>(headers(buyerToken)), JsonNode.class).getStatusCode().value());
        assertEquals(401, http.getForEntity("/api/me/auction-notifications", JsonNode.class)
                .getStatusCode().value());
    }

    @Test
    void concurrentOpeningBidsAcceptExactlyOne() throws Exception {
        String suffix = Long.toString(System.nanoTime());
        String first = "r2-race-a-" + suffix;
        String second = "r2-race-b-" + suffix;
        register(first, "13800000012");
        register(second, "13800000013");
        String firstToken = login("/api/auth/login", Map.of("username", first, "password", "customer-pass-8"));
        String secondToken = login("/api/auth/login", Map.of("username", second, "password", "customer-pass-8"));
        String sellerToken = login("/api/admin/auth/login",
                Map.of("username", "admin", "password", "Test-Pass-9931!"));
        long category2Id = http.getForObject("/api/categories/tree", JsonNode.class)
                .path("data").get(0).path("children").get(0).path("id").asLong();
        long productId = publishAuction(sellerToken, "R2并发出价-" + suffix, category2Id,
                BusinessTime.now().plusMinutes(2).withNano(0));

        ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            Future<ResponseEntity<JsonNode>> left = pool.submit(() -> placeBid(productId, firstToken, 10.00));
            Future<ResponseEntity<JsonNode>> right = pool.submit(() -> placeBid(productId, secondToken, 10.00));
            int firstStatus = left.get(10, TimeUnit.SECONDS).getStatusCode().value();
            int secondStatus = right.get(10, TimeUnit.SECONDS).getStatusCode().value();
            assertTrue(List.of(firstStatus, secondStatus).contains(201),
                    "one concurrent opening bid must be accepted, got " + firstStatus + "/" + secondStatus);
            assertTrue(List.of(firstStatus, secondStatus).contains(409),
                    "the colliding opening bid must be rejected, got " + firstStatus + "/" + secondStatus);
        } finally {
            pool.shutdownNow();
        }

        JsonNode snapshot = get("/api/products/" + productId + "/auction", firstToken).path("data");
        assertEquals(1, snapshot.path("bidCount").asInt());
        assertEquals(10.00, snapshot.path("currentPrice").asDouble(), 0.001);
    }

    @Test
    void expiredLiveAuctionRejectsBidAndDueScanSettlesUnsoldOnce() {
        String suffix = Long.toString(System.nanoTime());
        String buyerName = "r2-unsold-" + suffix;
        register(buyerName, "13800000014");
        String buyerToken = login("/api/auth/login",
                Map.of("username", buyerName, "password", "customer-pass-8"));
        String sellerToken = login("/api/admin/auth/login",
                Map.of("username", "admin", "password", "Test-Pass-9931!"));
        long category2Id = http.getForObject("/api/categories/tree", JsonNode.class)
                .path("data").get(0).path("children").get(0).path("id").asLong();
        long productId = publishAuction(sellerToken, "R2流拍扫描-" + suffix, category2Id,
                BusinessTime.now().plusMinutes(2).withNano(0));
        expireAuction(productId);

        ResponseEntity<JsonNode> lateBid = placeBid(productId, buyerToken, 10.00);
        assertEquals(409, lateBid.getStatusCode().value());
        assertEquals(40906, lateBid.getBody().path("code").asInt());

        AuctionSession auction = auctions.findByProductId(productId).orElseThrow();
        auctionSettlement.scanDueAuctions();
        JsonNode snapshot = get("/api/products/" + productId + "/auction", buyerToken).path("data");
        assertEquals("ENDED_UNSOLD", snapshot.path("auctionStatus").asText());
        assertFalse(snapshot.path("canBid").asBoolean());

        JsonNode sellerAlerts = get("/api/admin/auction-notifications?page=1&size=100", sellerToken).path("data");
        JsonNode buyerAlerts = get("/api/me/auction-notifications?page=1&size=10", buyerToken).path("data");
        int unsoldReminders = countNotifications(sellerAlerts, "AUCTION_UNSOLD", productId);
        assertEquals(1, unsoldReminders);
        assertEquals(0, countNotifications(buyerAlerts, "AUCTION_UNSOLD", productId));
        assertEquals(0, countNotifications(buyerAlerts, "AUCTION_WON", productId));

        JsonNode ended = get("/api/admin/auctions?status=ENDED_UNSOLD&page=1&size=100", sellerToken)
                .path("data").path("items");
        JsonNode listed = findByProductId(ended, productId);
        assertNotNull(listed);
        assertTrue(listed.path("winnerIntentId").isNull()
                || listed.path("winnerIntentId").isMissingNode()
                || listed.path("winnerIntentId").asLong() == 0);

        auctionSettlement.settleOne(auction.getId(), BusinessTime.now());
        JsonNode afterRepeat = get("/api/admin/auction-notifications?page=1&size=100", sellerToken).path("data");
        assertEquals(1, countNotifications(afterRepeat, "AUCTION_UNSOLD", productId));
    }

    @Test
    void snapshotReportsOutbidAndSseReconnectReplaysSnapshot() throws Exception {
        String suffix = Long.toString(System.nanoTime());
        String firstBuyer = "r2-outbid-a-" + suffix;
        String secondBuyer = "r2-outbid-b-" + suffix;
        register(firstBuyer, "13800000015");
        register(secondBuyer, "13800000016");
        String firstToken = login("/api/auth/login",
                Map.of("username", firstBuyer, "password", "customer-pass-8"));
        String secondToken = login("/api/auth/login",
                Map.of("username", secondBuyer, "password", "customer-pass-8"));
        String sellerToken = login("/api/admin/auth/login",
                Map.of("username", "admin", "password", "Test-Pass-9931!"));
        long category2Id = http.getForObject("/api/categories/tree", JsonNode.class)
                .path("data").get(0).path("children").get(0).path("id").asLong();
        long productId = publishAuction(sellerToken, "R2领先出局-" + suffix, category2Id,
                BusinessTime.now().plusMinutes(2).withNano(0));

        assertEquals(201, placeBid(productId, firstToken, 10.00).getStatusCode().value());
        assertEquals(201, placeBid(productId, secondToken, 12.00).getStatusCode().value());
        assertEquals("OUTBID", get("/api/products/" + productId + "/auction", firstToken)
                .path("data").path("myStatus").asText());
        assertEquals("LEADING", get("/api/products/" + productId + "/auction", secondToken)
                .path("data").path("myStatus").asText());

        HttpResponse<InputStream> firstStream = openSse("/api/products/" + productId + "/auction/stream", firstToken);
        try {
            assertEquals(200, firstStream.statusCode());
            assertTrue(readSseEvent(reader(firstStream.body()), "snapshot").contains("\"lastBidSeq\":2"));
        } finally {
            firstStream.body().close();
        }

        HttpResponse<InputStream> reconnect = openSse("/api/products/" + productId + "/auction/stream", firstToken);
        try {
            String snapshot = readSseEvent(reader(reconnect.body()), "snapshot");
            assertTrue(snapshot.contains("\"lastBidSeq\":2"));
            assertTrue(snapshot.contains("\"myStatus\":\"OUTBID\""));
        } finally {
            reconnect.body().close();
        }

        AuctionSession auction = auctions.findByProductId(productId).orElseThrow();
        auctionSettlement.settleOne(auction.getId(), BusinessTime.now().plusMinutes(3));
        assertEquals("WON", get("/api/products/" + productId + "/auction", secondToken)
                .path("data").path("myStatus").asText());
        assertEquals("LOST", get("/api/products/" + productId + "/auction", firstToken)
                .path("data").path("myStatus").asText());
        auctionSettlement.settleOne(auction.getId(), BusinessTime.now().plusMinutes(4));
        JsonNode sellerAlerts = get("/api/admin/auction-notifications?page=1&size=100", sellerToken).path("data");
        JsonNode winnerAlerts = get("/api/me/auction-notifications?page=1&size=10", secondToken).path("data");
        assertEquals(1, countNotifications(sellerAlerts, "AUCTION_SOLD", productId));
        assertEquals(1, countNotifications(winnerAlerts, "AUCTION_WON", productId));
        assertEquals(0, countNotifications(
                get("/api/me/auction-notifications?page=1&size=10", firstToken).path("data"),
                "AUCTION_WON", productId));
    }

    @Test
    void auctionPublishValidatesModeExclusiveFields() {
        String suffix = Long.toString(System.nanoTime());
        String sellerToken = login("/api/admin/auth/login",
                Map.of("username", "admin", "password", "Test-Pass-9931!"));
        long category2Id = http.getForObject("/api/categories/tree", JsonNode.class)
                .path("data").get(0).path("children").get(0).path("id").asLong();

        MultiValueMap<String, Object> missing = auctionForm("缺截止-" + suffix, category2Id);
        missing.remove("endsAt");
        assertEquals(400, postMultipart("/api/admin/products", missing, sellerToken).getStatusCode().value());

        MultiValueMap<String, Object> soon = auctionForm("截止过近-" + suffix, category2Id);
        soon.set("endsAt", BusinessTime.now().plusSeconds(30).withNano(0).toString());
        ResponseEntity<JsonNode> soonResponse = postMultipart("/api/admin/products", soon, sellerToken);
        assertEquals(400, soonResponse.getStatusCode().value());
        assertEquals(40001, soonResponse.getBody().path("code").asInt());

        MultiValueMap<String, Object> stock = auctionForm("拍卖库存-" + suffix, category2Id);
        stock.add("stock", "2");
        ResponseEntity<JsonNode> stockResponse = postMultipart("/api/admin/products", stock, sellerToken);
        assertEquals(400, stockResponse.getStatusCode().value());
        assertEquals(40001, stockResponse.getBody().path("code").asInt());

        MultiValueMap<String, Object> mixed = new LinkedMultiValueMap<>();
        mixed.add("name", "一口价带拍卖字段-" + suffix);
        mixed.add("price", "12.50");
        mixed.add("category2Id", Long.toString(category2Id));
        mixed.add("stock", "1");
        mixed.add("sellingMode", "FIXED_PRICE");
        mixed.add("startPrice", "10.00");
        mixed.add("minIncrement", "1.00");
        mixed.add("endsAt", BusinessTime.now().plusMinutes(2).withNano(0).toString());
        ResponseEntity<JsonNode> mixedResponse = postMultipart("/api/admin/products", mixed, sellerToken);
        assertEquals(400, mixedResponse.getStatusCode().value(),
                "P-A13/P-A00: FIXED_PRICE 发布携带拍卖字段应返回 40001，实际 HTTP "
                        + mixedResponse.getStatusCode().value() + " body=" + mixedResponse.getBody());
        assertEquals(40001, mixedResponse.getBody().path("code").asInt());
    }

    private long publishAuction(String sellerToken, String name, long category2Id, LocalDateTime endsAt) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("name", name);
        form.add("category2Id", Long.toString(category2Id));
        form.add("sellingMode", "AUCTION");
        form.add("startPrice", "10.00");
        form.add("minIncrement", "2.00");
        form.add("endsAt", endsAt.toString());
        HttpHeaders headers = headers(sellerToken);
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        ResponseEntity<JsonNode> response = http.postForEntity("/api/admin/products",
                new HttpEntity<>(form, headers), JsonNode.class);
        assertEquals(201, response.getStatusCode().value());
        return response.getBody().path("data").path("productId").asLong();
    }

    private ResponseEntity<JsonNode> placeBid(long productId, String buyerToken, double amount) {
        return http.exchange("/api/products/" + productId + "/auction/bids", HttpMethod.POST,
                new HttpEntity<>(Map.of("amount", amount), headers(buyerToken)), JsonNode.class);
    }

    private ResponseEntity<JsonNode> postJson(String path, String json, String token) {
        HttpHeaders headers = token == null ? new HttpHeaders() : headers(token);
        headers.setContentType(MediaType.APPLICATION_JSON);
        return http.exchange(path, HttpMethod.POST, new HttpEntity<>(json, headers), JsonNode.class);
    }

    private ResponseEntity<JsonNode> postMultipart(String path, MultiValueMap<String, Object> form, String token) {
        HttpHeaders headers = headers(token);
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        return http.postForEntity(path, new HttpEntity<>(form, headers), JsonNode.class);
    }

    private MultiValueMap<String, Object> auctionForm(String name, long category2Id) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        form.add("name", name);
        form.add("category2Id", Long.toString(category2Id));
        form.add("sellingMode", "AUCTION");
        form.add("startPrice", "10.00");
        form.add("minIncrement", "2.00");
        form.add("endsAt", BusinessTime.now().plusMinutes(2).withNano(0).toString());
        return form;
    }

    private void expireAuction(long productId) {
        jdbc.update("UPDATE auction_session SET ends_at = ? WHERE product_id = ?",
                java.sql.Timestamp.valueOf("2020-01-01 00:00:00"), productId);
    }

    private int countNotifications(JsonNode page, String type, long productId) {
        int count = 0;
        for (JsonNode item : page.path("items")) {
            if (type.equals(item.path("type").asText()) && item.path("productId").asLong() == productId) {
                count++;
            }
        }
        return count;
    }

    private JsonNode findByProductId(JsonNode items, long productId) {
        for (JsonNode item : items) {
            if (item.path("productId").asLong() == productId) {
                return item;
            }
        }
        return null;
    }

    private HttpResponse<InputStream> openSse(String path, String token) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(URI.create(http.getRootUri() + path))
                .timeout(Duration.ofSeconds(10))
                .header("Accept", "text/event-stream")
                .header("Authorization", "Bearer " + token)
                .GET().build();
        return HttpClient.newHttpClient().send(request, HttpResponse.BodyHandlers.ofInputStream());
    }

    private BufferedReader reader(InputStream stream) {
        return new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8));
    }

    private String readSseEvent(BufferedReader reader, String expectedEvent) throws Exception {
        StringBuilder event = new StringBuilder();
        boolean matching = false;
        String line;
        while ((line = reader.readLine()) != null) {
            if (line.isEmpty()) {
                if (matching) return event.toString();
                event.setLength(0);
                continue;
            }
            if (line.startsWith("event:")) matching = line.substring("event:".length()).trim().equals(expectedEvent);
            if (matching) event.append(line).append('\n');
        }
        throw new AssertionError("SSE stream closed before " + expectedEvent);
    }

    private CompletableFuture<String> readSseEventAsync(BufferedReader reader, String expectedEvent) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                return readSseEvent(reader, expectedEvent);
            } catch (Exception exception) {
                throw new IllegalStateException("Could not read SSE event: " + expectedEvent, exception);
            }
        });
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
