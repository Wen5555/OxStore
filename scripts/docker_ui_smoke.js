// Playwright CLI run-code template. The launcher replaces the marker with local settings.
// Uses real API responses; no route interception or mocked backend.
async (page) => {
  const config = __OXSTORE_UI_CONFIG__;
  await page.goto(config.url + '/admin/login');
  await page.getByLabel('账号').fill('admin');
  await page.getByLabel('密码').fill(config.password);
  await page.getByRole('button', { name: /登\s*录/ }).click();
  await page.waitForURL(config.url + '/admin');
  if (!config.continuePublished) {
    await page.goto(config.url + '/admin/products/publish');
    await page.getByLabel('商品名称').fill('Docker页面演示商品');
    await page.getByLabel('商品描述').fill('此商品通过真实Docker三容器和浏览器发布，用于课程交付演示。');
    await page.getByLabel('价格').fill('29.90');
    await page.locator('input[type=file]').setInputFiles(config.imageFile);
    await page.getByRole('button', { name: '发布商品', exact: true }).click();
    await page.getByText('商品发布成功', { exact: true }).waitFor();
  }
  await page.goto(config.url + '/admin/products/current');
  await page.getByText('Docker页面演示商品', { exact: true }).waitFor();
  await page.waitForTimeout(config.pauseMs || 0);
  await page.screenshot({ path: config.evidenceDir + '/01-current-product.png', fullPage: true });
  await page.goto(config.url + '/');
  await page.getByLabel('姓名').fill('容器演示买家');
  await page.getByLabel('手机号').fill('13800000009');
  await page.getByRole('button', { name: '提交购买意向', exact: true }).click();
  await page.getByText('购买意向提交成功', { exact: true }).first().waitFor();
  await page.waitForTimeout(config.pauseMs || 0);
  await page.screenshot({ path: config.evidenceDir + '/02-buyer-code.png', fullPage: true });
  const response = await page.request.get(config.url + '/api/products/current');
  const current = (await response.json()).data;
  if (!current || current.name !== 'Docker页面演示商品') throw new Error('Unexpected real current product');
  await page.goto(config.url + '/admin/intents');
  await page.getByRole('button', { name: '开始处理队首', exact: true }).click();
  await page.getByRole('button', { name: '确认成功', exact: true }).waitFor();
  await page.waitForTimeout(config.pauseMs || 0);
  await page.screenshot({ path: config.evidenceDir + '/03-in-transaction.png', fullPage: true });
  await page.getByRole('button', { name: '确认成功', exact: true }).click();
  await page.getByText('暂无排队意向', { exact: true }).waitFor();
  await page.goto(config.url + '/admin/products/' + current.id + '/records');
  await page.getByText('Docker页面演示商品', { exact: true }).waitFor();
  await page.waitForTimeout(config.pauseMs || 0);
  await page.screenshot({ path: config.evidenceDir + '/04-trade-history.png', fullPage: true });
  return { result: 'PASS', mocked_api: false, product_id: current.id,
           scope: 'seller login, product publish, buyer submit, current trade confirmation, complete records' };
}
