package com.team.shop.security;

import java.security.Principal;

public record UserIdentity(Long userId, String username, String role) implements Principal {
    @Override
    public String getName() {
        return username;
    }
}
