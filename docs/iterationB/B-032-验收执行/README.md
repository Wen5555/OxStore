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
| `evidence/results.json` / `results.md` | 统一窗口 totals + 逐 AC |
| `evidence/cases/PB-B*.json` | 各 AC 脱敏明细 |
| `evidence/screenshots/` | 真实 Playwright 截图 |
| `evidence/verify-api-db.json` | API→隔离库证明 |
| `evidence/screenshots-index.json` | 截图索引 |

不开 PR；不改业务；不 force-push。
