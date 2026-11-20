
const { chromium } = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {
  const fe = "http://127.0.0.1:5173";
  const out = {ok:false, shots:[]};
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:900}});
    await page.goto(fe + '/login', {waitUntil:'networkidle'});
    await page.locator('#username').fill('b032_buyer_a');
    await page.locator('#password').fill('B032-BuyerA-Pass9');
    await page.getByRole('button', { name: /登\s*录/ }).click();
    await page.waitForURL(u => !String(u).includes('/login'), {timeout:15000});
    await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b03-after-login.png", fullPage:true});
    out.shots.push('b03-after-login.png');

    const pid = "25";
    await page.goto(fe + '/products/' + pid, {waitUntil:'networkidle'});
    await page.waitForTimeout(800);
    const directBuy = await page.getByRole('button', { name: /立即购买|直接下单/ }).count();
    const addCart = await page.getByRole('button', { name: /加入购物车/ }).count();
    await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b12-product-detail-no-direct-buy.png", fullPage:true});
    out.shots.push('b12-product-detail-no-direct-buy.png');
    out.detail = {directBuy, addCart};

    await page.goto(fe + '/me/cart', {waitUntil:'networkidle'});
    await page.waitForTimeout(600);
    await page.getByRole('button', { name: /清空购物车/ }).click();
    const clearModal = page.locator('.ant-modal').filter({ hasText: '确定清空购物车' });
    await clearModal.waitFor({ state: 'visible', timeout: 10000 });
    await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b12-clear-cart-confirm.png", fullPage:true});
    out.shots.push('b12-clear-cart-confirm.png');

    // verify required shots exist and confirm≠cart
    const fs = require('fs');
    const crypto = require('crypto');
    const hash = (f) => crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
    const cart = "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b12-cart-selection.png";
    const conf = "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b12-checkout-confirm.png";
    const hist = "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b03-order-history.png";
    const adm = "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b03-admin-orders.png";
    out.required = {
      cart: fs.existsSync(cart),
      confirm: fs.existsSync(conf),
      history: fs.existsSync(hist),
      admin: fs.existsSync(adm),
      cart_confirm_distinct: fs.existsSync(cart) && fs.existsSync(conf) && hash(cart) !== hash(conf),
    };
    out.ok = out.required.cart && out.required.confirm && out.required.history && out.required.admin && out.required.cart_confirm_distinct && directBuy === 0 && addCart > 0;
  } catch(e) { out.error = String(e); }
  finally { await browser.close(); }
  console.log(JSON.stringify(out));
})();
