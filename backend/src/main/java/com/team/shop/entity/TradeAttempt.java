package com.team.shop.entity;
import com.team.shop.domain.TradeResult;
import com.team.shop.dto.request.FailAction;
import jakarta.persistence.*;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import java.time.LocalDateTime;
@Entity
@Table(name = "trade_attempt")
public class TradeAttempt {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "intent_id", nullable = false)
    private PurchaseIntent intent;
    @Column(name = "started_at", nullable = false)
    private LocalDateTime startedAt;
    @Column(name = "finished_at")
    private LocalDateTime finishedAt;
    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR) @Column(length = 10)
    private TradeResult result;
    @Enumerated(EnumType.STRING) @JdbcTypeCode(SqlTypes.VARCHAR) @Column(name = "fail_action", length = 10)
    private FailAction failAction;
    protected TradeAttempt() { }
    public TradeAttempt(PurchaseIntent intent, LocalDateTime now) {
        this.intent = intent; this.startedAt = now;
    }
    public void succeed(LocalDateTime now) {
        if (finishedAt != null) throw new IllegalStateException("交易尝试已结束");
        finishedAt = now; result = TradeResult.SUCCESS;
    }
    public void fail(FailAction action, LocalDateTime now) {
        if (finishedAt != null || action == null) throw new IllegalStateException("交易尝试已结束或缺少处理动作");
        finishedAt = now; result = TradeResult.FAILED; failAction = action;
    }
    public Long getId() { return id; }
    public PurchaseIntent getIntent() { return intent; }
    public LocalDateTime getStartedAt() { return startedAt; }
    public LocalDateTime getFinishedAt() { return finishedAt; }
    public TradeResult getResult() { return result; }
    public FailAction getFailAction() { return failAction; }
}
