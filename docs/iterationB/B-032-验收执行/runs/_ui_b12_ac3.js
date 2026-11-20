
const { chromium } = require('/tmp/oxstore-develop/frontend/node_modules/playwright');
(async () => {
  const fe = "http://127.0.0.1:5173";
  const out = {ok:false};
  const browser = await chromium.launch({headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:900}});
    await page.goto(fe + '/login', {waitUntil:'networkidle'});
    await page.locator('#username').fill('b032_buyer_a');
    await page.locator('#password').fill('B032-BuyerA-Pass9');
    await page.getByRole('button', { name: /登\s*录/ }).click();
    await page.waitForURL(u => !String(u).includes('/login'), {timeout:15000});
    await page.goto(fe + '/me/cart', {waitUntil:'networkidle'});
    await page.waitForTimeout(1200);
    const allLabel = await page.locator('text=全选可下单商品').count();
    const disabled = await page.locator('input[type=checkbox][disabled], .ant-checkbox-disabled').count();
    const invalidTag = await page.locator('text=已下架').count();
    const insufHint = await page.locator('text=当前库存').count();
    const checked = await page.locator('.ant-checkbox-checked').count();
    await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b12-cart-selection.png", fullPage:true});
    out.shots = ['b12-cart-selection.png'];
    out.ui = {allLabel, disabled, invalidTag, insufHint, checked};
    out.ok = allLabel > 0 && checked > 0;
  } catch(e) { out.error=String(e); }
  finally { await browser.close(); }
  console.log(JSON.stringify(out));
})();
