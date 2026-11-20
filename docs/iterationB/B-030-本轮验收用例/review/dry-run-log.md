# B-030 代表性真实演练日志

- UTC：2026-11-20T08:02:36.346877+00:00
- BASE：http://127.0.0.1:8080
- SUT_SHA：29c20ea0927528a98f873f4a1a0e169a6fa12281
- DB：oxstore_b030_local
- 声明：本日志证明脚本/接口可跑；**不**将业务 AC 标为通过

## 0. self_review
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

## 1. verify_api_db
```
{
  "configured_db": "oxstore_b030_local",
  "connection_database": "oxstore_b030_local",
  "api_product_id": "9",
  "api_product_name": "B030-CANARY-e051ea23",
  "row_in_db": {
    "id": 9,
    "name": "B030-CANARY-e051ea23"
  },
  "ok": true,
  "sut_sha": "29c20ea0927528a98f873f4a1a0e169a6fa12281",
  "base_url": "http://127.0.0.1:8080",
  "ts": 1795161756.5992568
}

```

## 2. place_order POS
- http=201 message=下单成功 orderId=3

## 3. oversell NEG (qty5 vs stock1)
- http=409 message=所选商品无法下单 expected_reject=True

## 4. SEQ-01 simultaneous real curl
```
wrote /workspace/docs/iterationB/B-030-本轮验收用例/runs/SEQ-01-simultaneous.json
{
  "B": {
    "returncode": 0,
    "stderr": "",
    "elapsed_ms": 20
  },
  "A": {
    "returncode": 0,
    "stderr": "",
    "elapsed_ms": 23
  }
}

```

## 5. favorite_then_offline
```
{
  "ok": true,
  "helper": "favorite_then_offline",
  "result": {
    "tokenA": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJiMDMwX2J1eWVyX2EiLCJ1c2VySWQiOjEsInJvbGUiOiJDVVNUT01FUiIsImlhdCI6MTc5NTE2MTc1NywiZXhwIjoxNzk1MTY4OTU3fQ.BhTZ37OiybrO92ShqKSCrPFUf5v2Oy2oEN8PrmtVcBM",
    "tokenS": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsInVzZXJJZCI6MSwicm9sZSI6IlNFTExFUiIsImlhdCI6MTc5NTE2MTc1NywiZXhwIjoxNzk1MTY4OTU3fQ.ktfXT8qixwlbp0RPqfRmJVKg9BmLb1kpciEaYP2F3vM",
    "productId": "1"
  }
}

```

## 结论

- 已对 develop 候选做真实 API+DB 演练（见上）。
- **未**将任何 AC 标记为通过；用例状态仍为待执行。
- 若单项 FAIL，见 results JSON。
