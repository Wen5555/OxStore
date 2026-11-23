# B-031 验收执行（收藏 / 购物车 · 21 AC）

独立于 B-030 材料树。仅本目录进入 B-031 分支提交。

```bash
cp fixtures/env.example runs/.env.local  # 填隔离库与密码
set -a; source runs/.env.local; set +a
python3 scripts/prepare_and_run.py
```

证据：`evidence/`（脱敏）。不开 PR；不改业务。

## 修正记录（2026-11-22，R2）

- PB-B08-AC1 由 FAIL 改判 **PASS**：原脚本期望商家「无此权限」，实际「角色无权访问」(40301)；AC 只要求商家不可访问客户收藏，B-037 已 5/5 复验。原始 FAIL 观察保留在 `results.json`。
- PB-B09-AC1 维持 **FAIL**：失效收藏点击无「已下架」提示，已在 `develop@29c20ea` 真实浏览器复现，记为 D-002（R3/B-019）。
- 当前合计：**20 PASS / 1 FAIL**。详见 `evidence/corrections.md`。
