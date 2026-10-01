package com.team.shop.config;

import com.team.shop.entity.Seller;
import com.team.shop.repository.SellerRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/** 仅在数据库没有 admin 时初始化；后续启动绝不重置密码。 */
@Component
public class DataInitializer implements CommandLineRunner {
    private static final Logger log = LoggerFactory.getLogger(DataInitializer.class);
    private static final String USERNAME = "admin";
    private final SellerRepository sellers;
    private final PasswordEncoder encoder;
    private final String initialPassword;
    public DataInitializer(SellerRepository sellers, PasswordEncoder encoder,
                           @Value("${shop.admin.initial-password:}") String initialPassword) {
        this.sellers = sellers;
        this.encoder = encoder;
        this.initialPassword = initialPassword;
    }
    @Override
    public void run(String... args) {
        if (sellers.findByUsername(USERNAME).isPresent()) return;
        if (initialPassword == null || initialPassword.length() < 8 || initialPassword.length() > 64
                || !initialPassword.matches("(?s).*[A-Za-z].*")
                || !initialPassword.matches("(?s).*\\d.*")
                || !initialPassword.matches("(?s).*[\\W_].*")
                || "Admin@123".equals(initialPassword)) {
            throw new IllegalStateException("首次建卖家账号必须提供符合改密强度的 ADMIN_INITIAL_PASSWORD（不可用旧公开密码）");
        }
        sellers.save(new Seller(USERNAME, encoder.encode(initialPassword)));
        log.info("已初始化卖家账号：{}", USERNAME);
    }
}
