# B-032 验收执行（结算原子性 / 确认变化 / 并发 · 26 AC）

独立于 B-030/B-031 材料树。仅本目录进入 B-032 分支提交。

## 范围

- PB-B01（5）、PB-B02（5）、PB-B03（5）、PB-B12（6）、PB-B13（5）= **26 AC**
- 真栈：MySQL `oxstore_b032_*` + BE `:8080` + FE `:5173`
- 被测：`develop@29c20ea`（与交付分支 tip 分离）
- 事务三断点：隔离库 test-only 控制表 `b032_tx_control` + MyISAM 探针 `b032_tx_probe`（不改业务代码）

## 一次加载

```bash
cp fixtures/env.example runs/.env.local  # 填隔离库与密码
set -a; source runs/.env.local; set +a
python3 scripts/prepare_and_run.py
```

## 证据

| 路径 | 说明 |
|---|---|
| `evidence/results.json` / `results.md` | 统一窗口 totals + **逐合取表** |
| `evidence/cases/PB-B*.json` | 各 AC 脱敏明细（含 conjuncts） |
| `evidence/screenshots/` | 真实 Playwright 截图（见同目录 README 映射） |
| `evidence/verify-api-db.json` | 进程→checkout SHA→隔离库绑定（非仅 env） |
| `evidence/screenshots-index.json` | 截图索引 |
| `fixtures/b032_tx_probes.sql` | TX 三断点探针 |
| `fixtures/V8__close_legacy_fixed_price_intents.sql` | PB-B03-AC5 真迁移路径 |

第二次审计：`scripts/second_audit_acs.py` + `conjuncts.py`。禁止 `or True` / 写死 PASS。PB-B03-AC5 走 V8 `CALL upgrade_oxstore_v8()`，不用假 close API。

不开 PR；不改业务；不 force-push。
