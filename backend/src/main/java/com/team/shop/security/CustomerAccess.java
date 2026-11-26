package com.team.shop.security;

import com.team.shop.exception.ApiBusinessException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import java.util.Collection;
import java.util.Objects;

/** Service-side guard: check every selected owner before any write. */
@Component
public class CustomerAccess {
    public Long requireCustomerId() {
        var authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !authentication.isAuthenticated()
                || !(authentication.getPrincipal() instanceof UserIdentity identity)) {
            throw new ApiBusinessException(401, 40101, "请先登录", null);
        }
        if (!"CUSTOMER".equals(identity.role())) throw new ApiBusinessException(403, 40301, "无此权限", null);
        return identity.userId();
    }
    public void requireOwner(Long ownerId) {
        requireOwners(java.util.Collections.singletonList(ownerId));
    }
    public void requireOwners(Collection<Long> ownerIds) {
        Long customerId = requireCustomerId();
        if (ownerIds.stream().anyMatch(id -> !Objects.equals(customerId, id)))
            throw new ApiBusinessException(403, 40302, "无权操作", null);
    }
    public void requireOrderOwner(Long ownerId) {
        if (!Objects.equals(requireCustomerId(), ownerId))
            throw new ApiBusinessException(403, 40302, "无权操作该订单", null);
    }
}
