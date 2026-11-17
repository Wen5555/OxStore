package com.team.shop;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.team.shop.domain.BusinessTime;
import com.team.shop.domain.OrderStatus;
import com.team.shop.entity.*;
import com.team.shop.repository.*;
import com.team.shop.security.JwtUtil;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.SpyBean;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.support.TransactionTemplate;

import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doThrow;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;

@SpringBootTest(properties = {
        "shop.jwt.secret=checkout-integration-secret-0123456789abcdef",
        "shop.admin.initial-password=Checkout-Password8"
})
@AutoConfigureMockMvc
class ChallengeBCheckoutIntegrationTest {
    @DynamicPropertySource static void database(DynamicPropertyRegistry p) {
        boolean mysql = System.getProperty("challengeb.jdbc.url") != null;
        p.add("spring.datasource.url", () -> System.getProperty("challengeb.jdbc.url","jdbc:h2:mem:b010_014;MODE=MySQL;DB_CLOSE_DELAY=-1"));
        p.add("spring.datasource.driver-class-name", () -> mysql ? "com.mysql.cj.jdbc.Driver" : "org.h2.Driver");
        p.add("spring.datasource.username", () -> mysql ? "root" : "sa");
        p.add("spring.datasource.password", () -> System.getProperty("challengeb.jdbc.password",""));
        p.add("spring.jpa.hibernate.ddl-auto", () -> mysql ? "none" : "create-drop");
    }
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JwtUtil jwt;
    @Autowired CustomerRepository customers;
    @Autowired ProductRepository products;
    @Autowired CategoryRepository categories;
    @Autowired CartItemTombstoneRepository tombstones;
    @Autowired CheckoutConfirmationRepository confirmations;
    @Autowired TransactionTemplate tx;
    @SpyBean ShopOrderRepository orders;
    @SpyBean OperationReceiptRepository receipts;
    @SpyBean CartItemRepository cart;

    record Reply(int status, JsonNode body) { JsonNode data() { return body.path("data"); } int code() { return body.path("code").asInt(); } }
    private Customer buyer() { return customers.saveAndFlush(new Customer("checkout-"+UUID.randomUUID(),"hash","13800000000",null,BusinessTime.now())); }
    private String token(Customer c) { return jwt.generate(c.getId(),"CUSTOMER",c.getUsername()); }
    private String seller() { return jwt.generate(1L,"SELLER","admin"); }
    private Product product(String stock, String price) {
        var category = categories.findAll().stream().filter(c -> !c.isRoot()).findFirst().orElseThrow();
        return products.saveAndFlush(Product.create("item-"+UUID.randomUUID(),"",new BigDecimal(price),new BigInteger(stock),category));
    }
    private Reply post(String path, Object body, String token, String key) throws Exception {
        var request = org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post(path)
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(body));
        if (token != null) request.header("Authorization","Bearer "+token);
        if (key != null) request.header("Idempotency-Key",key);
        var r=mvc.perform(request).andReturn().getResponse();
        return new Reply(r.getStatus(),json.readTree(r.getContentAsString(StandardCharsets.UTF_8)));
    }
    private String add(Customer c, Product p, String quantity) throws Exception {
        Reply added=post("/api/me/cart/items",Map.of("productId",p.getId().toString()),token(c),UUID.randomUUID().toString());
        assertEquals(200,added.status(),added.body().toString());
        String id=added.data().path("cartItemId").asText();
        change(c,id,quantity);
        return id;
    }
    private void change(Customer c,String id,String quantity) throws Exception {
        var r=mvc.perform(patch("/api/me/cart/items/"+id).header("Authorization","Bearer "+token(c))
                .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("quantity",quantity)))).andReturn().getResponse();
        assertEquals(200,r.getStatus(),r.getContentAsString());
    }
    private Reply confirmation(Customer c,String... ids) throws Exception {
        return post("/api/me/checkout/confirmations",Map.of("cartItemIds",List.of(ids)),token(c),null);
    }
    private String confirm(Customer c,String... ids) throws Exception {
        Reply r=confirmation(c,ids);assertEquals(200,r.status(),r.body().toString());return r.data().path("confirmationToken").asText();
    }
    private Reply submit(Customer c,String confirmation,String key) throws Exception {
        return post("/api/me/orders",Map.of("confirmationToken",confirmation),token(c),key);
    }
    private Reply advance(long id,String action,String expected) throws Exception {
        return post("/api/admin/orders/"+id+"/actions",Map.of("action",action,"expectedStatus",expected),seller(),null);
    }
    private Reply cancel(Customer c,long id,String expected,boolean asSeller) throws Exception {
        return post((asSeller?"/api/admin/orders/":"/api/me/orders/")+id+"/cancel",Map.of("expectedStatus",expected),asSeller?seller():token(c),null);
    }
    private BigInteger stock(Product p) { return products.findById(p.getId()).orElseThrow().getStock(); }
    private long placed(Customer c,Product p) throws Exception {
        String id=add(c,p,"1");Reply r=submit(c,confirm(c,id),UUID.randomUUID().toString());
        assertEquals(201,r.status(),r.body().toString());return r.data().path("orderId").asLong();
    }

    @Test void confirmationIsReadOnlyAndOnlySelectedRowsMatter() throws Exception {
        Customer c=buyer();Product p=product("5","0.01"),offline=product("0","2.00");
        String id=add(c,p,"3");
        // Seed an existing invalid row; it must not block a selected valid row.
        cart.saveAndFlush(new CartItem(c,offline,BigInteger.ONE,BusinessTime.now()));
        long count=orders.count();Reply r=confirmation(c,id,id);
        assertEquals(200,r.status());assertEquals(1,r.data().path("items").size());
        assertEquals("0.03",r.data().path("totalAmount").asText());
        assertEquals(BigInteger.valueOf(5),stock(p));assertEquals(count,orders.count());
        assertTrue(cart.findById(Long.valueOf(id)).isPresent());
    }

    @Test void emptyMixedOwnershipAndMultipleFailuresAreRejectedBeforeWrites() throws Exception {
        Customer c=buyer(),other=buyer();Product p=product("2","1.00"),q=product("5","2.00");
        String id=add(c,p,"3"),off=add(c,q,"1"),foreign=add(other,p,"1");
        tx.executeWithoutResult(s -> products.findByIdForUpdate(q.getId()).orElseThrow().takeOffline(BusinessTime.now()));
        assertEquals(40005,confirmation(c).code());
        assertEquals(40302,confirmation(c,id,"999999999",foreign).code());
        Reply failed=confirmation(c,id,off);
        assertEquals(40910,failed.code());assertEquals(2,failed.data().path("errors").size());
        assertEquals("INSUFFICIENT_STOCK",failed.data().path("errors").get(0).path("reason").asText());
        assertEquals("OFFLINE",failed.data().path("errors").get(1).path("reason").asText());
        assertEquals(BigInteger.TWO,stock(p));
        String otherToken=confirm(other,foreign);
        assertEquals(40302,submit(c,otherToken,UUID.randomUUID().toString()).code());
    }

    @Test void checkoutAtomicallyCreatesOneMultiItemOrderWithExactAmountsAndTombstones() throws Exception {
        Customer c=buyer();Product a=product("3","19.90"),b=product("8","2.35"),unselected=product("1","1.00");
        String x=add(c,a,"3"),y=add(c,b,"2"),z=add(c,unselected,"1");
        Reply r=submit(c,confirm(c,x,y),UUID.randomUUID().toString());
        assertEquals(201,r.status(),r.body().toString());assertEquals("PLACED",r.data().path("status").asText());
        assertEquals(2,r.data().path("items").size());assertEquals("64.40",r.data().path("totalAmount").asText());
        assertEquals(BigInteger.ZERO,stock(a));assertEquals(BigInteger.valueOf(6),stock(b));
        assertEquals("AUTO_ZERO",products.findById(a.getId()).orElseThrow().getOfflineReason().name());
        assertFalse(cart.findById(Long.valueOf(x)).isPresent());assertFalse(cart.findById(Long.valueOf(y)).isPresent());
        assertTrue(cart.findById(Long.valueOf(z)).isPresent());assertTrue(tombstones.findByCartItemId(Long.valueOf(x)).isPresent());
    }

    @Test void lockBeforeQuantityChangesRequiresNewConfirmationAndErrorsLeaveSelectionIntact() throws Exception {
        Customer c=buyer();Product p=product("8","1.00");String id=add(c,p,"1"),old=confirm(c,id);
        change(c,id,"2");long count=orders.count();
        assertEquals(40913,submit(c,old,UUID.randomUUID().toString()).code());
        assertEquals(count,orders.count());assertEquals(BigInteger.valueOf(8),stock(p));
        assertEquals(BigInteger.TWO,cart.findById(Long.valueOf(id)).orElseThrow().getQuantity());
        assertEquals(201,submit(c,confirm(c,id),UUID.randomUUID().toString()).status());
    }

    @Test void deletedAndOfflineSelectionsAreNotSilentlySkippedAndFailedKeyCanRetry() throws Exception {
        Customer c=buyer();Product p=product("2","1.00");String id=add(c,p,"1"),token=confirm(c,id),key=UUID.randomUUID().toString();
        tx.executeWithoutResult(s -> products.findByIdForUpdate(p.getId()).orElseThrow().takeOffline(BusinessTime.now()));
        assertEquals(40910,submit(c,token,key).code());assertTrue(cart.findById(Long.valueOf(id)).isPresent());
        tx.executeWithoutResult(s -> products.findByIdForUpdate(p.getId()).orElseThrow().putOnline(BusinessTime.now()));
        assertEquals(201,submit(c,token,key).status());
        assertEquals(40909,submit(c,token,key).code());
        // An unknown/removed selected row is a whole-operation failure.
        assertEquals(40910,confirmation(c,id).code());
    }

    @Test void sameRequestAndConfirmationCannotCreateSecondOrderButNewPurchaseCan() throws Exception {
        Customer c=buyer();Product p=product("5","1.00");String id=add(c,p,"1"),token=confirm(c,id),key=UUID.randomUUID().toString();
        Reply first=submit(c,token,key);assertEquals(201,first.status());
        Reply retry=submit(c,token,key);assertEquals(40909,retry.code());
        assertEquals(first.data().path("orderId").asText(),retry.data().path("orderId").asText());
        assertEquals(40909,submit(c,token,UUID.randomUUID().toString()).code());
        String newId=add(c,p,"1"),fresh=confirm(c,newId);
        assertEquals(40916,submit(c,fresh,key).code());
        assertEquals(201,submit(c,fresh,UUID.randomUUID().toString()).status());
        assertEquals(BigInteger.valueOf(3),stock(p));
    }

    @Test void duplicateConcurrentCheckoutHasExactlyOneWinner() throws Exception {
        Customer c=buyer();Product p=product("5","1.00");String t=confirm(c,add(c,p,"2")),key=UUID.randomUUID().toString();
        List<Reply> results=race(() -> submit(c,t,key),() -> submit(c,t,key));
        assertEquals(List.of(201,409),results.stream().map(Reply::status).sorted().toList());
        assertEquals(BigInteger.valueOf(3),stock(p));
    }

    @Test void twoBuyersCannotOversellEvenWithReversedMultiProductSelections() throws Exception {
        Customer a=buyer(),b=buyer();Product p=product("1","1.00"),q=product("1","2.00");
        String aToken=confirm(a,add(a,p,"1"),add(a,q,"1"));
        String bToken=confirm(b,add(b,q,"1"),add(b,p,"1"));long count=orders.count();
        List<Reply> results=race(() -> submit(a,aToken,UUID.randomUUID().toString()),() -> submit(b,bToken,UUID.randomUUID().toString()));
        assertEquals(List.of(201,409),results.stream().map(Reply::status).sorted().toList());
        assertEquals(count+1,orders.count());assertEquals(BigInteger.ZERO,stock(p));assertEquals(BigInteger.ZERO,stock(q));
        Customer loser=results.get(0).status()==201?b:a;
        assertEquals(2,cart.findByCustomerIdOrderByIdAsc(loser.getId()).size());
    }

    @Test void aCartAddWaitingBehindCheckoutSurvivesAsANewRow() throws Exception {
        Customer c=buyer();Product p=product("5","1.00");String id=add(c,p,"1"),t=confirm(c,id);
        CountDownLatch stockWritten=new CountDownLatch(1),release=new CountDownLatch(1),addStarted=new CountDownLatch(1);
        org.mockito.Mockito.doAnswer(invocation -> {
            if (((OperationReceipt)invocation.getArgument(0)).getOperationType()==com.team.shop.domain.ReceiptOperationType.CHECKOUT) {
                stockWritten.countDown();if (!release.await(10,TimeUnit.SECONDS)) throw new IllegalStateException("release timed out");
            }
            OperationReceipt saved = receipts.save(invocation.getArgument(0));
            receipts.flush();
            return saved;
        }).when(receipts).saveAndFlush(any(OperationReceipt.class));
        ExecutorService pool=Executors.newFixedThreadPool(2);
        try {
            Future<Reply> checkout=pool.submit(() -> submit(c,t,UUID.randomUUID().toString()));
            assertTrue(stockWritten.await(10,TimeUnit.SECONDS));
            Future<String> newRow=pool.submit(() -> {addStarted.countDown();return add(c,p,"2");});
            assertTrue(addStarted.await(5,TimeUnit.SECONDS));
            assertThrows(TimeoutException.class,() -> newRow.get(200,TimeUnit.MILLISECONDS));
            release.countDown();assertEquals(201,checkout.get(15,TimeUnit.SECONDS).status());
            String newId=newRow.get(15,TimeUnit.SECONDS);assertNotEquals(id,newId);
            assertEquals(BigInteger.TWO,cart.findById(Long.valueOf(newId)).orElseThrow().getQuantity());
        } finally {release.countDown();pool.shutdownNow();}
    }

    @Test void failureCreatingOrderRollsBackEverything() throws Exception { fault(0); }
    @Test void failureRemovingCartRollsBackOrderAndStock() throws Exception { fault(1); }
    @Test void failureRecordingReceiptRollsBackAlreadyFlushedBusinessWrites() throws Exception { fault(2); }
    private void fault(int stage) throws Exception {
        Customer c=buyer();Product p=product("2","1.00");String id=add(c,p,"1"),t=confirm(c,id);long count=orders.count();
        if(stage==0)doThrow(new IllegalStateException("injected order failure")).when(orders).saveAndFlush(any(ShopOrder.class));
        if(stage==1)doThrow(new IllegalStateException("injected cart failure")).when(cart).delete(any(CartItem.class));
        if(stage==2)doThrow(new IllegalStateException("injected receipt failure")).when(receipts).saveAndFlush(any(OperationReceipt.class));
        Reply r=submit(c,t,UUID.randomUUID().toString());assertEquals(500,r.status());
        assertEquals(count,orders.count());assertEquals(BigInteger.TWO,stock(p));
        assertTrue(cart.findById(Long.valueOf(id)).isPresent());assertTrue(tombstones.findByCartItemId(Long.valueOf(id)).isEmpty());
    }

    @Test void fullFiveStateFlowDoesNotRecheckOrDeductInventoryAtCompletion() throws Exception {
        Customer c=buyer();Product p=product("1","1.00");long id=placed(c,p);
        assertEquals(40911,advance(id,"SHIP","PLACED").code());
        assertEquals(200,advance(id,"CONFIRM","PLACED").status());
        assertEquals(40904,advance(id,"CONFIRM","PLACED").code());
        assertEquals(200,advance(id,"PREPARE","CONFIRMED").status());
        assertEquals(200,advance(id,"SHIP","PREPARED").status());
        assertEquals(40911,cancel(c,id,"SHIPPED",false).code());
        Reply completed=advance(id,"COMPLETE","SHIPPED");assertEquals(200,completed.status());
        assertEquals("COMPLETED",completed.data().path("status").asText());assertEquals(BigInteger.ZERO,stock(p));
        assertEquals(40911,cancel(c,id,"COMPLETED",true).code());
        assertEquals(40911,advance(id,"COMPLETE","SHIPPED").code());
        assertEquals(40405,advance(Long.MAX_VALUE,"CONFIRM","PLACED").code());
        assertEquals(40405,cancel(c,Long.MAX_VALUE,"PLACED",false).code());
        Reply denied=post("/api/admin/orders/"+id+"/actions",Map.of("action","COMPLETE","expectedStatus","SHIPPED"),token(c),null);
        assertEquals(403,denied.status());
    }

    @Test void realCheckoutCancellationUsesSnapshotOnceAndDoesNotReturnItemsToCart() throws Exception {
        Customer c=buyer();Product p=product("2","1.00");String row=add(c,p,"2");
        long id=submit(c,confirm(c,row),UUID.randomUUID().toString()).data().path("orderId").asLong();
        assertEquals(200,cancel(c,id,"PLACED",false).status());assertEquals(BigInteger.TWO,stock(p));
        assertEquals(40911,cancel(c,id,"CANCELLED",true).code());assertEquals(BigInteger.TWO,stock(p));
        assertTrue(cart.findByCustomerIdOrderByIdAsc(c.getId()).isEmpty());
    }

    @Test void customerCancelAndShippingRaceProducesOneLegalFinalState() throws Exception { transitionRace(false); }
    @Test void sellerCancelAndCompletionRaceProducesOneLegalFinalState() throws Exception { transitionRace(true); }
    @Test void hugeQuantityAndAmountRemainExactThroughCheckout() throws Exception {
        Customer c=buyer();String huge="90071992547409931234567890";Product p=product(huge,"0.01");
        String row=add(c,p,huge);Reply r=submit(c,confirm(c,row),UUID.randomUUID().toString());
        assertEquals(201,r.status(),r.body().toString());
        assertEquals(huge,r.data().path("items").get(0).path("quantity").asText());
        assertEquals(new BigDecimal(new BigInteger(huge),2).toPlainString(),r.data().path("totalAmount").asText());
        assertEquals(BigInteger.ZERO,stock(p));
    }
    @Test void bothPartiesCancellingConcurrentlyCompensateOnlyOnce() throws Exception {
        Customer c=buyer();Product p=product("1","1.00");long id=placed(c,p);
        List<Reply> r=race(() -> cancel(c,id,"PLACED",false),() -> cancel(c,id,"PLACED",true));
        assertEquals(List.of(200,409),r.stream().map(Reply::status).sorted().toList());
        assertEquals(BigInteger.ONE,stock(p));assertEquals(OrderStatus.CANCELLED,orders.findById(id).orElseThrow().getStatus());
    }
    @Test void confirmationWinningBeforeCancellationStillAllowsANewValidCancel() throws Exception {
        Customer c=buyer();Product p=product("1","1.00");long id=placed(c,p);
        assertEquals(200,advance(id,"CONFIRM","PLACED").status());
        assertEquals(40904,cancel(c,id,"PLACED",false).code());
        assertEquals(200,cancel(c,id,"CONFIRMED",false).status());assertEquals(BigInteger.ONE,stock(p));
    }
    private void transitionRace(boolean completion) throws Exception {
        Customer c=buyer();Product p=product("1","1.00");long id=placed(c,p);
        assertEquals(200,advance(id,"CONFIRM","PLACED").status());assertEquals(200,advance(id,"PREPARE","CONFIRMED").status());
        if(completion)assertEquals(200,advance(id,"SHIP","PREPARED").status());
        String expected=completion?"SHIPPED":"PREPARED";
        List<Reply> r=race(() -> cancel(c,id,expected,completion),() -> advance(id,completion?"COMPLETE":"SHIP",expected));
        assertEquals(List.of(200,409),r.stream().map(Reply::status).sorted().toList());
        OrderStatus actual=orders.findById(id).orElseThrow().getStatus();
        assertTrue(actual==OrderStatus.CANCELLED||actual==(completion?OrderStatus.COMPLETED:OrderStatus.SHIPPED));
        assertEquals(actual==OrderStatus.CANCELLED?BigInteger.ONE:BigInteger.ZERO,stock(p));
    }

    private List<Reply> race(Callable<Reply> a,Callable<Reply> b) throws Exception {
        ExecutorService pool=Executors.newFixedThreadPool(2);CountDownLatch ready=new CountDownLatch(2),go=new CountDownLatch(1);
        try {
            List<Future<Reply>> futures=new ArrayList<>();
            for(Callable<Reply> task:List.of(a,b))futures.add(pool.submit(() -> {ready.countDown();if(!go.await(5,TimeUnit.SECONDS))throw new IllegalStateException("race timed out");return task.call();}));
            assertTrue(ready.await(5,TimeUnit.SECONDS));go.countDown();
            return List.of(futures.get(0).get(20,TimeUnit.SECONDS),futures.get(1).get(20,TimeUnit.SECONDS));
        } finally {go.countDown();pool.shutdownNow();}
    }
}
