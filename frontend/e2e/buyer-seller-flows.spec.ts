import { expect, test } from '@playwright/test'

const apiResponse = (data: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ code: 0, message: 'ok', data }),
})

test('匿名买家可浏览商品，但提交意向时必须登录且没有口令入口', async ({ page }) => {
  await page.route('**/api/categories/tree', (route) =>
    route.fulfill(apiResponse([{ id: 1, name: '服饰', children: [{ id: 2, name: '上衣', children: [] }] }])),
  )
  await page.route('**/api/products?**', (route) =>
    route.fulfill(apiResponse({
      items: [{
        productId: 42,
        name: '测试商品',
        price: 88,
        mainImagePath: null,
        category2Id: 2,
        category2Name: '上衣',
      }],
      page: 1,
      size: 10,
      total: 1,
      pages: 1,
    })),
  )
  await page.route('**/api/products/42', (route) =>
    route.fulfill(apiResponse({
      productId: 42,
      name: '测试商品',
      descriptionHtml: '<p>商品描述</p>',
      price: 88,
      stock: 2,
      status: 'ONLINE',
      canPurchase: true,
      category2Id: 2,
      category2Name: '上衣',
      images: [],
      mainImagePath: null,
      publishedAt: '2026-10-25T09:00:00',
      statusUpdatedAt: '2026-10-25T09:00:00',
    })),
  )

  await page.goto('/')
  await page.getByText('测试商品').first().click()
  await expect(page.getByRole('heading', { name: '商品描述' })).toBeVisible()
  await page.getByRole('button', { name: '提交购买意向' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByText(/口令/)).toHaveCount(0)
})

test('下架商品详情即使 API 返回成功也不展示商品信息', async ({ page }) => {
  await page.route('**/api/products/99', (route) =>
    route.fulfill(apiResponse({
      productId: 99,
      name: '已下架商品',
      descriptionHtml: '<p>不可见描述</p>',
      price: 88,
      stock: 0,
      status: 'OFFLINE',
      canPurchase: false,
      category2Id: 2,
      category2Name: '上衣',
      images: [],
      mainImagePath: null,
      publishedAt: '2026-10-25T09:00:00',
      statusUpdatedAt: '2026-10-25T09:00:00',
    })),
  )

  await page.goto('/products/99')
  await expect(page.getByText('商品当前不可查看')).toBeVisible()
  await expect(page.getByText('已下架商品')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '提交购买意向' })).toHaveCount(0)
})

test('卖家按商品队列开始交易，确认成功请求不带请求体', async ({ page }) => {
  let queueStatus: 'QUEUING' | 'IN_TRANSACTION' | 'DONE' = 'QUEUING'
  let successBody: string | null = 'not-called'
  let failBody: string | null = 'not-called'

  await page.route('**/api/admin/auth/login', (route) =>
    route.fulfill(apiResponse({ token: 'seller-token', userId: 1, role: 'SELLER', username: 'admin' })),
  )
  await page.route('**/api/admin/products?**', (route) =>
    route.fulfill(apiResponse({
      items: [{
        productId: 42,
        name: '测试商品',
        price: 88,
        stock: 2,
        category2Id: 2,
        category2Name: '上衣',
        status: 'ONLINE',
        canPurchase: true,
        descriptionHtml: '',
        images: [],
        mainImagePath: null,
        publishedAt: '2026-10-25T09:00:00',
        statusUpdatedAt: '2026-10-25T09:00:00',
      }],
      page: 1,
      size: 10,
      total: 1,
      pages: 1,
    })),
  )
  await page.route('**/api/admin/intents**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/701/start')) {
      queueStatus = 'IN_TRANSACTION'
      await route.fulfill(apiResponse(null))
      return
    }
    if (url.pathname.endsWith('/701/success')) {
      successBody = route.request().postData()
      queueStatus = 'DONE'
      await route.fulfill(apiResponse(null))
      return
    }
    if (url.pathname.endsWith('/701/fail')) {
      failBody = route.request().postData()
      queueStatus = 'DONE'
      await route.fulfill(apiResponse(null))
      return
    }
    const items = queueStatus === 'DONE' ? [] : [{
      intentId: 701,
      productId: 42,
      customerId: 17,
      username: '队首买家',
      phone: '13800000000',
      status: queueStatus,
      submittedAt: '2026-10-25T10:00:00',
      position: queueStatus === 'QUEUING' ? 1 : 0,
    }]
    await route.fulfill(apiResponse({ items, page: 1, size: 10, total: items.length, pages: 1 }))
  })

  await page.goto('/admin/login')
  await page.getByLabel('账号').fill('admin')
  await page.getByLabel('密码').fill('password')
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await page.getByRole('button', { name: '商品管理' }).click()
  await page.getByRole('button', { name: '意向队列' }).click()
  await expect(page.getByText('队首买家')).toBeVisible()
  await page.getByRole('button', { name: '开始处理队首' }).click()
  await page.getByRole('button', { name: '确认成功' }).click()
  await expect(page.getByText('当前没有进行中的交易')).toBeVisible()
  expect(successBody).toBeNull()

  queueStatus = 'QUEUING'
  await page.getByRole('button', { name: '商品管理' }).click()
  await page.getByRole('button', { name: '意向队列' }).click()
  await page.getByRole('button', { name: '开始处理队首' }).click()
  await page.getByRole('button', { name: '失败并重新排队' }).click()
  await page.getByRole('button', { name: '重新排队', exact: true }).click()
  await expect(page.getByText('当前没有进行中的交易')).toBeVisible()
  expect(JSON.parse(failBody ?? 'null')).toEqual({ action: 'REQUEUE' })
})

test('买家购买历史按后端订单字段展示成功和失败终态', async ({ page }) => {
  await page.route('**/api/categories/tree', (route) =>
    route.fulfill(apiResponse([])),
  )
  await page.route('**/api/products?**', (route) =>
    route.fulfill(apiResponse({ items: [], page: 1, size: 10, total: 0, pages: 0 })),
  )
  await page.route('**/api/auth/login', (route) =>
    route.fulfill(apiResponse({ token: 'customer-token', userId: 17, role: 'CUSTOMER', username: 'buyer' })),
  )
  await page.route('**/api/me/order-history?**', (route) =>
    route.fulfill(apiResponse({
      items: [{
        orderId: 904,
        productName: '历史商品',
        submittedAt: '2026-10-25T10:00:00',
        status: 'FAILED',
        transactedAt: '2026-10-25T10:30:00',
      }],
      page: 1,
      size: 10,
      total: 1,
      pages: 1,
    })),
  )

  await page.goto('/login')
  await page.getByLabel('用户名').fill('buyer')
  await page.getByLabel('密码').fill('password')
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await page.getByRole('button', { name: '我的购买历史' }).click()
  await expect(page.getByRole('cell', { name: '历史商品' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '失败' })).toBeVisible()
})

test('买家可查看账户概览、进入购买历史并退出登录', async ({ page }) => {
  await page.route('**/api/auth/login', (route) =>
    route.fulfill(apiResponse({ token: 'customer-token', userId: 17, role: 'CUSTOMER', username: 'buyer' })),
  )
  await page.route('**/api/categories/tree', (route) =>
    route.fulfill(apiResponse([])),
  )
  await page.route('**/api/products?**', (route) =>
    route.fulfill(apiResponse({ items: [], page: 1, size: 10, total: 0, pages: 0 })),
  )
  await page.route('**/api/me/order-history?**', (route) =>
    route.fulfill(apiResponse({ items: [], page: 1, size: 10, total: 0, pages: 0 })),
  )

  await page.goto('/login')
  await page.getByLabel('用户名').fill('buyer')
  await page.getByLabel('密码').fill('password')
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await page.getByRole('button', { name: '我的账户' }).click()

  await expect(page.getByRole('heading', { name: '买家账户' })).toBeVisible()
  await expect(page.getByText('buyer', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('17', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: '查看购买历史' }).click()
  await expect(page.getByRole('heading', { name: '我的购买历史' })).toBeVisible()
  await page.goto('/me/account')
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page).toHaveURL('/')
  await expect(page.getByRole('button', { name: /登\s*录/ })).toBeVisible()
})
