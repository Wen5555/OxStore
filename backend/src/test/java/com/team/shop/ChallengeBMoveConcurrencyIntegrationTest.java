package com.team.shop;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.ReceiptOperationType;
import com.team.shop.entity.*;
import com.team.shop.repository.*;
import com.team.shop.security.JwtUtil;
import jakarta.persistence.PersistenceException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.SpyBean;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.support.TransactionTemplate;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;

/** B-026: real transactions/connections, controlled ordering, and storage fault injection. */
@SpringBootTest(properties = {
        "shop.jwt.secret=move-concurrency-secret-0123456789abcdef",
        "shop.admin.initial-password=Move-Password8"
})
@AutoConfigureMockMvc
class ChallengeBMoveConcurrencyIntegrationTest {
    @DynamicPropertySource static void database(DynamicPropertyRegistry p) {
        boolean mysql = System.getProperty("challengeb.jdbc.url") != null;
        p.add("spring.datasource.url", () -> System.getProperty("challengeb.jdbc.url",
                "jdbc:h2:mem:b026;MODE=MySQL;DB_CLOSE_DELAY=-1"));
        p.add("spring.datasource.driver-class-name", () -> mysql ? "com.mysql.cj.jdbc.Driver" : "org.h2.Driver");
        p.add("spring.datasource.username", () -> mysql ? "root" : "sa");
        p.add("spring.datasource.password", () -> System.getProperty("challengeb.jdbc.password", ""));
        p.add("spring.jpa.hibernate.ddl-auto", () -> mysql ? "none" : "create-drop");
    }

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JwtUtil jwt;
    @Autowired CustomerRepository customers;
    @Autowired ProductRepository products;
    @Autowired CategoryRepository categories;
    @Autowired FavoriteMutationRepository mutations;
    @Autowired CartItemTombstoneRepository tombstones;
    @Autowired ShopOrderRepository orders;
    @Autowired TransactionTemplate tx;
    @Autowired JdbcTemplate jdbc;
    @SpyBean FavoriteRepository favorites;
    @SpyBean CartItemRepository cart;
    @SpyBean OperationReceiptRepository receipts;

    record Reply(int status, JsonNode body) {
        int code() { return body.path("code").asInt(); }
        JsonNode data() { return body.path("data"); }
    }
    @FunctionalInterface interface Action { Reply run() throws Exception; }
    record Race(Reply move, Reply other, String key) {}

    private Customer buyer() {
        return customers.saveAndFlush(new Customer("move-" + UUID.randomUUID(), "hash",
                "13800000000", null, BusinessTime.now()));
    }
    private Product product() {
        var category = categories.findAll().stream().filter(c -> !c.isRoot()).findFirst().orElseThrow();
        return products.saveAndFlush(Product.create("move-" + UUID.randomUUID(), "", new BigDecimal("2.50"),
                BigInteger.TWO, category));
    }
    private String token(Customer c) { return jwt.generate(c.getId(), "CUSTOMER", c.getUsername()); }
    private Reply reply(org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder request,
                        Customer c) throws Exception {
        var response = mvc.perform(request.header("Authorization", "Bearer " + token(c)))
                .andReturn().getResponse();
        return new Reply(response.getStatus(), json.readTree(response.getContentAsString(StandardCharsets.UTF_8)));
    }
    private Reply add(Customer c, Product p) throws Exception {
        return reply(post("/api/me/cart/items").contentType(MediaType.APPLICATION_JSON)
                .header("Idempotency-Key", UUID.randomUUID().toString())
                .content(json.writeValueAsString(Map.of("productId", p.getId().toString()))), c);
    }
    private String row(Customer c, Product p) throws Exception {
        Reply r = add(c, p);
        assertEquals(200, r.status(), r.body().toString());
        return r.data().path("cartItemId").asText();
    }
    private Reply quantity(Customer c, String id, String quantity) throws Exception {
        return reply(patch("/api/me/cart/items/" + id).contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("quantity", quantity))), c);
    }
    private Reply remove(Customer c, String id) throws Exception {
        return reply(delete("/api/me/cart/items/" + id), c);
    }
    private Reply favorite(Customer c, Product p) throws Exception {
        return reply(put("/api/me/favorites/" + p.getId()), c);
    }
    private Reply cancel(Customer c, Product p) throws Exception {
        return reply(delete("/api/me/favorites/" + p.getId()), c);
    }
    private Reply move(Customer c, String key, String... ids) throws Exception {
        return reply(post("/api/me/cart/move-to-favorites").contentType(MediaType.APPLICATION_JSON)
                .header("Idempotency-Key", key)
                .content(json.writeValueAsString(Map.of("cartItemIds", List.of(ids)))), c);
    }
    private OperationReceipt receipt(Customer c, String key) {
        return receipts.findByCustomerIdAndOperationTypeAndRequestKey(c.getId(),
                ReceiptOperationType.MOVE_TO_FAVORITES, key).orElseThrow();
    }
    private Favorite savedFavorite(Customer c, Product p) {
        return favorites.findByCustomerIdAndProductId(c.getId(), p.getId()).orElseThrow();
    }
    private void moved(Customer c, String id) {
        assertFalse(cart.existsById(Long.valueOf(id)));
        assertEquals(c.getId(), tombstones.findByCartItemId(Long.valueOf(id)).orElseThrow().getCustomerId());
    }
    private static void await(CountDownLatch latch) throws InterruptedException {
        assertTrue(latch.await(15, TimeUnit.SECONDS), "concurrent request did not reach the expected checkpoint");
    }
    private static Reply invoke(Action action) {
        try { return action.run(); } catch (Exception e) { throw new CompletionException(e); }
    }

    /** Pause after the move's business writes have flushed but before its receipt/transaction commits. */
    private Race afterMove(Customer c, Action later, String... ids) throws Exception {
        String key = UUID.randomUUID().toString();
        CountDownLatch written = new CountDownLatch(1), release = new CountDownLatch(1), started = new CountDownLatch(1);
        doAnswer(invocation -> {
            OperationReceipt r = invocation.getArgument(0);
            if (r.getOperationType() == ReceiptOperationType.MOVE_TO_FAVORITES && r.getRequestKey().equals(key)) {
                written.countDown();
                await(release);
            }
            // Spring Data repository methods are abstract; use save+flush rather than callRealMethod().
            OperationReceipt saved = receipts.save(r);
            receipts.flush();
            return saved;
        }).when(receipts).saveAndFlush(any(OperationReceipt.class));
        ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            Future<Reply> moving = pool.submit(() -> move(c, key, ids));
            await(written);
            Future<Reply> other = pool.submit(() -> { started.countDown(); return later.run(); });
            await(started);
            assertThrows(TimeoutException.class, () -> other.get(200, TimeUnit.MILLISECONDS),
                    "later operation must wait for the moving customer's transaction");
            release.countDown();
            return new Race(moving.get(20, TimeUnit.SECONDS), other.get(20, TimeUnit.SECONDS), key);
        } finally { release.countDown(); pool.shutdownNow(); }
    }

    /** Hold an earlier cart mutation uncommitted, so the move must reread after obtaining the customer lock. */
    private Race beforeMove(Customer c, Action earlier, String... ids) throws Exception {
        String key = UUID.randomUUID().toString();
        CountDownLatch written = new CountDownLatch(1), release = new CountDownLatch(1), started = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            Future<Reply> other = pool.submit(() -> tx.execute(s -> {
                customers.findByIdForUpdate(c.getId()).orElseThrow();
                Reply r = invoke(earlier);
                cart.flush();
                written.countDown();
                try { await(release); } catch (InterruptedException e) { throw new CompletionException(e); }
                return r;
            }));
            await(written);
            Future<Reply> moving = pool.submit(() -> { started.countDown(); return move(c, key, ids); });
            await(started);
            assertThrows(TimeoutException.class, () -> moving.get(200, TimeUnit.MILLISECONDS));
            release.countDown();
            return new Race(moving.get(20, TimeUnit.SECONDS), other.get(20, TimeUnit.SECONDS), key);
        } finally { release.countDown(); pool.shutdownNow(); }
    }

    @Test void sameKeyConcurrentRequestsCommitOnceAndDifferentBodyIsRejected() throws Exception {
        Customer c = buyer(); Product p = product(), q = product();
        String id = row(c, p), unselected = row(c, q), key = UUID.randomUUID().toString();
        CountDownLatch start = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            Callable<Reply> action = () -> { await(start); return move(c, key, id, id); };
            Future<Reply> a = pool.submit(action), b = pool.submit(action);
            start.countDown();
            assertEquals(List.of(0, 40915), java.util.stream.Stream.of(a.get(20, TimeUnit.SECONDS),
                    b.get(20, TimeUnit.SECONDS)).map(Reply::code).sorted().toList());
        } finally { start.countDown(); pool.shutdownNow(); }
        moved(c, id); savedFavorite(c, p);
        assertEquals(40916, move(c, key, unselected).code());
        assertTrue(cart.existsById(Long.valueOf(unselected)));
        assertEquals(1, mutations.findById(new FavoriteMutation.Key(c.getId(), p.getId())).orElseThrow().getOperationSeq());
        assertEquals(List.of(id), json.convertValue(json.readTree(receipt(c, key).getResultPayload())
                .path("result").path("movedCartItemIds"), List.class));
    }

    @Test void normalizedSelectionKeepsOriginalResultOrderForPermutedRetries() throws Exception {
        Customer c = buyer(); Product p = product(), q = product();
        String x = row(c, p), y = row(c, q), key = UUID.randomUUID().toString();
        Reply first = move(c, key, y, x, y);
        assertEquals(200, first.status());
        assertEquals(List.of(y, x), json.convertValue(first.data().path("movedCartItemIds"), List.class));
        assertEquals(40915, move(c, key, x, y).code());
        assertEquals(200, cancel(c, p).status());
        Reply replay = move(c, key, x, y, x);
        assertEquals(first.data(), replay.data());
        assertFalse(favorites.findByCustomerIdAndProductId(c.getId(), p.getId()).isPresent());
        assertEquals(40916, move(c, key, x).code());
    }

    @Test void legacyOrderSensitiveReceiptRemainsUsableIncludingItsSkippedRows() throws Exception {
        Customer c = buyer(); Product p = product(), q = product();
        String x = row(c, p), y = row(c, q), key = UUID.randomUUID().toString();
        remove(c, x);
        Reply first = move(c, key, y, x);
        assertEquals(200, first.status());
        byte[] legacyBody = json.writeValueAsBytes(List.of(y, x));
        String oldHash = java.util.HexFormat.of().formatHex(java.security.MessageDigest
                .getInstance("SHA-256").digest(legacyBody));
        jdbc.update("update operation_receipt set request_hash = ? where id = ?", oldHash, receipt(c, key).getId());
        assertEquals(40915, move(c, key, x, y).code());
        assertEquals(40916, move(c, key, y).code());
        cancel(c, q);
        Reply replay = move(c, key, x, y);
        assertEquals(200, replay.status()); assertEquals(first.data(), replay.data());
        assertFalse(favorites.findByCustomerIdAndProductId(c.getId(), q.getId()).isPresent());
    }

    @Test void overlappingDifferentKeysMoveEachRowOnceAndSkipTheAlreadyMovedRow() throws Exception {
        Customer c = buyer(); Product p = product(), q = product(), r = product();
        String x = row(c, p), y = row(c, q), z = row(c, r);
        CountDownLatch start = new CountDownLatch(1); ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            Future<Reply> a = pool.submit(() -> { await(start); return move(c, UUID.randomUUID().toString(), x, y); });
            Future<Reply> b = pool.submit(() -> { await(start); return move(c, UUID.randomUUID().toString(), y, z); });
            start.countDown();
            Reply first = a.get(20, TimeUnit.SECONDS), second = b.get(20, TimeUnit.SECONDS);
            assertEquals(200, first.status()); assertEquals(200, second.status());
            assertEquals(List.of(1, 2), java.util.stream.Stream.of(first, second)
                    .map(value -> value.data().path("movedLineCount").asInt()).sorted().toList());
            assertEquals(1, first.data().path("skippedDeletedCartItemIds").size()
                    + second.data().path("skippedDeletedCartItemIds").size());
        } finally { start.countDown(); pool.shutdownNow(); }
        moved(c, x); moved(c, y); moved(c, z);
        savedFavorite(c, p); savedFavorite(c, q); savedFavorite(c, r);
        assertEquals(1, mutations.findById(new FavoriteMutation.Key(c.getId(), q.getId())).orElseThrow().getOperationSeq());
    }

    @Test void earlierQuantityChangeMovesEntireRowWithoutStockOrOrderChanges() throws Exception {
        Customer c = buyer(); Product p = product(); String id = row(c, p);
        long orderCount = orders.count();
        Race r = beforeMove(c, () -> quantity(c, id, "999999999999999999999999999999"), id);
        assertEquals(200, r.other().status()); assertEquals(200, r.move().status());
        assertEquals(1, r.move().data().path("movedLineCount").asInt());
        moved(c, id); savedFavorite(c, p);
        Product unchanged = products.findById(p.getId()).orElseThrow();
        assertEquals(BigInteger.TWO, unchanged.getStock());
        assertEquals(p.getStatus(), unchanged.getStatus()); assertEquals(orderCount, orders.count());
    }

    @Test void earlierAddIsIncludedInTheEntireMovedRow() throws Exception {
        Customer c = buyer(); Product p = product(); String id = row(c, p);
        Race r = beforeMove(c, () -> add(c, p), id);
        assertEquals(id, r.other().data().path("cartItemId").asText());
        assertEquals("2", r.other().data().path("quantity").asText());
        assertEquals(200, r.move().status()); moved(c, id);
        assertTrue(cart.findByCustomerIdOrderByIdAsc(c.getId()).isEmpty());
    }

    @Test void earlierDeletionIsSkippedAndActualCountIsReturned() throws Exception {
        Customer c = buyer(); Product p = product(), q = product();
        String x = row(c, p), y = row(c, q);
        Race r = beforeMove(c, () -> remove(c, x), x, y);
        assertEquals(200, r.move().status());
        assertEquals(1, r.move().data().path("movedLineCount").asInt());
        assertEquals(List.of(x), json.convertValue(r.move().data().path("skippedDeletedCartItemIds"), List.class));
        assertFalse(favorites.findByCustomerIdAndProductId(c.getId(), p.getId()).isPresent());
        savedFavorite(c, q); moved(c, y);
    }

    @Test void earlierClearRejectsAllGoneWithoutWritingReceipt() throws Exception {
        Customer c = buyer(); Product p = product(); String id = row(c, p);
        Race r = beforeMove(c, () -> reply(delete("/api/me/cart"), c), id);
        assertEquals(40005, r.move().code());
        assertTrue(receipts.findByCustomerIdAndOperationTypeAndRequestKey(c.getId(),
                ReceiptOperationType.MOVE_TO_FAVORITES, r.key()).isEmpty());
        assertFalse(favorites.findByCustomerIdAndProductId(c.getId(), p.getId()).isPresent());
    }

    @Test void laterCancelWinsAndOriginalReceiptReplaysWithoutRecreatingFavorite() throws Exception {
        Customer c = buyer(); Product p = product(); String id = row(c, p);
        Race r = afterMove(c, () -> cancel(c, p), id);
        assertEquals(200, r.move().status()); assertEquals(200, r.other().status()); moved(c, id);
        assertFalse(favorites.findByCustomerIdAndProductId(c.getId(), p.getId()).isPresent());
        Reply replay = move(c, r.key(), id);
        assertEquals(200, replay.status()); assertEquals(r.move().data(), replay.data());
        assertEquals(r.move().body().path("message"), replay.body().path("message"));
        assertFalse(favorites.findByCustomerIdAndProductId(c.getId(), p.getId()).isPresent());
        assertEquals(2, mutations.findById(new FavoriteMutation.Key(c.getId(), p.getId())).orElseThrow().getOperationSeq());
        assertEquals(40005, move(c, UUID.randomUUID().toString(), id).code());
    }

    @Test void laterNewAddSurvivesOldMoveRetryAndGetsANewRowId() throws Exception {
        Customer c = buyer(); Product p = product(); String id = row(c, p);
        Race r = afterMove(c, () -> add(c, p), id);
        assertEquals(200, r.move().status()); assertEquals(200, r.other().status());
        String newId = r.other().data().path("cartItemId").asText(); assertNotEquals(id, newId);
        assertEquals(40915, move(c, r.key(), id).code());
        assertEquals(200, cancel(c, p).status());
        assertEquals(200, move(c, r.key(), id).status());
        assertEquals(BigInteger.ONE, cart.findById(Long.valueOf(newId)).orElseThrow().getQuantity());
        moved(c, id);
    }

    @Test void laterQuantityUpdateCannotResurrectTheRemovedRow() throws Exception {
        Customer c = buyer(); Product p = product(); String id = row(c, p);
        Race r = afterMove(c, () -> quantity(c, id, "8"), id);
        assertEquals(200, r.move().status()); assertEquals(40912, r.other().code());
        moved(c, id); assertTrue(cart.findByCustomerIdOrderByIdAsc(c.getId()).isEmpty());
    }

    @Test void existingFavoriteIsDeduplicatedAndItsOriginalTimestampIsKept() throws Exception {
        Customer c = buyer(); Product p = product(); String id = row(c, p);
        assertEquals(200, favorite(c, p).status());
        Favorite old = savedFavorite(c, p);
        Race r = afterMove(c, () -> favorite(c, p), id);
        assertEquals(200, r.move().status()); assertEquals(200, r.other().status());
        Favorite current = savedFavorite(c, p);
        assertEquals(old.getId(), current.getId()); assertEquals(old.getCreatedAt(), current.getCreatedAt());
        moved(c, id);
    }

    @Test void cancellationBeforeMoveDoesNotEnableTheSpecialReplayRule() throws Exception {
        Customer c = buyer(); Product p = product(); String id = row(c, p), key = UUID.randomUUID().toString();
        favorite(c, p); cancel(c, p);
        assertEquals(200, move(c, key, id).status());
        assertEquals(40915, move(c, key, id).code()); savedFavorite(c, p);
    }

    @Test void cancellationThenIndependentRefavoriteDoesNotLetOldRetryOverwriteNewFavorite() throws Exception {
        Customer c = buyer(); Product p = product(); String id = row(c, p), key = UUID.randomUUID().toString();
        assertEquals(200, move(c, key, id).status()); cancel(c, p); favorite(c, p);
        Favorite fresh = savedFavorite(c, p);
        assertEquals(200, move(c, key, id).status());
        assertEquals(fresh.getId(), savedFavorite(c, p).getId());
        assertEquals(fresh.getCreatedAt(), savedFavorite(c, p).getCreatedAt());
    }

    @Test void foreignDeletedRowRejectsWholeBatchBeforeProductDetailsAreExposed() throws Exception {
        Customer c = buyer(), other = buyer(); Product p = product(), q = product();
        String own = row(c, p), foreign = row(other, q); remove(other, foreign);
        tx.executeWithoutResult(s -> products.findByIdForUpdate(p.getId()).orElseThrow().takeOffline(BusinessTime.now()));
        Reply rejected = move(c, UUID.randomUUID().toString(), own, foreign);
        assertEquals(40302, rejected.code()); assertTrue(rejected.data().isNull());
        assertTrue(cart.existsById(Long.valueOf(own)));
        assertFalse(favorites.findByCustomerIdAndProductId(c.getId(), p.getId()).isPresent());
    }

    @Test void waitingForSellerProductLockRechecksOfflineStateAndRejectsWholeBatch() throws Exception {
        Customer c = buyer(); Product p = product(), q = product();
        String x = row(c, p), y = row(c, q), key = UUID.randomUUID().toString();
        favorite(c, q); Favorite existing = savedFavorite(c, q);
        CountDownLatch down = new CountDownLatch(1), release = new CountDownLatch(1), started = new CountDownLatch(1);
        ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            Future<?> seller = pool.submit(() -> tx.executeWithoutResult(s -> {
                products.findByIdForUpdate(q.getId()).orElseThrow().takeOffline(BusinessTime.now());
                products.flush(); down.countDown();
                try { await(release); } catch (InterruptedException e) { throw new CompletionException(e); }
            }));
            await(down);
            Future<Reply> moving = pool.submit(() -> { started.countDown(); return move(c, key, x, y); });
            await(started); assertThrows(TimeoutException.class, () -> moving.get(200, TimeUnit.MILLISECONDS));
            release.countDown(); seller.get(20, TimeUnit.SECONDS);
            Reply r = moving.get(20, TimeUnit.SECONDS);
            assertEquals(40914, r.code()); assertEquals(1, r.data().path("errors").size());
            assertEquals("OFFLINE", r.data().path("errors").get(0).path("reason").asText());
            assertEquals("商品已下架", r.data().path("errors").get(0).path("message").asText());
        } finally { release.countDown(); pool.shutdownNow(); }
        assertTrue(cart.existsById(Long.valueOf(x))); assertTrue(cart.existsById(Long.valueOf(y)));
        assertEquals(existing.getCreatedAt(), savedFavorite(c, q).getCreatedAt());
        assertFalse(favorites.findByCustomerIdAndProductId(c.getId(), p.getId()).isPresent());
        assertTrue(tombstones.findByCartItemId(Long.valueOf(x)).isEmpty());
        assertTrue(receipts.findByCustomerIdAndOperationTypeAndRequestKey(c.getId(),
                ReceiptOperationType.MOVE_TO_FAVORITES, key).isEmpty());
    }

    @Test void reversedSelectionsAcrossCustomersUseTheSameProductLockOrder() throws Exception {
        Customer a = buyer(), b = buyer(); Product p = product(), q = product();
        String ax = row(a, p), ay = row(a, q), bx = row(b, p), by = row(b, q);
        CountDownLatch start = new CountDownLatch(1); ExecutorService pool = Executors.newFixedThreadPool(2);
        try {
            Future<Reply> first = pool.submit(() -> { await(start); return move(a, UUID.randomUUID().toString(), ax, ay); });
            Future<Reply> second = pool.submit(() -> { await(start); return move(b, UUID.randomUUID().toString(), by, bx); });
            start.countDown();
            assertEquals(200, first.get(20, TimeUnit.SECONDS).status());
            assertEquals(200, second.get(20, TimeUnit.SECONDS).status());
        } finally { start.countDown(); pool.shutdownNow(); }
        moved(a, ax); moved(a, ay); moved(b, bx); moved(b, by);
        assertEquals(BigInteger.TWO, products.findById(p.getId()).orElseThrow().getStock());
        assertEquals(BigInteger.TWO, products.findById(q.getId()).orElseThrow().getStock());
    }

    enum FailurePoint { FAVORITE_WRITE, CART_DELETE, RECEIPT_AFTER_FLUSH }

    @ParameterizedTest @EnumSource(FailurePoint.class)
    void storageFailureRollsBackAllTablesAndSameKeyCanRetry(FailurePoint point) throws Exception {
        Customer c = buyer(); Product p = product(), q = product();
        String x = row(c, p), y = row(c, q), key = UUID.randomUUID().toString();
        favorite(c, q); Favorite old = savedFavorite(c, q);
        long oldSequence = mutations.findById(new FavoriteMutation.Key(c.getId(), q.getId())).orElseThrow().getOperationSeq();
        long orderCount = orders.count();
        switch (point) {
            case FAVORITE_WRITE -> doThrow(new PersistenceException("injected JPA failure"))
                    .when(favorites).saveAll(any());
            case CART_DELETE -> doThrow(new DataIntegrityViolationException("injected cart failure"))
                    .when(cart).deleteAll(any(Iterable.class));
            case RECEIPT_AFTER_FLUSH -> doThrow(new DataIntegrityViolationException("injected receipt failure"))
                    .when(receipts).saveAndFlush(any(OperationReceipt.class));
        }
        Reply failed = move(c, key, x, y);
        assertEquals(500, failed.status()); assertEquals(50001, failed.code());
        assertEquals("操作失败，请重试", failed.body().path("message").asText());
        assertTrue(cart.existsById(Long.valueOf(x))); assertTrue(cart.existsById(Long.valueOf(y)));
        assertFalse(favorites.findByCustomerIdAndProductId(c.getId(), p.getId()).isPresent());
        assertEquals(old.getId(), savedFavorite(c, q).getId());
        assertEquals(old.getCreatedAt(), savedFavorite(c, q).getCreatedAt());
        assertTrue(mutations.findById(new FavoriteMutation.Key(c.getId(), p.getId())).isEmpty());
        assertEquals(oldSequence, mutations.findById(new FavoriteMutation.Key(c.getId(), q.getId())).orElseThrow().getOperationSeq());
        assertTrue(tombstones.findByCartItemId(Long.valueOf(x)).isEmpty());
        assertTrue(tombstones.findByCartItemId(Long.valueOf(y)).isEmpty());
        assertTrue(receipts.findByCustomerIdAndOperationTypeAndRequestKey(c.getId(),
                ReceiptOperationType.MOVE_TO_FAVORITES, key).isEmpty());
        assertEquals(orderCount, orders.count());
        assertEquals(BigInteger.TWO, products.findById(p.getId()).orElseThrow().getStock());
        reset(favorites, cart, receipts);
        assertEquals(200, move(c, key, x, y).status()); moved(c, x); moved(c, y);
        assertEquals(40915, move(c, key, x, y).code());
    }
}
