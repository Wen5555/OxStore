# B-031 验收执行（收藏 / 购物车 · 21 AC）

独立于 B-030 材料树。仅本目录进入 B-031 分支提交。

```bash
cp fixtures/env.example runs/.env.local  # 填隔离库与密码
set -a; source runs/.env.local; set +a
python3 scripts/prepare_and_run.py
```

证据：`evidence/`（脱敏）。不开 PR；不改业务。
