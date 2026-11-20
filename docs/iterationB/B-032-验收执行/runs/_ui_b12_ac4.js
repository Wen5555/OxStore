
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
    await page.waitForTimeout(800);
    await page.getByRole('button', { name: '下单' }).click();
    const modal = page.locator('.ant-modal').filter({ hasText: '确认下单' });
    await modal.waitFor({ state: 'visible', timeout: 10000 });
    await page.waitForTimeout(400);
    const hasTotal = await modal.locator('text=总金额').count();
    const hasUnit = await modal.locator('text=¥').count();
    const bodyText = await modal.innerText();
    await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b12-checkout-confirm.png", fullPage:true});
    out.shots = ['b12-checkout-confirm.png'];
    out.ui = {hasTotal, hasUnit, bodyText: bodyText.slice(0, 400), url: page.url()};
    out.ok = hasTotal > 0 && hasUnit > 0 && bodyText.includes('确认下单');
  } catch(e) { out.error=String(e); }
  finally { await browser.close(); }
  console.log(JSON.stringify(out));
})();
