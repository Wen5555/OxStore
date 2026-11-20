# B-030 代表性演练日志

- 时间（UTC）：2026-11-20T07:37:33.402860+00:00
- 目的：验证交付物可执行性；**不**将业务 AC 标为通过

## 1. 静态自审

```
{
  "ac_count": 79,
  "case_count": 148,
  "errors": [],
  "warnings": [],
  "result": "PASS_STATIC_REVIEW",
  "note": "PASS_STATIC_REVIEW ≠ business acceptance. Unrun cases stay 待执行."
}

```

## 2. prepare --dry-check

```
DB OK: oxstore_b030_local
BASE: http://127.0.0.1:8080
SUT_SHA: (unset)
dry-check only; no API writes

```

## 3. reset --dry-run

```
Would execute namespace reset SQL on oxstore_b030_local case= DRY

-- Resolve B030 customers and products
SET @ns := 'B030';

DELETE oi FROM order_item oi
  JOIN shop_order so ON so.id = oi.order_id
  JOIN customer c ON c.id = so.customer_id
 WHERE c.username LIKE 'b030\_%';

DELETE so FROM shop_order so
  JOIN customer c ON c.id = so.customer_id
 WHERE c.username LIKE 'b030\_%';

DELETE ci FROM cart_item ci
  JOIN customer c ON c.id = ci.customer_id
 WHERE c.us ...

```

## 4. barrier_runner 烟测（echo，非业务）

```
wrote /workspace/docs/iterationB/B-030-本轮验收用例/runs/SEQ-01-simultaneous.json
{
  "A": {
    "returncode": 0,
    "stderr": "",
    "elapsed_ms": 51
  },
  "B": {
    "returncode": 0,
    "stderr": "",
    "elapsed_ms": 51
  }
}

```

## 5. 被测服务探测

- BASE `http://127.0.0.1:8080` GET / → reachable=False (<urlopen error [Errno 111] Connection refused>)
- POST path probe GET `/api/auth/login` → reachable=False (<urlopen error [Errno 111] Connection refused>)

**阻塞（如实）**：当前云代理环境未启动挑战 B 被测栈；代表性业务演练无法连真实接口。
已完成：静态自审、DB 名前置门禁演练、reset dry-run、栅栏烟测。
## 6. 代表性用例纸面走查（非业务通过）

- `PB-B01-AC1-POS`：已在 cases/ 含 HTTP/断言/清理；执行状态仍 **待执行**
- `PB-B13-AC1-POS`：已在 cases/ 含 HTTP/断言/清理；执行状态仍 **待执行**
- `PB-B13-AC1-NEG`：已在 cases/ 含 HTTP/断言/清理；执行状态仍 **待执行**
- `PB-B02-AC3-NEG`：已在 cases/ 含 HTTP/断言/清理；执行状态仍 **待执行**
- `PB-B13-AC5-CON`：已在 cases/ 含 HTTP/断言/清理；执行状态仍 **待执行**
- `PB-B08-AC1-POS`：已在 cases/ 含 HTTP/断言/清理；执行状态仍 **待执行**

## 结论

- 交付物可执行性：**脚本与用例入口可用**；**业务验收演练阻塞于缺少独立测试环境**。
- 不得将任何 AC 标为通过。

### blockers

- No live BE at http://127.0.0.1:8080. Cannot rehearse POS/NEG/UI/concurrency against real MySQL+BE+FE in this environment. Scripts and cases are ready; business execution blocked until independent test stack is up with oxstore_b030_* DB.

### evidence

- self_review exit=0
- prepare --dry-check exit=0
- reset --dry-run exit=0
- barrier smoke exit=0