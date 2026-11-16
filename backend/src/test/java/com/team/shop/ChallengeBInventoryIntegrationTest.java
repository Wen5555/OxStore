package com.team.shop;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.team.shop.domain.BusinessTime;
import com.team.shop.entity.Product;
import com.team.shop.entity.Customer;
import com.team.shop.entity.PurchaseIntent;
import com.team.shop.repository.*;
import com.team.shop.security.JwtUtil;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.support.TransactionTemplate;

import java.math.BigInteger;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
        "shop.jwt.secret=inventory-integration-secret-0123456789abcdef",
        "shop.admin.initial-password=Inventory-Password8"
})
@AutoConfigureMockMvc
class ChallengeBInventoryIntegrationTest {
    @DynamicPropertySource static void database(DynamicPropertyRegistry properties) {
        boolean mysql = System.getProperty("challengeb.jdbc.url") != null;
        properties.add("spring.datasource.url", () -> System.getProperty("challengeb.jdbc.url", "jdbc:h2:mem:b006;MODE=MySQL;DB_CLOSE_DELAY=-1"));
        properties.add("spring.datasource.driver-class-name", () -> mysql ? "com.mysql.cj.jdbc.Driver" : "org.h2.Driver");
        properties.add("spring.datasource.username", () -> mysql ? "root" : "sa");
        properties.add("spring.datasource.password", () -> System.getProperty("challengeb.jdbc.password", ""));
        properties.add("spring.jpa.hibernate.ddl-auto", () -> mysql ? "none" : "create-drop");
    }
    @Autowired MockMvc mvc;
    @Autowired ObjectMapper json;
    @Autowired JwtUtil jwt;
    @Autowired ProductRepository products;
    @Autowired CategoryRepository categories;
    @Autowired CustomerRepository customers;
    @Autowired IntentRepository intents;
    @Autowired TransactionTemplate tx;

    private String seller() { return "Bearer " + jwt.generate(1L,"SELLER","admin"); }
    private long leaf() { return categories.findAll().stream().filter(c -> !c.isRoot()).findFirst().orElseThrow().getId(); }
    private JsonNode create(String stock) throws Exception {
        var response = mvc.perform(multipart("/api/admin/products").param("name","B006-"+System.nanoTime())
                        .param("price","12.50").param("stock",stock).param("category2Id",Long.toString(leaf()))
                        .header("Authorization",seller()))
                .andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
        return json.readTree(response).path("data");
    }
    private JsonNode update(long id, String stock) throws Exception {
        return json.readTree(mvc.perform(patch("/api/admin/products/"+id).header("Authorization",seller())
                        .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("stock",stock))))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString()).path("data");
    }

    @Test void hugeInventoryRoundTripsThroughHttpAndJpaWithoutImplicitRelisting() throws Exception {
        String huge = "900719925474099312345678901234567890";
        JsonNode product = create(huge);
        assertTrue(product.path("stock").isTextual());
        assertEquals(huge, product.path("stock").asText());
        long id = product.path("productId").asLong();
        assertEquals(new BigInteger(huge), products.findById(id).orElseThrow().getStock());
        assertEquals("OFFLINE",update(id,"0").path("status").asText());
        mvc.perform(get("/api/products/"+id)).andExpect(status().isNotFound());
        assertEquals("OFFLINE",update(id,huge).path("status").asText());
        mvc.perform(post("/api/admin/products/"+id+"/online").header("Authorization",seller()))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.stock").value(huge));
        mvc.perform(get("/api/products/"+id)).andExpect(status().isOk()).andExpect(jsonPath("$.data.stock").value(huge));
    }

    @Test void invalidInventoryAndImmutableFieldsRejectTheEntireWrite() throws Exception {
        long id = create("7").path("productId").asLong();
        for (String value : new String[]{"-1","1.2","1e3","01",""," 2","2\n"}) {
            mvc.perform(patch("/api/admin/products/"+id).header("Authorization",seller())
                            .contentType(MediaType.APPLICATION_JSON).content(json.writeValueAsString(Map.of("stock",value))))
                    .andExpect(status().isBadRequest()).andExpect(jsonPath("$.message").value("库存不能为负数，请输入非负整数。"));
        }
        for (String body : new String[]{"{\"stock\":2}","{\"stock\":1.5}","{\"stock\":null}"}) {
            mvc.perform(patch("/api/admin/products/"+id).header("Authorization",seller()).contentType(MediaType.APPLICATION_JSON).content(body))
                    .andExpect(status().isBadRequest()).andExpect(jsonPath("$.message").value("库存不能为负数，请输入非负整数。"));
        }
        mvc.perform(patch("/api/admin/products/"+id).header("Authorization",seller()).contentType(MediaType.APPLICATION_JSON)
                        .content("{\"stock\":\"0\",\"name\":\"changed\"}"))
                .andExpect(status().isBadRequest());
        assertEquals(BigInteger.valueOf(7), products.findById(id).orElseThrow().getStock());
    }

    @Test void domainCompensationPersistsAndManualOfflineDoesNotRecover() throws Exception {
        long auto = create("2").path("productId").asLong();
        tx.executeWithoutResult(s -> products.findByIdForUpdate(auto).orElseThrow().deductForOrder(BigInteger.TWO,BusinessTime.now()));
        assertEquals("AUTO_ZERO", products.findById(auto).orElseThrow().getOfflineReason().name());
        tx.executeWithoutResult(s -> products.findByIdForUpdate(auto).orElseThrow().restoreForCancelledOrder(BigInteger.TWO,BusinessTime.now()));
        assertEquals("ONLINE",products.findById(auto).orElseThrow().getStatus().name());
        mvc.perform(post("/api/admin/products/"+auto+"/offline").header("Authorization",seller())).andExpect(status().isOk());
        tx.executeWithoutResult(s -> products.findByIdForUpdate(auto).orElseThrow().restoreForCancelledOrder(BigInteger.TWO,BusinessTime.now()));
        Product after = products.findById(auto).orElseThrow();
        assertEquals("OFFLINE",after.getStatus().name()); assertEquals("MANUAL",after.getOfflineReason().name());
        assertEquals(BigInteger.valueOf(4),after.getStock());
    }

    @Test void maintenanceDoesNotRewriteOldIntentQueueOrInventFailureHistory() throws Exception {
        long id = create("3").path("productId").asLong();
        Long intentId = tx.execute(s -> {
            Customer c = customers.save(new Customer("b006-"+System.nanoTime(),"hash","13800000000",null,BusinessTime.now()));
            return intents.save(PurchaseIntent.submit(products.findById(id).orElseThrow(),c,1)).getId();
        });
        mvc.perform(post("/api/admin/products/"+id+"/offline").header("Authorization",seller())).andExpect(status().isOk());
        update(id,"0");
        assertEquals("QUEUING",intents.findById(intentId).orElseThrow().getStatus().name());
    }
}
