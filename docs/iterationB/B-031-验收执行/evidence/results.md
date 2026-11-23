# B-031 21 AC 执行结果（统一单次执行）

- 执行窗口：`2026-11-20T11:10:37Z` → `2026-11-20T11:11:18Z`
- SUT：`develop@29c20ea0927528a98f873f4a1a0e169a6fa12281`
- DB：`oxstore_b031_local` · BE：`http://127.0.0.1:8080` · FE：`http://127.0.0.1:5173`
- PASS 20 / FAIL 1 / BLOCKED 0 / TOTAL 21

| AC | 结论 | 摘要 |
|---|---|---|
| PB-B08-AC1 | **PASS**（复判） | 原判因期望文案错误；实际「角色无权访问」/40301 符合「商家不可访问客户收藏」，B-037 复验通过 |
| PB-B08-AC2 | **PASS** | 符合预期 |
| PB-B08-AC3 | **PASS** | 符合预期 |
| PB-B08-AC4 | **PASS** | 符合预期 |
| PB-B08-AC5 | **PASS** | 符合预期 |
| PB-B09-AC1 | **FAIL**（D-002） | 期望强制详情 UI tip「已下架」，tipOfflineExact=0；「商品当前不可查看」(unavailableEmpty=1)/API「商品已下架」不能替代 |
| PB-B09-AC2 | **PASS** | 符合预期 |
| PB-B09-AC3 | **PASS** | 符合预期 |
| PB-B09-AC4 | **PASS** | 符合预期 |
| PB-B09-AC5 | **PASS** | 符合预期 |
| PB-B10-AC1 | **PASS** | 符合预期 |
| PB-B10-AC2 | **PASS** | 符合预期 |
| PB-B10-AC3 | **PASS** | 符合预期 |
| PB-B10-AC4 | **PASS** | 符合预期 |
| PB-B10-AC5 | **PASS** | 符合预期 |
| PB-B10-AC6 | **PASS** | 符合预期 |
| PB-B11-AC1 | **PASS** | 符合预期 |
| PB-B11-AC2 | **PASS** | 符合预期 |
| PB-B11-AC3 | **PASS** | 符合预期 |
| PB-B11-AC4 | **PASS** | 符合预期 |
| PB-B11-AC5 | **PASS** | 符合预期 |
