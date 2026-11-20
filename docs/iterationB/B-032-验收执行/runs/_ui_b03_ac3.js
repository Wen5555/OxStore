
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
    await page.goto(fe + '/me/order-history', {waitUntil:'networkidle'});
    await page.waitForTimeout(1000);
    const title = await page.locator('text=订单历史').first().isVisible().catch(()=>false);
    const empty = await page.locator('text=暂无订单').count();
    await page.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b03-order-history.png", fullPage:true});
    out.shots.push('b03-order-history.png');
    out.customer = {title, empty};

    const page2 = await browser.newPage({viewport:{width:1280,height:900}});
    await page2.goto(fe + '/admin/login', {waitUntil:'networkidle'});
    await page2.locator('#username').fill('admin');
    await page2.locator('#password').fill("B032-Seller-Pass9!");
    await page2.getByRole('button', { name: /登\s*录/ }).click();
    await page2.waitForURL(u => /\/admin(\/|$)/.test(String(u)) && !String(u).includes('/login'), {timeout:20000});
    await page2.goto(fe + '/admin/orders', {waitUntil:'networkidle'});
    await page2.waitForTimeout(1200);
    if (page2.url().includes('/login')) throw new Error('still on admin login: '+page2.url());
    const adminTitle = await page2.locator('text=订单管理').first().isVisible().catch(()=>false);
    await page2.screenshot({path: "/workspace/docs/iterationB/B-032-\u9a8c\u6536\u6267\u884c/evidence/screenshots/b03-admin-orders.png", fullPage:true});
    out.shots.push('b03-admin-orders.png');
    out.admin = {title: adminTitle, url: page2.url()};
    out.ok = title && empty === 0 && adminTitle && !page2.url().includes('/login');
  } catch(e) { out.error = String(e); }
  finally { await browser.close(); }
  console.log(JSON.stringify(out));
})();
