import { expect, test } from '@playwright/test'

const apiResponse = (data: unknown) => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ code: 0, message: 'ok', data }),
})

test('匿名买家可浏览商品，一口价详情不再提交旧意向且没有口令入口', async ({ page }) => {
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
  await expect(page.getByRole('button', { name: '加入购物车' })).toBeVisible()
  await expect(page.getByRole('button', { name: '提交购买意向' })).toHaveCount(0)
  await expect(page.getByText(/口令/)).toHaveCount(0)
})

test('一口价商品不再进入旧意向队列且不请求拍卖快照', async ({ page }) => {
  let auctionSnapshotRequests = 0
  let intentRequests = 0
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  await page.route('**/api/categories/tree', (route) =>
    route.fulfill(apiResponse([{ id: 1, name: '家居', children: [{ id: 2, name: '灯具', children: [] }] }])),
  )
  await page.route('**/api/products?**', (route) =>
    route.fulfill(apiResponse({
      items: [{
        productId: 42,
        name: '普通商品回归',
        price: 88,
        mainImagePath: null,
        category2Id: 2,
        category2Name: '灯具',
        sellingMode: 'FIXED_PRICE',
        auction: null,
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
      name: '普通商品回归',
      descriptionHtml: '<p>一口价商品描述</p>',
      price: 88,
      stock: 2,
      status: 'ONLINE',
      canPurchase: true,
      category2Id: 2,
      category2Name: '灯具',
      images: [],
      mainImagePath: null,
      publishedAt: '2026-11-09T10:00:00',
      statusUpdatedAt: '2026-11-09T10:00:00',
      sellingMode: 'FIXED_PRICE',
      auction: null,
    })),
  )
  await page.route('**/api/products/42/auction', async (route) => {
    auctionSnapshotRequests += 1
    await route.fulfill(apiResponse({}))
  })
  await page.route('**/api/me/favorites/42', (route) =>
    route.fulfill(apiResponse({ favorited: false, createdAt: null })),
  )
  await page.route('**/api/products/42/intents', async (route) => {
    intentRequests += 1
    await route.fulfill(apiResponse({ intentId: 701, productId: 42, status: 'QUEUING' }))
  })

  await page.goto('/')
  await page.getByText('普通商品回归').first().click()
  await expect(page.getByRole('button', { name: '加入购物车' })).toBeVisible()
  await expect(page.getByRole('button', { name: '提交购买意向' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '出价' })).toHaveCount(0)
  expect(intentRequests).toBe(0)
  expect(auctionSnapshotRequests).toBe(0)
})

test('拍卖 SSE 更新领先状态并在结拍后禁用出价', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  const snapshot = {
    productId: 88,
    productName: '实时拍卖商品',
    sellingMode: 'AUCTION',
    auctionStatus: 'LIVE',
    startPrice: 10,
    minIncrement: 2,
    currentPrice: 10,
    nextMinBid: 12,
    bidCount: 1,
    endsAt: '2026-11-09T12:00:00',
    settledAt: null,
    serverTime: '2026-11-09T11:00:00',
    leaderAlias: 'b***r',
    lastBidSeq: 1,
    recentBids: [],
    canBid: true,
    myStatus: 'LEADING',
  }
  const bid = {
    productId: 88,
    bidSeq: 2,
    amount: 12,
    currentPrice: 12,
    nextMinBid: 14,
    bidCount: 2,
    leaderAlias: 'b***r',
    bidAt: '2026-11-09T11:30:00',
    youAreLeading: true,
  }
  const settled = {
    productId: 88,
    auctionStatus: 'ENDED_SOLD',
    finalPrice: 12,
    winnerAlias: 'b***r',
    settledAt: '2026-11-09T12:00:00',
    youWon: true,
  }
  await page.route('**/api/products/88', (route) =>
    route.fulfill(apiResponse({
      productId: 88,
      name: '实时拍卖商品',
      descriptionHtml: '',
      price: 10,
      stock: 1,
      status: 'ONLINE',
      canPurchase: false,
      category2Id: 2,
      category2Name: '灯具',
      images: [],
      mainImagePath: null,
      publishedAt: '2026-11-09T10:00:00',
      statusUpdatedAt: '2026-11-09T10:00:00',
      sellingMode: 'AUCTION',
    })),
  )
  await page.route('**/api/products/88/auction', (route) =>
    route.fulfill(apiResponse(snapshot)),
  )
  await page.route('**/api/products/88/auction/stream', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        `event: snapshot\ndata: ${JSON.stringify(snapshot)}\n\n`,
        `event: bid\nid: 2\ndata: ${JSON.stringify(bid)}\n\n`,
        `event: settled\nid: settled\ndata: ${JSON.stringify(settled)}\n\n`,
      ].join(''),
    }),
  )

  await page.goto('/products/88')
  await expect(page.getByText('出价次数：2')).toBeVisible()
  await expect(page.getByText('当前领先者：b***r')).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('恭喜你中标')
  await expect(page.getByRole('button', { name: /出\s*价/ })).toBeDisabled()
  await expect(page.getByRole('button', { name: '提交购买意向' })).toHaveCount(0)
})

test('买家拍卖提醒页通过通知 SSE 显示结拍提醒', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  const notification = {
    notificationId: 903,
    auctionId: 88,
    productId: 88,
    type: 'AUCTION_WON',
    productName: 'R4结拍提醒商品',
    finalPrice: 12,
    createdAt: '2026-11-09T12:00:00',
    readAt: null,
  }
  await page.route('**/api/me/auction-notifications?**', (route) =>
    route.fulfill(apiResponse({ items: [], page: 1, size: 10, total: 0, pages: 0, unread: 0 })),
  )
  await page.route('**/api/me/auction-notifications/stream', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 200))
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: `event: notification\nid: 903\ndata: ${JSON.stringify(notification)}\n\n`,
    })
  })

  await page.goto('/me/auction-notifications')
  await expect(page.getByText('R4结拍提醒商品')).toBeVisible()
  await expect(page.getByText('恭喜你中标，成交价 ¥12.00')).toBeVisible()
  await expect(page.getByText('暂无拍卖中标提醒')).toHaveCount(0)
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

test('拍卖实时出价更新最近出价和本人被超越状态', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  const snapshot = {
    productId: 42,
    productName: '实时拍卖商品',
    sellingMode: 'AUCTION',
    auctionStatus: 'LIVE',
    startPrice: 10,
    minIncrement: 1,
    currentPrice: 15,
    nextMinBid: 16,
    bidCount: 2,
    endsAt: '2026-11-10T18:00:00',
    settledAt: null,
    serverTime: '2026-11-10T17:00:00',
    leaderAlias: 'B***r',
    lastBidSeq: 2,
    recentBids: [{ bidSeq: 2, amount: 15, bidderAlias: 'B***r', bidAt: '2026-11-10T16:59:00' }],
    canBid: true,
    myStatus: 'LEADING',
  }
  await page.route('**/api/products/42', (route) =>
    route.fulfill(apiResponse({
      productId: 42,
      name: '实时拍卖商品',
      descriptionHtml: '',
      price: 10,
      stock: 1,
      status: 'ONLINE',
      canPurchase: false,
      sellingMode: 'AUCTION',
      category2Id: 2,
      category2Name: '上衣',
      images: [],
      mainImagePath: null,
      publishedAt: '2026-11-10T16:00:00',
      statusUpdatedAt: '2026-11-10T16:00:00',
    })),
  )
  await page.route('**/api/products/42/auction', (route) =>
    route.fulfill(apiResponse(snapshot)),
  )
  await page.route('**/api/products/42/auction/stream', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        `event: snapshot\ndata: ${JSON.stringify(snapshot)}`,
        `event: bid\ndata: ${JSON.stringify({
          productId: 42,
          bidSeq: 3,
          amount: 16,
          currentPrice: 16,
          nextMinBid: 17,
          bidCount: 3,
          leaderAlias: 'C***r',
          bidAt: '2026-11-10T17:00:01',
          youAreLeading: false,
        })}`,
        '',
      ].join('\n\n'),
    }),
  )

  await page.goto('/products/42')

  await expect(page.getByText('已被超越')).toBeVisible()
  await expect(page.getByText('#3 C***r：¥16.00')).toBeVisible()
  await expect(page.getByText('出价次数：3')).toBeVisible()
})

test('卖家可处理拍卖履约，确认成功请求不带请求体', async ({ page }) => {
  let queueStatus: 'IN_TRANSACTION' | 'DONE' = 'IN_TRANSACTION'
  let successBody: string | null = 'not-called'
  const auctionSnapshot = {
    productId: 42,
    productName: '测试商品',
    sellingMode: 'AUCTION',
    auctionStatus: 'ENDED_SOLD',
    startPrice: 88,
    minIncrement: 1,
    currentPrice: 88,
    nextMinBid: 89,
    bidCount: 1,
    endsAt: '2026-10-25T10:00:00',
    settledAt: '2026-10-25T10:00:00',
    serverTime: '2026-10-25T10:00:00',
    leaderAlias: 'b***r',
    lastBidSeq: 1,
    recentBids: [],
    canBid: false,
    myStatus: 'WON',
  }

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
        sellingMode: 'AUCTION',
      }],
      page: 1,
      size: 10,
      total: 1,
      pages: 1,
    })),
  )
  await page.route('**/api/admin/intents**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/701/success')) {
      successBody = route.request().postData()
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
      status: 'IN_TRANSACTION',
      submittedAt: '2026-10-25T10:00:00',
      position: 0,
    }]
    await route.fulfill(apiResponse({ items, page: 1, size: 10, total: items.length, pages: 1 }))
  })
  await page.route('**/api/products/42/auction', (route) =>
    route.fulfill(apiResponse(auctionSnapshot)),
  )
  await page.route('**/api/products/42/auction/stream', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: `event: snapshot\ndata: ${JSON.stringify(auctionSnapshot)}\n\n`,
    }),
  )

  await page.goto('/admin/login')
  await page.getByLabel('账号').fill('admin')
  await page.getByLabel('密码').fill('password')
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await page.getByRole('button', { name: '商品管理' }).click()
  await page.getByRole('button', { name: '拍卖履约' }).click()
  await expect(page.getByText('队首买家')).toBeVisible()
  await page.getByRole('button', { name: '确认成功' }).click()
  await expect(page.getByText('当前没有进行中的交易')).toBeVisible()
  expect(successBody).toBeNull()
})

test('卖家一口价商品不能进入旧意向队列', async ({ page }) => {
  let intentQueueRequests = 0
  await page.addInitScript(() => localStorage.setItem('seller_token', 'seller-token'))
  await page.route('**/api/admin/products?**', (route) =>
    route.fulfill(apiResponse({
      items: [{
        productId: 42,
        name: '一口价归档商品',
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
        sellingMode: 'FIXED_PRICE',
      }],
      page: 1,
      size: 100,
      total: 1,
      pages: 1,
    })),
  )
  await page.route('**/api/admin/intents**', async (route) => {
    intentQueueRequests += 1
    await route.fulfill(apiResponse({ items: [], page: 1, size: 10, total: 0, pages: 0 }))
  })

  await page.goto('/admin/products/42/intents')

  await expect(page).toHaveURL('/admin/products')
  await expect(page.getByRole('button', { name: '拍卖履约' })).toHaveCount(0)
  expect(intentQueueRequests).toBe(0)
})

test('客户令牌失效后提示原因并返回原页且不自动重试操作', async ({ page }) => {
  let markReadRequests = 0
  const notification = {
    notificationId: 903,
    auctionId: 88,
    productId: 88,
    type: 'AUCTION_WON',
    productName: '待读拍卖提醒',
    finalPrice: 12,
    createdAt: '2026-11-09T12:00:00',
    readAt: null,
  }
  await page.addInitScript(() => localStorage.setItem('customer_token', 'expired-token'))
  await page.route('**/api/me/auction-notifications?**', (route) =>
    route.fulfill(apiResponse({ items: [notification], page: 1, size: 10, total: 1, pages: 1, unread: 1 })),
  )
  await page.route('**/api/me/auction-notifications/stream', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }),
  )
  await page.route('**/api/me/auction-notifications/903/read', async (route) => {
    markReadRequests += 1
    await route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ code: 40101, message: '请重新登录', data: null }),
    })
  })
  await page.route('**/api/auth/login', (route) =>
    route.fulfill(apiResponse({ token: 'customer-token', userId: 17, role: 'CUSTOMER', username: 'buyer' })),
  )

  await page.goto('/me/auction-notifications')
  await page.getByRole('button', { name: '查看商品' }).click()
  await expect(page).toHaveURL(/\/login\?returnTo=/)
  await expect(page.locator('.ant-message-notice').filter({ hasText: '请重新登录' })).toBeVisible()

  await page.getByLabel('用户名').fill('buyer')
  await page.getByLabel('密码').fill('password')
  await page.getByRole('button', { name: /登\s*录/ }).click()

  await expect(page).toHaveURL('/me/auction-notifications')
  await expect(page.getByText('待读拍卖提醒')).toBeVisible()
  expect(markReadRequests).toBe(1)
})

test('统一请求层保留成功提示和逐项失败数据', async ({ page }) => {
  const itemError = {
    cartItemId: '21',
    productId: '11',
    productName: '测试商品',
    reason: 'OFFLINE',
    message: '商品「测试商品」已下架，请从购物车移除后重试。',
  }
  await page.route('**/api/me/checkout/confirmations', (route) =>
    route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({ code: 40910, message: '所选商品无法下单', data: { errors: [itemError] } }),
    }),
  )
  await page.route('**/api/me/favorites/44', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        message: '已收藏',
        data: { favoriteId: '31', productId: '44', createdAt: '2026-11-16T10:00:00' },
      }),
    }),
  )

  await page.goto('/login')
  const result = await page.evaluate(async () => {
    const { request, requestWithMessage } = await import('../src/api/request')
    let failure: { message: string; data: unknown; itemErrors: unknown[] } | undefined
    try {
      await request({ url: '/me/checkout/confirmations', method: 'POST', data: { cartItemIds: ['21'] } })
    } catch (error) {
      const apiError = error as Error & { data: unknown; itemErrors: unknown[] }
      failure = { message: apiError.message, data: apiError.data, itemErrors: apiError.itemErrors }
    }
    const success = await requestWithMessage<{ favoriteId: string; productId: string; createdAt: string }>({
      url: '/me/favorites/44',
      method: 'PUT',
    })
    return { failure, success }
  })

  expect(result.failure).toEqual({
    message: '所选商品无法下单',
    data: { errors: [itemError] },
    itemErrors: [itemError],
  })
  expect(result.success).toEqual({
    data: { favoriteId: '31', productId: '44', createdAt: '2026-11-16T10:00:00' },
    message: '已收藏',
  })
  await expect(page.locator('.ant-message-notice')).toHaveCount(0)
})

test('挑战B越权提示使用服务端原文', async ({ page }) => {
  await page.route('**/api/me/favorites/44', (route) =>
    route.fulfill({
      status: 403,
      contentType: 'application/json',
      body: JSON.stringify({ code: 40302, message: '无权操作', data: null }),
    }),
  )

  await page.goto('/login')
  await page.evaluate(async () => {
    const { request } = await import('../src/api/request')
    try {
      await request({ url: '/me/favorites/44', method: 'GET' })
    } catch {
      return
    }
  })

  await expect(page.locator('.ant-message-notice').filter({ hasText: '无权操作' })).toBeVisible()
  await expect(page.getByText('当前账号无权执行此操作。')).toHaveCount(0)
})

test('买家订单历史按挑战B订单字段展示状态与快照', async ({ page }) => {
  await page.route('**/api/categories/tree', (route) =>
    route.fulfill(apiResponse([])),
  )
  await page.route('**/api/products?**', (route) =>
    route.fulfill(apiResponse({ items: [], page: 1, size: 10, total: 0, pages: 0 })),
  )
  await page.route('**/api/auth/login', (route) =>
    route.fulfill(apiResponse({ token: 'customer-token', userId: 17, role: 'CUSTOMER', username: 'buyer' })),
  )
  await page.route('**/api/me/orders?**', (route) =>
    route.fulfill(apiResponse({
      items: [{
        orderId: '904',
        orderNo: 'OX-904',
        customerId: '17',
        status: 'CANCELLED',
        items: [{ productId: '42', productName: '历史商品', unitPrice: '88.00', quantity: '1', lineAmount: '88.00' }],
        totalAmount: '88.00',
        createdAt: '2026-10-25T10:00:00',
        cancelledBy: 'CUSTOMER',
        cancelledAt: '2026-10-25T10:30:00',
        cancelReason: null,
        allowedActions: [],
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
  await page.getByRole('button', { name: '订单历史' }).click()
  await expect(page.getByRole('cell', { name: '历史商品' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '已取消' })).toBeVisible()
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
  await page.route('**/api/me/orders?**', (route) =>
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

  await page.getByRole('button', { name: '订单历史' }).click()
  await expect(page.getByRole('heading', { name: '订单历史' })).toBeVisible()
  await page.goto('/me/account')
  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page).toHaveURL('/')
  await expect(page.getByRole('button', { name: /登\s*录/ })).toBeVisible()
})

test('商品详情收藏和加购使用契约接口，加购只增加一件', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  await page.route('**/api/products/42', (route) =>
    route.fulfill(apiResponse({
      productId: 42, name: '详情商品', price: 20, stock: '3', status: 'ONLINE', canPurchase: true,
      category2Id: 2, category2Name: '家居', images: [], mainImagePath: null,
      descriptionHtml: '', publishedAt: '2026-11-16T10:00:00', statusUpdatedAt: '2026-11-16T10:00:00',
      sellingMode: 'FIXED_PRICE',
    })),
  )
  let favoriteWrites = 0
  let favoriteDeletes = 0
  await page.route('**/api/me/favorites/42', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill(apiResponse({ favorited: false, createdAt: null }))
      return
    }
    if (route.request().method() === 'DELETE') {
      favoriteDeletes += 1
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, message: '已取消收藏', data: null }) })
      return
    }
    favoriteWrites += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ code: 0, message: '已收藏', data: { favoriteId: '51', productId: '42', createdAt: '2026-11-16T10:00:00' } }),
    })
  })
  let cartRequest: { productId: string; key?: string } | undefined
  await page.route('**/api/me/cart/items', async (route) => {
    cartRequest = {
      productId: route.request().postDataJSON().productId,
      key: route.request().headers()['idempotency-key'],
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ code: 0, message: '已加入购物车', data: { cartItemId: '71' } }),
    })
  })

  await page.goto('/products/42')
  await page.getByRole('button', { name: /收\s*藏/ }).click()
  await expect(page.locator('.ant-message-notice').filter({ hasText: '已收藏' })).toBeVisible()
  await expect(page.getByRole('button', { name: '取消收藏' })).toBeVisible()
  await page.getByRole('button', { name: '加入购物车' }).click()
  await expect(page.locator('.ant-message-notice').filter({ hasText: '已加入购物车' })).toBeVisible()
  await page.getByRole('button', { name: '取消收藏' }).click()
  await expect(page.locator('.ant-message-notice').filter({ hasText: '已取消收藏' })).toBeVisible()
  expect(favoriteWrites).toBe(1)
  expect(favoriteDeletes).toBe(1)
  expect(cartRequest?.productId).toBe('42')
  expect(cartRequest?.key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i)
  await expect(page.getByRole('button', { name: '直接下单' })).toHaveCount(0)
})

test('匿名详情登录返回后不会自动执行收藏或加购', async ({ page }) => {
  let writes = 0
  await page.route('**/api/products/42', (route) =>
    route.fulfill(apiResponse({
      productId: 42, name: '详情商品', price: 20, stock: '3', status: 'ONLINE', canPurchase: true,
      category2Id: 2, category2Name: '家居', images: [], mainImagePath: null, descriptionHtml: '',
      publishedAt: '2026-11-16T10:00:00', statusUpdatedAt: '2026-11-16T10:00:00', sellingMode: 'FIXED_PRICE',
    })),
  )
  await page.route('**/api/auth/login', (route) =>
    route.fulfill(apiResponse({ token: 'customer-token', userId: 17, role: 'CUSTOMER', username: 'buyer' })),
  )
  await page.route('**/api/me/favorites/42', async (route) => {
    if (route.request().method() !== 'GET') writes += 1
    await route.fulfill(apiResponse({ favorited: false, createdAt: null }))
  })
  await page.route('**/api/me/cart/items', async (route) => {
    writes += 1
    await route.fulfill(apiResponse({ cartItemId: '71' }))
  })

  await page.goto('/products/42')
  await page.getByRole('button', { name: '加入购物车' }).click()
  await expect(page).toHaveURL('/login')
  await page.getByLabel('用户名').fill('buyer')
  await page.getByLabel('密码').fill('password')
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await expect(page).toHaveURL('/products/42')
  expect(writes).toBe(0)
})

test('收藏列表将失效商品设为只读并支持取消收藏', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  await page.route('**/api/me/favorites?**', (route) =>
    route.fulfill(apiResponse({
      items: [
        { favoriteId: '1', productId: '42', productName: '在售商品', unitPrice: '20.00', mainImageUrl: null, createdAt: '2026-11-16T10:00:00', valid: true, invalidLabel: null, canOpenDetail: true },
        { favoriteId: '2', productId: '43', productName: '下架商品', unitPrice: '30.00', mainImageUrl: null, createdAt: '2026-11-16T10:00:00', valid: false, invalidLabel: '已下架', canOpenDetail: false },
      ],
      page: 1, size: 10, total: 2, pages: 1,
    })),
  )
  await page.route('**/api/me/favorites/43', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, message: '已取消收藏', data: null }) }),
  )

  await page.goto('/me/favorites')
  await expect(page.getByRole('link', { name: '在售商品' })).toHaveAttribute('href', '/products/42')
  await expect(page.getByRole('link', { name: '下架商品' })).toHaveCount(0)
  await page.getByRole('button', { name: '取消收藏' }).nth(1).click()
  await expect(page.getByText('下架商品')).toHaveCount(0)
  await expect(page.locator('.ant-message-notice').filter({ hasText: '已取消收藏' })).toBeVisible()
})

test('购物车改量拒绝非整数、数量零移除且不修改其他行', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  const items = [{
    cartItemId: '21', productId: '11', productName: '键盘', unitPrice: '10.00', mainImageUrl: null,
    quantity: '2', stock: '5', online: true, invalidLabel: null, defaultCheckoutSelected: true,
    canCheckoutSelect: true, canFavoriteSelect: true, updatedAt: '2026-11-16T10:00:00',
  }, {
    cartItemId: '22', productId: '12', productName: '下架商品', unitPrice: '15.00', mainImageUrl: null,
    quantity: '1', stock: '0', online: false, invalidLabel: '已下架', defaultCheckoutSelected: false,
    canCheckoutSelect: false, canFavoriteSelect: false, updatedAt: '2026-11-16T10:00:00',
  }, {
    cartItemId: '23', productId: '13', productName: '库存不足商品', unitPrice: '8.00', mainImageUrl: null,
    quantity: '3', stock: '1', online: true, invalidLabel: null, defaultCheckoutSelected: false,
    canCheckoutSelect: true, canFavoriteSelect: true, updatedAt: '2026-11-16T10:00:00',
  }]
  await page.route('**/api/me/cart', (route) => route.fulfill(apiResponse({ items })))
  let patchCount = 0
  await page.route('**/api/me/cart/items/21', async (route) => {
    patchCount += 1
    expect(route.request().postDataJSON()).toEqual({ quantity: '0' })
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, message: '已移除', data: null }) })
  })

  await page.goto('/me/cart')
  const checkboxes = page.locator('.ant-checkbox-input')
  await expect(checkboxes).toHaveCount(4)
  await expect(checkboxes.nth(1)).toBeChecked()
  await expect(checkboxes.nth(2)).toBeDisabled()
  await expect(checkboxes.nth(3)).not.toBeChecked()
  await page.getByRole('checkbox', { name: '全选可下单商品' }).check()
  await expect(checkboxes.nth(1)).toBeChecked()
  await expect(checkboxes.nth(3)).toBeChecked()
  const quantity = page.getByLabel('键盘数量')
  await quantity.fill('1.5')
  await page.getByRole('button', { name: '更新数量' }).first().click()
  await expect(quantity).toHaveValue('2')
  await expect(page.locator('.ant-message-notice').filter({ hasText: '数量无效，请输入正整数' })).toBeVisible()
  expect(patchCount).toBe(0)

  await quantity.fill('0')
  await page.getByRole('button', { name: '更新数量' }).first().click()
  await expect(page.getByText('键盘')).toHaveCount(0)
  await expect(page.getByText('下架商品')).toBeVisible()
  expect(patchCount).toBe(1)
})

test('清空购物车二次确认后只清车，不创建订单', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  let clearRequests = 0
  let orderRequests = 0
  await page.route('**/api/me/cart', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill(apiResponse({ items: [{
        cartItemId: '21', productId: '11', productName: '键盘', unitPrice: '10.00', mainImageUrl: null,
        quantity: '2', stock: '5', online: true, invalidLabel: null, defaultCheckoutSelected: true,
        canCheckoutSelect: true, canFavoriteSelect: true, updatedAt: '2026-11-16T10:00:00',
      }] }))
      return
    }
    clearRequests += 1
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ code: 0, message: '购物车已清空', data: null }) })
  })
  await page.route('**/api/me/checkout/confirmations', async (route) => {
    orderRequests += 1
    await route.fulfill(apiResponse(null))
  })

  await page.goto('/me/cart')
  await page.getByRole('button', { name: '清空购物车' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('确定清空购物车？')
  expect(clearRequests).toBe(0)
  await dialog.getByRole('button', { name: '清空购物车' }).click()
  await expect(page.getByText('购物车是空的')).toBeVisible()
  expect(clearRequests).toBe(1)
  expect(orderRequests).toBe(0)
})

test('HTTP环境缺少randomUUID时仍可确认并提交订单', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('customer_token', 'customer-token')
    Object.defineProperty(Crypto.prototype, 'randomUUID', { configurable: true, value: undefined })
  })

  const cartItem = {
    cartItemId: '21', productId: '11', productName: '键盘', unitPrice: '10.00', mainImageUrl: null,
    quantity: '2', stock: '5', online: true, invalidLabel: null, defaultCheckoutSelected: true,
    canCheckoutSelect: true, canFavoriteSelect: true, updatedAt: '2026-11-16T10:00:00',
  }
  let orderRequest: { confirmationToken: string; key?: string } | undefined
  let confirmationRequests = 0
  await page.route('**/api/me/cart', (route) =>
    route.fulfill(apiResponse({ items: orderRequest ? [] : [cartItem] })),
  )
  await page.route('**/api/me/checkout/confirmations', (route) => {
    confirmationRequests += 1
    return route.fulfill(apiResponse({
      confirmationToken: 'b6f90dc4-e989-4cd7-97d8-6f754dd40d1a',
      items: [{
        cartItemId: '21', productId: '11', productName: '键盘', unitPrice: '10.00',
        quantity: '2', lineAmount: '20.00',
      }],
      totalAmount: '20.00',
      createdAt: '2026-11-16T10:00:00',
    }))
  })
  await page.route('**/api/me/orders', async (route) => {
    orderRequest = {
      confirmationToken: route.request().postDataJSON().confirmationToken,
      key: route.request().headers()['idempotency-key'],
    }
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        message: '下单成功',
        data: {
          orderId: '904', orderNo: 'OX-904', customerId: '17', status: 'PLACED',
          items: [{ productId: '11', productName: '键盘', unitPrice: '10.00', quantity: '2', lineAmount: '20.00' }],
          totalAmount: '20.00', createdAt: '2026-11-16T10:00:00', cancelledBy: null,
          cancelledAt: null, cancelReason: null, allowedActions: ['CANCEL'],
        },
      }),
    })
  })

  await page.goto('/me/cart')
  await page.getByRole('button', { name: '下单' }).click()
  await expect.poll(() => confirmationRequests).toBe(1)
  await expect(page.getByRole('dialog', { name: '确认下单' })).toBeVisible()
  await page.getByRole('button', { name: '确认下单' }).click()
  await expect(page.getByRole('dialog', { name: '下单成功' })).toContainText('OX-904')
  expect(orderRequest?.confirmationToken).toBe('b6f90dc4-e989-4cd7-97d8-6f754dd40d1a')
  expect(orderRequest?.key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i)
})

test('购物车旧行改量冲突后刷新并保留仍有效的勾选', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  let cartItems = [{
    cartItemId: '21', productId: '11', productName: '旧行商品', unitPrice: '10.00', mainImageUrl: null,
    quantity: '2', stock: '5', online: true, invalidLabel: null, defaultCheckoutSelected: true,
    canCheckoutSelect: true, canFavoriteSelect: true, updatedAt: '2026-11-16T10:00:00',
  }, {
    cartItemId: '22', productId: '12', productName: '保留商品', unitPrice: '15.00', mainImageUrl: null,
    quantity: '1', stock: '3', online: true, invalidLabel: null, defaultCheckoutSelected: true,
    canCheckoutSelect: true, canFavoriteSelect: true, updatedAt: '2026-11-16T10:00:00',
  }]
  await page.route('**/api/me/cart', (route) => route.fulfill(apiResponse({ items: cartItems })))
  await page.route('**/api/me/cart/items/21', async (route) => {
    cartItems = cartItems.filter((item) => item.cartItemId !== '21')
    await route.fulfill({
      status: 409, contentType: 'application/json',
      body: JSON.stringify({ code: 40912, message: '该商品已不在购物车，请刷新页面后查看。', data: null }),
    })
  })

  await page.goto('/me/cart')
  const checkboxes = page.locator('.ant-checkbox-input')
  await expect(checkboxes).toHaveCount(3)
  await page.getByLabel('旧行商品数量').fill('3')
  await page.getByRole('button', { name: '更新数量' }).first().click()
  await expect(page.getByText('该商品已不在购物车，请刷新页面后查看。')).toBeVisible()
  await expect(page.getByText('旧行商品')).toHaveCount(0)
  await expect(page.getByLabel('保留商品数量')).toBeVisible()
  await expect(checkboxes.nth(1)).toBeChecked()
})

test('买家旧意向归档可追溯成功与关闭记录且不提供订单操作', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  await page.route('**/api/me/legacy-intents?**', (route) =>
    route.fulfill(apiResponse({
      items: [
        { legacyIntentId: '1', productId: '11', productNameSnapshot: '成功历史商品', originalStatus: 'DONE', submittedAt: '2026-10-25T10:00:00', processedAt: '2026-10-25T10:30:00', closedAt: null, displayStatus: 'DONE', readOnly: true },
        { legacyIntentId: '2', productId: '12', productNameSnapshot: '关闭历史商品', originalStatus: 'IN_TRANSACTION', submittedAt: '2026-10-25T11:00:00', processedAt: null, closedAt: '2026-11-01T10:00:00', displayStatus: 'CLOSED', readOnly: true },
      ],
      page: 1, size: 10, total: 2, pages: 1,
    })),
  )

  await page.goto('/me/legacy-intents')
  await expect(page.getByText('成功历史商品')).toBeVisible()
  await expect(page.getByText('原交易成功')).toBeVisible()
  await expect(page.getByText('已关闭（原交易中）')).toBeVisible()
  await expect(page.getByRole('button', { name: /取消|确认|发货|完成/ })).toHaveCount(0)
})

test('卖家库存改为正数不会触发自动上架，旧意向归档可按顾客筛选', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('seller_token', 'seller-token'))
  let onlineRequests = 0
  await page.route('**/api/admin/products**', async (route) => {
    const method = route.request().method()
    if (method === 'PATCH') {
      await route.fulfill(apiResponse({
        productId: 7, name: '零库存商品', price: 20, category2Id: 2, category2Name: '家居',
        stock: '3', descriptionHtml: '', images: [], mainImagePath: null, status: 'OFFLINE',
        canPurchase: false, publishedAt: '2026-11-16T10:00:00', statusUpdatedAt: '2026-11-16T10:00:00',
        sellingMode: 'FIXED_PRICE',
      }))
      return
    }
    await route.fulfill(apiResponse({
      items: [{
        productId: 7, name: '零库存商品', price: 20, category2Id: 2, category2Name: '家居',
        stock: '0', descriptionHtml: '', images: [], mainImagePath: null, status: 'OFFLINE',
        canPurchase: false, publishedAt: '2026-11-16T10:00:00', statusUpdatedAt: '2026-11-16T10:00:00',
        sellingMode: 'FIXED_PRICE',
      }],
      page: 1, size: 100, total: 1, pages: 1,
    }))
  })
  await page.route('**/api/categories/tree', (route) =>
    route.fulfill(apiResponse([{ id: 1, name: '家居', children: [{ id: 2, name: '灯具', children: [] }] }])),
  )
  await page.route('**/api/admin/products/7/online', async (route) => {
    onlineRequests += 1
    await route.fulfill(apiResponse(null))
  })
  let archiveQuery: string | null = null
  await page.route('**/api/admin/legacy-intents?**', async (route) => {
    archiveQuery = new URL(route.request().url()).searchParams.get('customerId')
    await route.fulfill(apiResponse({ items: [], page: 1, size: 10, total: 0, pages: 0 }))
  })

  await page.goto('/admin/products/7/edit')
  await expect(page.getByText('库存恢复为正数不会自动上架')).toBeVisible()
  await page.getByLabel('库存数量').fill('3')
  await page.getByRole('button', { name: '保存库存和类目' }).click()
  await expect(page).toHaveURL('/admin/products')
  expect(onlineRequests).toBe(0)
  await page.goto('/admin/legacy-intents?customerId=17')
  await expect(page.getByRole('heading', { name: '旧意向归档' })).toBeVisible()
  await expect.poll(() => archiveQuery).toBe('17')
})

test('购物车下单与转收藏使用各自的默认选择规则', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  await page.route('**/api/me/cart', (route) =>
    route.fulfill(apiResponse({
      items: [
        {
          cartItemId: '21', productId: '11', productName: '库存充足商品', unitPrice: '10.00',
          mainImageUrl: null, quantity: '2', stock: '5', online: true, invalidLabel: null,
          defaultCheckoutSelected: true, canCheckoutSelect: true, canFavoriteSelect: true,
          updatedAt: '2026-11-16T10:00:00',
        },
        {
          cartItemId: '22', productId: '12', productName: '超库存商品', unitPrice: '15.00',
          mainImageUrl: null, quantity: '3', stock: '1', online: true, invalidLabel: null,
          defaultCheckoutSelected: false, canCheckoutSelect: true, canFavoriteSelect: true,
          updatedAt: '2026-11-16T10:00:00',
        },
      ],
    })),
  )

  await page.goto('/me/cart')
  await expect(page.getByLabel('选择库存充足商品')).toBeChecked()
  await expect(page.getByLabel('选择超库存商品')).not.toBeChecked()

  await page.getByText('转收藏选择', { exact: true }).click()
  await expect(page.getByLabel('选择库存充足商品')).toBeChecked()
  await expect(page.getByLabel('选择超库存商品')).toBeChecked()
  await page.getByRole('button', { name: '转为收藏' }).click()
  await expect(page.getByRole('dialog', { name: '确认转为收藏' })).toContainText('所选 2 件商品')
})

test('下单确认失败时保留勾选和未提交数量', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  await page.route('**/api/me/cart', (route) =>
    route.fulfill(apiResponse({
      items: [{
        cartItemId: '21', productId: '11', productName: '显示器', unitPrice: '10.00',
        mainImageUrl: null, quantity: '2', stock: '5', online: true, invalidLabel: null,
        defaultCheckoutSelected: true, canCheckoutSelect: true, canFavoriteSelect: true,
        updatedAt: '2026-11-16T10:00:00',
      }],
    })),
  )
  await page.route('**/api/me/checkout/confirmations', (route) =>
    route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 40910,
        message: '所选商品无法下单',
        data: {
          errors: [{
            cartItemId: '21',
            productId: '11',
            productName: '显示器',
            reason: 'INSUFFICIENT_STOCK',
            message: '商品「显示器」库存不足：当前可售 1 件，您选购了 2 件，请减少数量或移除后重试。',
            availableStock: '1',
            requestedQuantity: '2',
          }],
        },
      }),
    }),
  )

  await page.goto('/me/cart')
  await page.getByLabel('显示器数量').fill('4')
  await page.getByRole('button', { name: '下单' }).click()
  await expect(page.getByLabel('选择显示器')).toBeChecked()
  await expect(page.getByLabel('显示器数量')).toHaveValue('4')
  await expect(page.getByText('商品「显示器」库存不足：当前可售 1 件，您选购了 2 件，请减少数量或移除后重试。')).toBeVisible()
})

test('40913 后重新生成确认并使用新的幂等键', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  let confirmationRequests = 0
  const submitted: Array<{ token: string; key?: string }> = []
  await page.route('**/api/me/cart', (route) =>
    route.fulfill(apiResponse({
      items: [{
        cartItemId: '21', productId: '11', productName: '键盘', unitPrice: '10.00',
        mainImageUrl: null, quantity: '2', stock: '5', online: true, invalidLabel: null,
        defaultCheckoutSelected: true, canCheckoutSelect: true, canFavoriteSelect: true,
        updatedAt: '2026-11-16T10:00:00',
      }],
    })),
  )
  await page.route('**/api/me/checkout/confirmations', (route) => {
    confirmationRequests += 1
    const token = confirmationRequests === 1
      ? 'b6f90dc4-e989-4cd7-97d8-6f754dd40d1a'
      : 'c6f90dc4-e989-4cd7-97d8-6f754dd40d1a'
    const quantity = confirmationRequests === 1 ? '2' : '1'
    return route.fulfill(apiResponse({
      confirmationToken: token,
      items: [{
        cartItemId: '21', productId: '11', productName: '键盘', unitPrice: '10.00',
        quantity, lineAmount: `${quantity}0.00`,
      }],
      totalAmount: `${quantity}0.00`,
      createdAt: '2026-11-16T10:00:00',
    }))
  })
  await page.route('**/api/me/orders**', async (route) => {
    submitted.push({
      token: route.request().postDataJSON().confirmationToken,
      key: route.request().headers()['idempotency-key'],
    })
    if (submitted.length === 1) {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ code: 40913, message: '确认信息已变化，请重新确认', data: null }),
      })
      return
    }
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        code: 0,
        message: '下单成功',
        data: {
          orderId: '904', orderNo: 'OX-904', customerId: '17', status: 'PLACED',
          items: [{ productId: '11', productName: '键盘', unitPrice: '10.00', quantity: '1', lineAmount: '10.00' }],
          totalAmount: '10.00', createdAt: '2026-11-16T10:00:00', cancelledBy: null,
          cancelledAt: null, cancelReason: null, allowedActions: ['CANCEL'],
        },
      }),
    })
  })

  await page.goto('/me/cart')
  await page.getByRole('button', { name: '下单' }).click()
  await page.getByRole('button', { name: '确认下单' }).click()
  await expect.poll(() => confirmationRequests).toBe(2)
  await expect(page.getByRole('dialog', { name: '确认下单' })).toContainText('× 1')
  await page.getByRole('button', { name: '确认下单' }).click()
  await expect(page.getByRole('dialog', { name: '下单成功' })).toContainText('OX-904')
  expect(submitted[0].token).not.toBe(submitted[1].token)
  expect(submitted[0].key).not.toBe(submitted[1].key)
})

test('重复下单响应可跳转订单历史查找原单', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  await page.route('**/api/me/cart', (route) =>
    route.fulfill(apiResponse({
      items: [{
        cartItemId: '21', productId: '11', productName: '键盘', unitPrice: '10.00',
        mainImageUrl: null, quantity: '1', stock: '5', online: true, invalidLabel: null,
        defaultCheckoutSelected: true, canCheckoutSelect: true, canFavoriteSelect: true,
        updatedAt: '2026-11-16T10:00:00',
      }],
    })),
  )
  await page.route('**/api/me/checkout/confirmations', (route) =>
    route.fulfill(apiResponse({
      confirmationToken: 'b6f90dc4-e989-4cd7-97d8-6f754dd40d1a',
      items: [{
        cartItemId: '21', productId: '11', productName: '键盘', unitPrice: '10.00',
        quantity: '1', lineAmount: '10.00',
      }],
      totalAmount: '10.00',
      createdAt: '2026-11-16T10:00:00',
    })),
  )
  await page.route('**/api/me/orders**', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 40909,
          message: '订单已提交，请勿重复下单',
          data: { orderId: '904', orderNo: 'OX-904' },
        }),
      })
      return
    }
    await route.fulfill(apiResponse({
      items: [{
        orderId: '904', orderNo: 'OX-904', customerId: '17', status: 'PLACED',
        items: [{ productId: '11', productName: '键盘', unitPrice: '10.00', quantity: '1', lineAmount: '10.00' }],
        totalAmount: '10.00', createdAt: '2026-11-16T10:00:00', cancelledBy: null,
        cancelledAt: null, cancelReason: null, allowedActions: ['CANCEL'],
      }],
      page: 1, size: 10, total: 1, pages: 1,
    }))
  })

  await page.goto('/me/cart')
  await page.getByRole('button', { name: '下单' }).click()
  await page.getByRole('button', { name: '确认下单' }).click()
  await expect(page).toHaveURL('/me/order-history')
  await expect(page.getByText('OX-904')).toBeVisible()
})

test('大字符串商品 ID 从详情路由到加购请求不丢精度', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  let addedProductId: unknown
  await page.route('**/api/products/9007199254740993', (route) =>
    route.fulfill(apiResponse({
      productId: '9007199254740993',
      name: '大 ID 商品',
      descriptionHtml: '',
      price: 10,
      stock: '2',
      status: 'ONLINE',
      canPurchase: true,
      category2Id: 2,
      category2Name: '灯具',
      images: [],
      mainImagePath: null,
      publishedAt: '2026-11-16T10:00:00',
      statusUpdatedAt: '2026-11-16T10:00:00',
      sellingMode: 'FIXED_PRICE',
    })),
  )
  await page.route('**/api/me/favorites/9007199254740993', (route) =>
    route.fulfill(apiResponse({ favorited: false, createdAt: null })),
  )
  await page.route('**/api/me/cart/items', async (route) => {
    addedProductId = route.request().postDataJSON().productId
    await route.fulfill(apiResponse({ cartItemId: '21' }))
  })

  await page.goto('/products/9007199254740993')
  await page.getByRole('button', { name: '加入购物车' }).click()
  expect(addedProductId).toBe('9007199254740993')
})
