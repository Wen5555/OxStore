import { expect, test } from '@playwright/test'

test('库存按原始十进制字符串提交，非法小数不被自动四舍五入', async ({ page }) => {
  const huge = '900719925474099312345678901234567890'
  const item = {
    productId: 41, name: '大整数库存', price: 1, stock: huge,
    category2Id: 2, category2Name: '其他', status: 'ONLINE', canPurchase: true,
    descriptionHtml: '', images: [], mainImagePath: null, sellingMode: 'FIXED_PRICE',
    publishedAt: '2026-11-16T10:00:00', statusUpdatedAt: '2026-11-16T10:00:00',
  }
  const respond = (data: unknown) => ({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, message: 'ok', data }) })
  let submitted: unknown
  await page.addInitScript(() => localStorage.setItem('seller_token', 'test-seller'))
  await page.route('**/api/categories/tree', route => route.fulfill(respond([
    { id: 1, name: '分类', children: [{ id: 2, name: '其他', children: [] }] },
  ])))
  await page.route('**/api/admin/products?**', route => route.fulfill(respond({ items: [item], page: 1, size: 100, total: 1, pages: 1 })))
  await page.route('**/api/admin/products/41', route => {
    submitted = route.request().postDataJSON()
    return route.fulfill(respond(item))
  })
  await page.goto('/admin/products/41/edit')
  const inventory = page.getByLabel('库存数量')
  await expect(inventory).toHaveValue(huge)
  await inventory.fill('1.5')
  await page.getByRole('button', { name: '保存库存和类目' }).click()
  await expect(page.getByText('库存不能为负数，请输入非负整数。')).toBeVisible()
  expect(submitted).toBeUndefined()
  await inventory.fill(huge)
  await page.getByRole('button', { name: '保存库存和类目' }).click()
  await expect(page).toHaveURL(/\/admin\/products$/)
  expect(submitted).toEqual({ stock: huge, category2Id: 2 })
})
