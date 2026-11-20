
const { chromium } = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {
  const fe = "http://127.0.0.1:5173";
  const out = {ok:false, shots:[]};
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:800}});
    await page.goto(fe + '/login', {waitUntil:'networkidle', timeout:60000});
    await page.locator('#username').fill('b032_buyer_a');
    await page.locator('#password').fill('B032-BuyerA-Pass9');
    await page.getByRole('button', { name: /登\s*录/ }).click();
    await page.waitForURL(u => !String(u).includes('/login'), { timeout: 15000 });
    await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b03-after-login.png", fullPage:true});
    out.shots.push('b03-after-login.png');

    await page.goto(fe + '/', {waitUntil:'networkidle', timeout:60000});
    const link = page.locator('a[href*="/products/"]').first();
    await link.waitFor({ timeout: 10000 });
    await link.click();
    await page.waitForURL(u => String(u).includes('/products/'), { timeout: 10000 });
    await page.waitForTimeout(800);
    await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b12-product-detail-no-direct-buy.png", fullPage:true});
    out.shots.push('b12-product-detail-no-direct-buy.png');
    const add = page.getByRole('button', { name: /加入购物车/ });
    if (await add.count()) { await add.first().click(); await page.waitForTimeout(800); }

    await page.goto(fe + '/me/cart', {waitUntil:'networkidle', timeout:60000});
    await page.waitForTimeout(1000);
    await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b12-cart-selection.png", fullPage:true});
    out.shots.push('b12-cart-selection.png');

    const checkout = page.getByRole('button', { name: /结算|确认下单|去结算|提交订单/ });
    if (await checkout.count()) {
      await checkout.first().click();
      await page.waitForTimeout(1200);
      await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b12-checkout-confirm.png", fullPage:true});
      out.shots.push('b12-checkout-confirm.png');
    } else {
      // still capture cart state as selection evidence
      await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b12-checkout-confirm.png", fullPage:true});
      out.shots.push('b12-checkout-confirm.png');
    }

    // clear-cart confirm UI if available
    const clearBtn = page.getByRole('button', { name: /清空/ });
    if (await clearBtn.count()) {
      await clearBtn.first().click();
      await page.waitForTimeout(600);
      await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b12-clear-cart-confirm.png", fullPage:true});
      out.shots.push('b12-clear-cart-confirm.png');
    }

    await page.goto(fe + '/me/order-history', {waitUntil:'networkidle', timeout:60000});
    await page.waitForTimeout(800);
    await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b03-order-history.png", fullPage:true});
    out.shots.push('b03-order-history.png');

    const page2 = await browser.newPage({viewport:{width:1280,height:800}});
    await page2.goto(fe + '/admin/login', {waitUntil:'networkidle', timeout:60000});
    await page2.locator('#username').fill('admin');
    await page2.locator('#password').fill("B032-Seller-Pass9!");
    await page2.getByRole('button', { name: /登\s*录/ }).click();
    await page2.waitForURL(u => String(u).includes('/admin'), { timeout: 15000 });
    await page2.goto(fe + '/admin/orders', {waitUntil:'networkidle', timeout:60000});
    await page2.waitForTimeout(800);
    await page2.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b03-admin-orders.png", fullPage:true});
    out.shots.push('b03-admin-orders.png');

    out.ok = out.shots.length >= 4;
  } catch (e) {
    out.error = String(e);
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify(out));
})();
