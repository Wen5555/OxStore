#!/usr/bin/env python3
"""Real browser main-path: login → product → add cart → checkout → order success.

Uses Playwright Chromium against live FE (B030_FE_URL) proxied to BE.
Saves screenshots under review/browser/ (no JWT in artifacts).
Cross-checks API/DB after UI success.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b030_common import connect_mysql, load_env  # noqa: E402
from helpers_lib import load_fixtures, product_id  # noqa: E402
from redact import dumps_redacted  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review" / "browser"
# Prefer frontend's playwright package
FRONTEND = Path("/tmp/oxstore-develop/frontend")


def main() -> int:
    env = load_env()
    load_fixtures()
    subprocess.check_call(
        [sys.executable, str(ROOT / "scripts" / "reset_namespace.py"), "--case-id", "BROWSER-MAIN"],
        cwd=str(ROOT),
    )
    # re-align fixtures after reset
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "prepare_fixtures.py")], cwd=str(ROOT))
    load_fixtures()
    pid = product_id("P-ON-10")
    fe = env.get("B030_FE_URL", "http://127.0.0.1:5173").rstrip("/")
    OUT.mkdir(parents=True, exist_ok=True)

    # Run via node+playwright for reliable Chromium
    js = f'''
const {{ chromium }} = require({json.dumps(str(FRONTEND / "node_modules" / "playwright"))});
(async () => {{
  const browser = await chromium.launch({{ headless: true }});
  const page = await browser.newPage();
  const out = {json.dumps(str(OUT))};
  const fe = {json.dumps(fe)};
  const pid = {json.dumps(pid)};
  const shots = [];
  async function shot(name) {{
    const p = out + '/' + name + '.png';
    await page.screenshot({{ path: p, fullPage: true }});
    shots.push(name + '.png');
  }}
  try {{
    await page.goto(fe + '/login', {{ waitUntil: 'networkidle' }});
    await page.locator('#username').fill('b030_buyer_a');
    await page.locator('#password').fill('B030-BuyerA-Pass9');
    await page.getByRole('button', {{ name: /登\\s*录/ }}).click();
    await page.waitForURL(url => !String(url).includes('/login'), {{ timeout: 15000 }});
    await shot('01-after-login');

    await page.goto(fe + '/products/' + pid, {{ waitUntil: 'networkidle' }});
    await shot('02-product-detail');
    await page.getByRole('button', {{ name: /加入购物车/ }}).click();
    await page.waitForTimeout(1000);
    await shot('03-after-add-cart');

    await page.goto(fe + '/me/cart', {{ waitUntil: 'networkidle' }});
    await shot('04-cart');
    // Ensure at least one line selected (Ant Design checkbox)
    const summary = page.getByText(/已选\\s*\\d+\\s*件商品/);
    let selected = 0;
    if (await summary.count()) {{
      const t = await summary.first().innerText();
      const m = t.match(/已选\\s*(\\d+)\\s*件/);
      selected = m ? Number(m[1]) : 0;
    }}
    if (selected < 1) {{
      const boxes = page.locator('.ant-checkbox-input');
      const n = await boxes.count();
      for (let i = 0; i < n; i++) {{
        await boxes.nth(i).check({{ force: true }});
      }}
    }}
    await shot('04b-cart-selected');
    await page.getByRole('button', {{ name: /^下\\s*单$/ }}).click();
    // Prefer Ant Design modal wrapper
    const dialog = page.locator('.ant-modal').filter({{ hasText: '确认下单' }});
    await dialog.waitFor({{ state: 'visible', timeout: 15000 }});
    await dialog.getByText(/合计|金额|商品/).first().waitFor({{ timeout: 5000 }}).catch(() => {{}});
    await page.waitForTimeout(400);
    await shot('05-checkout-confirm-modal');
    await dialog.getByRole('button', {{ name: /确认下\\s*单/ }}).click();
    const successModal = page.locator('.ant-modal').filter({{ hasText: '下单成功' }});
    await successModal.waitFor({{ state: 'visible', timeout: 15000 }});
    await shot('06b-success-modal');
    await shot('06-after-submit');
    await page.goto(fe + '/me/order-history', {{ waitUntil: 'networkidle' }});
    await shot('07-order-history');
    const bodyText = await page.locator('body').innerText();
    const hasSuccess = bodyText.includes('下单成功') || bodyText.includes('PLACED') || /B030-在售/.test(bodyText) || /12\\.50/.test(bodyText);
    console.log(JSON.stringify({{ ok: true, shots, selectedBeforeOrder: selected, hasSuccessHint: hasSuccess, bodySnippet: bodyText.slice(0, 800) }}));
  }} catch (e) {{
    try {{ await shot('99-error'); }} catch (_) {{}}
    console.log(JSON.stringify({{ ok: false, error: String(e), shots }}));
    process.exitCode = 1;
  }} finally {{
    await browser.close();
  }}
}})();
'''
    # keep runner outside review/ to avoid committing temp js; write under runs/
    js_path = ROOT / "runs" / "_run_mainpath.js"
    js_path.parent.mkdir(parents=True, exist_ok=True)
    js_path.write_text(js, encoding="utf-8")
    p = subprocess.run(
        ["node", str(js_path)],
        cwd=str(FRONTEND),
        capture_output=True,
        text=True,
        timeout=180,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "NODE_PATH": str(FRONTEND / "node_modules")},
    )
    print(p.stdout[-2000:])
    print(p.stderr[-1000:], file=sys.stderr)
    try:
        ui = json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        ui = {"ok": False, "raw": p.stdout[-2000:], "stderr": p.stderr[-1000:]}

    # DB cross-check
    conn = connect_mysql(env)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT so.id, so.order_no, so.status, so.total_amount "
                "FROM shop_order so JOIN customer c ON c.id=so.customer_id "
                "WHERE c.username='b030_buyer_a' ORDER BY so.id DESC LIMIT 3"
            )
            orders = cur.fetchall()
            cur.execute(
                "SELECT stock, status FROM product WHERE id=%s",
                (pid,),
            )
            product = cur.fetchone()
            cur.execute(
                "SELECT COUNT(*) AS c FROM cart_item ci "
                "JOIN customer c ON c.id=ci.customer_id "
                "WHERE c.username='b030_buyer_a' AND ci.product_id=%s",
                (pid,),
            )
            cart_left = cur.fetchone()["c"]
    finally:
        conn.close()

    evidence = {
        "path": "login → product detail → add cart → cart checkout → order history",
        "fe": fe,
        "productId": pid,
        "sut_sha": env.get("B030_SUT_SHA"),
        "db": env.get("B030_DB_NAME"),
        "ui": ui,
        "db_after": {
            "orders": orders,
            "product": product,
            "cart_lines_for_product": cart_left,
        },
        "assertions": {
            "ui_ok": bool(ui.get("ok")),
            "has_placed_order": any(o["status"] == "PLACED" for o in orders),
            "stock_decremented": str(product["stock"]) == "9",  # started 10, bought 1
            "screenshots_present": any(OUT.glob("0*.png")),
        },
    }
    evidence["assertions"]["pass"] = all(
        [
            evidence["assertions"]["ui_ok"],
            evidence["assertions"]["has_placed_order"],
            evidence["assertions"]["stock_decremented"],
            evidence["assertions"]["screenshots_present"],
        ]
    )
    (OUT / "evidence.json").write_text(
        dumps_redacted(evidence, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    md = [
        "# 浏览器主路径联测证据",
        "",
        f"- FE：`{fe}` · SUT：`{env.get('B030_SUT_SHA')}` · DB：`{env.get('B030_DB_NAME')}`",
        f"- pass：`{evidence['assertions']['pass']}`",
        f"- UI ok：{evidence['assertions']['ui_ok']} · 有 PLACED 单：{evidence['assertions']['has_placed_order']} · stock→9：{evidence['assertions']['stock_decremented']}",
        "",
        "## 截图",
        "",
    ]
    for shot in sorted(OUT.glob("0*.png")):
        md.append(f"- `{shot.name}`")
        md.append(f"  ![{shot.name}](./{shot.name})")
    md.append("")
    (OUT / "README.md").write_text("\n".join(md), encoding="utf-8")
    # remove runner js from review (keep only evidence)
    try:
        js_path.unlink()
    except Exception:
        pass
    print(dumps_redacted({k: evidence[k] for k in ("assertions", "db_after", "productId")}, ensure_ascii=False, indent=2, default=str))
    return 0 if evidence["assertions"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
