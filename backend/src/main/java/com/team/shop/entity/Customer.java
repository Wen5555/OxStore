package com.team.shop.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.LocalDateTime;

@Entity
@Table(name = "customer")
public class Customer {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 50)
    private String username;

    @Column(name = "password_hash", nullable = false, length = 255)
    private String passwordHash;

    @Column(nullable = false, length = 20)
    private String phone;

    @Column(length = 200)
    private String location;

    @Column(name = "registered_at", nullable = false)
    private LocalDateTime registeredAt;

    protected Customer() {
    }

    public Customer(String username, String passwordHash, String phone, String location, LocalDateTime registeredAt) {
        this.username = username;
        this.passwordHash = passwordHash;
        this.phone = phone;
        this.location = location;
        this.registeredAt = registeredAt;
    }

    public Long getId() { return id; }
    public String getUsername() { return username; }
    public String getPasswordHash() { return passwordHash; }
    public String getPhone() { return phone; }
    public String getLocation() { return location; }
    public LocalDateTime getRegisteredAt() { return registeredAt; }
}
