package com.team.shop.security;

import com.team.shop.dto.ApiResponse;
import com.team.shop.exception.ApiBusinessException;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest(properties = {
        "spring.datasource.url=jdbc:h2:mem:b005;MODE=MySQL;DB_CLOSE_DELAY=-1",
        "spring.datasource.driver-class-name=org.h2.Driver", "spring.datasource.username=sa",
        "spring.datasource.password=", "spring.jpa.hibernate.ddl-auto=create-drop",
        "shop.jwt.secret=challenge-b-integration-secret-0123456789abcdef",
        "shop.admin.initial-password=ChallengeB-Password8"
})
@AutoConfigureMockMvc
@Import(ChallengeBSecurityIntegrationTest.Probes.class)
class ChallengeBSecurityIntegrationTest {
    private static final String SECRET = "challenge-b-integration-secret-0123456789abcdef";
    @Autowired MockMvc mvc;
    @Autowired JwtUtil jwt;
    @Autowired GuardProbe probe;

    @Test void distinguishesMissingExpiredAndMalformedCredentials() throws Exception {
        mvc.perform(get("/api/me/__b005")).andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("请先登录"));
        String expired = new JwtUtil(SECRET, -1000).generate(7L, "CUSTOMER", "buyer");
        for (String token : List.of(expired, "malformed")) {
            mvc.perform(get("/api/me/__b005").header("Authorization", "Bearer " + token))
                    .andExpect(status().isUnauthorized()).andExpect(jsonPath("$.code").value(40101))
                    .andExpect(jsonPath("$.message").value("请重新登录"));
        }
    }

    @Test void sellerCancellationAndCustomerPrivateEndpointsHaveCorrectRoleGuards() throws Exception {
        mvc.perform(post("/api/admin/orders/1/cancel")).andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("请先登录后台"));
        mvc.perform(post("/api/admin/orders/1/cancel").header("Authorization", "Bearer invalid"))
                .andExpect(status().isUnauthorized()).andExpect(jsonPath("$.message").value("请先登录后台"));
        String seller = jwt.generate(1L, "SELLER", "admin");
        for (String path : List.of("/api/me/favorites", "/api/me/cart", "/api/me/orders")) {
            mvc.perform(get(path).header("Authorization", "Bearer " + seller)).andExpect(status().isForbidden());
        }
        mvc.perform(post("/api/me/cart/move-to-favorites").header("Authorization", "Bearer " + seller))
                .andExpect(status().isForbidden()).andExpect(jsonPath("$.message").value("无此权限"));
        mvc.perform(get("/api/admin/products").header("Authorization", "Bearer " + jwt.generate(7L,"CUSTOMER","buyer")))
                .andExpect(status().isForbidden());
    }

    @Test void rejectsMixedOwnershipBeforeAnyWriteAndPreservesItemErrorData() throws Exception {
        String buyer = jwt.generate(7L, "CUSTOMER", "buyer");
        int before = probe.writes.get();
        mvc.perform(post("/api/me/__b005/batch").header("Authorization", "Bearer " + buyer)
                        .contentType(MediaType.APPLICATION_JSON).content("[7,8]"))
                .andExpect(status().isForbidden()).andExpect(jsonPath("$.code").value(40302))
                .andExpect(jsonPath("$.message").value("无权操作"));
        assertEquals(before, probe.writes.get());
        mvc.perform(get("/api/me/__b005/order/8").header("Authorization", "Bearer " + buyer))
                .andExpect(status().isForbidden()).andExpect(jsonPath("$.message").value("无权操作该订单"));
        mvc.perform(post("/api/me/__b005/batch").header("Authorization", "Bearer " + buyer)
                        .contentType(MediaType.APPLICATION_JSON).content("[7,7]"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.message").value("已更新"));
        mvc.perform(get("/api/me/__b005/errors").header("Authorization", "Bearer " + buyer))
                .andExpect(status().isConflict()).andExpect(jsonPath("$.code").value(40910))
                .andExpect(jsonPath("$.data.errors[0].reason").value("OFFLINE"));
    }

    @Test void preflightAllowsIdempotencyHeaderAndAnonymousBrowsingStillWorks() throws Exception {
        mvc.perform(options("/api/me/orders").header("Origin","http://localhost:5173")
                        .header("Access-Control-Request-Method","POST")
                        .header("Access-Control-Request-Headers","Authorization,Idempotency-Key,Content-Type"))
                .andExpect(status().isOk()).andExpect(header().exists("Access-Control-Allow-Headers"));
        mvc.perform(get("/api/products")).andExpect(status().isOk());
    }

    @TestConfiguration static class Probes {
        @Bean GuardProbe guardProbe(CustomerAccess access) { return new GuardProbe(access); }
    }

    /** Test-only routes exercise the real filter chain/advice without implementing future business tasks. */
    @RestController @RequestMapping("/api/me/__b005")
    static class GuardProbe {
        private final CustomerAccess access;
        final AtomicInteger writes = new AtomicInteger();
        GuardProbe(CustomerAccess access) { this.access = access; }
        @GetMapping ApiResponse<Long> identity() { return ApiResponse.ok(access.requireCustomerId()); }
        @PostMapping("/batch") ApiResponse<Integer> batch(@RequestBody List<Long> owners) {
            access.requireOwners(owners);
            return ApiResponse.ok("已更新", writes.incrementAndGet());
        }
        @GetMapping("/order/{owner}") ApiResponse<Void> order(@PathVariable Long owner) {
            access.requireOrderOwner(owner); return ApiResponse.ok(null);
        }
        @GetMapping("/errors") ApiResponse<Void> errors() {
            throw new ApiBusinessException(409,40910,"所选商品无法下单",
                    Map.of("errors",List.of(Map.of("reason","OFFLINE","message","商品已下架"))));
        }
    }
}
