import { expect, test } from '@playwright/test'

const apiResponse = (data: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ code: 0, data }),
})

test('买家提交购买意向后可凭口令查询状态和排位', async ({ page }) => {
  let submittedIntent: { buyerName: string; buyerPhone: string } | undefined

  await page.route('**/api/products/current', (route) =>
    route.fulfill(apiResponse({
      id: 42,
      name: '测试商品',
      description: '供端到端测试使用',
      imagePath: '',
      price: 88,
      status: 'ONLINE',
      freezeSource: null,
      publishedAt: '2026-10-05T10:00:00',
      soldAt: null,
      statusUpdatedAt: null,
    })),
  )

  await page.route('**/api/intents', async (route) => {
    if (route.request().method() === 'POST') {
      submittedIntent = route.request().postDataJSON()
      await route.fulfill(apiResponse({ code: 'BUYER-CODE-123', position: 1, status: 'QUEUING' }))
      return
    }
    await route.continue()
  })

  await page.route('**/api/intents/BUYER-CODE-123', (route) =>
    route.fulfill(apiResponse({
      id: 501,
      productId: 42,
      buyerName: '测试买家',
      buyerPhone: '13800138000',
      status: 'QUEUING',
      submittedAt: '2026-10-05T10:01:00',
      position: 1,
      processedAt: null,
      currentTradeAttemptId: null,
    })),
  )

  await page.goto('/')
  await page.getByLabel('姓名').fill('测试买家')
  await page.getByLabel('手机号').fill('13800138000')
  await page.getByRole('button', { name: '提交购买意向' }).click()

  const confirmation = page.getByRole('dialog')
  await expect(confirmation.getByText('BUYER-CODE-123')).toBeVisible()
  await page.goto('/intent')
  await page.getByLabel('购买意向口令码').fill('BUYER-CODE-123')
  await page.getByRole('button', { name: /查\s*询/ }).click()

  await expect(page).toHaveURL(/\/intent\/BUYER-CODE-123$/)
  await expect(page.getByText('第 1 位')).toBeVisible()
  await expect(page.getByText('排队中')).toBeVisible()
  expect(submittedIntent).toEqual({ buyerName: '测试买家', buyerPhone: '13800138000' })
})

test('卖家登录后开始队首交易并确认成功', async ({ page }) => {
  let queueState: 'QUEUING' | 'IN_TRANSACTION' | 'DONE' = 'QUEUING'
  let startedIntentId: number | undefined
  let successRequest: { tradeAttemptId: number } | undefined

  await page.route('**/api/admin/auth/login', (route) =>
    route.fulfill(apiResponse({ token: 'mock-jwt-token', username: 'admin' })),
  )

  await page.route('**/api/admin/intents', async (route) => {
    const queue = queueState === 'DONE'
      ? []
      : [{
          id: 701,
          productId: 42,
          buyerName: '队首买家',
          buyerPhone: '13900139000',
          status: queueState,
          submittedAt: '2026-10-05T10:02:00',
          position: queueState === 'QUEUING' ? 1 : 0,
          processedAt: null,
          currentTradeAttemptId: queueState === 'IN_TRANSACTION' ? 9001 : null,
        }]
    await route.fulfill(apiResponse(queue))
  })

  await page.route('**/api/admin/intents/701/start', async (route) => {
    startedIntentId = 701
    queueState = 'IN_TRANSACTION'
    await route.fulfill(apiResponse(null))
  })

  await page.route('**/api/admin/intents/701/success', async (route) => {
    successRequest = route.request().postDataJSON()
    queueState = 'DONE'
    await route.fulfill(apiResponse(null))
  })

  await page.goto('/admin/login')
  await page.getByLabel('账号').fill('admin')
  await page.getByLabel('密码').fill('mock-password')
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await page.getByRole('banner').getByRole('button', { name: /意向队列/ }).click()

  await expect(page.getByText('队首买家')).toBeVisible()
  await expect(page.getByText(/提交时间：/)).toBeVisible()
  await page.getByRole('button', { name: '开始处理队首' }).click()
  await page.getByRole('button', { name: '确认成功' }).click()

  await expect(page.getByText('暂无排队意向')).toBeVisible()
  await expect(page.getByText('当前没有进行中的交易')).toBeVisible()
  expect(startedIntentId).toBe(701)
  expect(successRequest).toEqual({ tradeAttemptId: 9001 })
})

test('发布商品时要求填写非空描述', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('shop_token', 'mock-jwt-token'))
  await page.goto('/admin/products/publish')
  await page.getByLabel('商品名称').fill('测试商品')
  await page.getByLabel('价格').fill('88')
  await page.getByRole('button', { name: '发布商品', exact: true }).click()
  await expect(page.getByText('请输入商品描述')).toBeVisible()

  await page.getByLabel('商品描述').fill('   ')
  await page.getByRole('button', { name: '发布商品', exact: true }).click()
  await expect(page.getByText('商品描述不能全是空白')).toBeVisible()
})