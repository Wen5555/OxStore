import { expect, test } from '@playwright/test'
import { saveShot } from './evidence'

const apiResponse = (data: unknown, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify({ code: 0, message: 'ok', data }),
})

test('卖家发布页可选拍卖模式并提交拍卖字段', async ({ page }) => {
  const published: string[] = []
  await page.addInitScript(() => localStorage.setItem('seller_token', 'seller-token'))
  await page.route('**/api/categories/tree', (route) =>
    route.fulfill(apiResponse([{ id: 1, name: '家居', children: [{ id: 2, name: '灯具', children: [] }] }])),
  )
  await page.route('**/api/admin/products', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fulfill(apiResponse({ items: [], page: 1, size: 10, total: 0, pages: 0 }))
      return
    }
    published.push(route.request().postData() ?? '')
    await route.fulfill(apiResponse({
      productId: 501,
      name: '卖家拍卖商品',
      sellingMode: 'AUCTION',
      status: 'ONLINE',
      price: 10,
      stock: 1,
    }, 201))
  })

  await page.goto('/admin/products/publish')
  await expect(page.getByText('普通在售')).toBeVisible()
  await page.getByRole('radio', { name: '拍卖' }).check()
  await expect(page.getByText('最低加价幅度')).toBeVisible()
  await expect(page.getByText('竞价截止时间')).toBeVisible()
  await saveShot(page, 'p-a16', 'seller_publish_auction_fields')

  await page.getByLabel('商品名称').fill('卖家拍卖商品')
  await page.getByLabel('价格').fill('10')
  await page.getByLabel('二级类目').click()
  await page.locator('.ant-cascader-menu-item').filter({ hasText: '家居' }).click()
  await page.locator('.ant-cascader-menu-item').filter({ hasText: '灯具' }).click()
  await page.getByLabel('最低加价幅度').fill('2')
  await page.getByRole('button', { name: '发布商品', exact: true }).click()
  await expect(page.getByText('请选择竞价截止时间')).toBeVisible()
  expect(published).toHaveLength(0)
  await saveShot(page, 'p-a16', 'seller_publish_requires_deadline')
})

test('卖家拍卖管理展示成交履约入口与流拍', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('seller_token', 'seller-token'))
  await page.route('**/api/admin/auctions**', (route) =>
    route.fulfill(apiResponse({
      items: [
        {
          productId: 88,
          productName: '成交拍品',
          auctionStatus: 'ENDED_SOLD',
          startPrice: 10,
          currentPrice: 16,
          bidCount: 3,
          endsAt: '2026-11-09T12:00:00',
          settledAt: '2026-11-09T12:00:02',
          winnerAlias: 'b***r',
          winnerIntentId: 701,
        },
        {
          productId: 91,
          productName: '流拍拍品',
          auctionStatus: 'ENDED_UNSOLD',
          startPrice: 8,
          currentPrice: null,
          bidCount: 0,
          endsAt: '2026-11-09T12:05:00',
          settledAt: '2026-11-09T12:05:03',
          winnerAlias: null,
          winnerIntentId: null,
        },
      ],
      page: 1, size: 10, total: 2, pages: 1,
    })),
  )

  await page.goto('/admin/auctions')
  await expect(page.getByRole('cell', { name: '成交拍品' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '已成交' })).toBeVisible()
  await expect(page.getByRole('button', { name: '处理履约' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '流拍拍品' })).toBeVisible()
  await expect(page.getByRole('cell', { name: '已流拍' })).toBeVisible()
  await saveShot(page, 'p-a16', 'seller_auction_results_and_unsold')
  await page.getByRole('button', { name: '处理履约' }).click()
  await expect(page).toHaveURL(/\/admin\/products\/88\/intents$/)
})

test('卖家提醒区分成交履约与流拍查看入口', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('seller_token', 'seller-token'))
  await page.route('**/api/admin/auction-notifications?**', (route) =>
    route.fulfill(apiResponse({
      items: [
        {
          notificationId: 1,
          auctionId: 88,
          productId: 88,
          type: 'AUCTION_SOLD',
          productName: '成交拍品',
          finalPrice: 16,
          createdAt: '2026-11-09T12:00:02',
          readAt: null,
        },
        {
          notificationId: 2,
          auctionId: 91,
          productId: 91,
          type: 'AUCTION_UNSOLD',
          productName: '流拍拍品',
          finalPrice: null,
          createdAt: '2026-11-09T12:05:03',
          readAt: null,
        },
      ],
      page: 1, size: 10, total: 2, pages: 1, unread: 2,
    })),
  )
  await page.route('**/api/admin/auction-notifications/stream', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: ': ping\n\n' }),
  )

  await page.goto('/admin/auction-notifications')
  await expect(page.getByText('拍卖已成交，成交价 ¥16.00')).toBeVisible()
  await expect(page.getByText('拍卖流拍')).toBeVisible()
  await expect(page.getByRole('button', { name: '处理履约' })).toBeVisible()
  await expect(page.getByRole('button', { name: '查看商品' })).toBeVisible()
  await saveShot(page, 'p-a16', 'seller_notifications_sold_and_unsold')
  await page.getByRole('button', { name: '处理履约' }).click()
  await expect(page).toHaveURL(/\/admin\/products\/88\/intents$/)
})

test('卖家履约页对拍卖中标意向隐藏重新排队并展示流拍状态', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('seller_token', 'seller-token'))
  await page.route('**/api/admin/products?**', (route) =>
    route.fulfill(apiResponse({
      items: [{
        productId: 88,
        name: '成交拍品',
        price: 16,
        stock: 1,
        status: 'FROZEN',
        sellingMode: 'AUCTION',
        category2Id: 2,
        category2Name: '灯具',
        canPurchase: false,
        descriptionHtml: '',
        images: [],
        mainImagePath: null,
        publishedAt: '2026-11-09T10:00:00',
        statusUpdatedAt: '2026-11-09T12:00:02',
        auction: { auctionStatus: 'ENDED_SOLD', currentPrice: 16, nextMinBid: 18, endsAt: '2026-11-09T12:00:00', bidCount: 3 },
      }],
      page: 1, size: 100, total: 1, pages: 1,
    })),
  )
  await page.route('**/api/admin/intents**', (route) =>
    route.fulfill(apiResponse({
      items: [{
        intentId: 701,
        productId: 88,
        customerId: 17,
        username: '中标买家',
        phone: '13800000000',
        status: 'IN_TRANSACTION',
        submittedAt: '2026-11-09T12:00:02',
        position: 0,
      }],
      page: 1, size: 10, total: 1, pages: 1,
    })),
  )
  await page.route('**/api/products/88/auction', (route) =>
    route.fulfill(apiResponse({
      productId: 88, productName: '成交拍品', sellingMode: 'AUCTION', auctionStatus: 'ENDED_SOLD',
      startPrice: 10, minIncrement: 2, currentPrice: 16, nextMinBid: 18, bidCount: 3,
      endsAt: '2026-11-09T12:00:00', settledAt: '2026-11-09T12:00:02', serverTime: '2026-11-09T12:01:00',
      leaderAlias: 'b***r', lastBidSeq: 3, recentBids: [], canBid: false, myStatus: null,
    })),
  )
  await page.route('**/api/products/88/auction/stream', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: ': ping\n\n' }),
  )

  await page.goto('/admin/products/88/intents')
  await expect(page.getByText('已结拍，中标人已进入交易中')).toBeVisible()
  await expect(page.getByText('中标买家')).toBeVisible()
  await expect(page.getByRole('button', { name: '确认成功' })).toBeVisible()
  await expect(page.getByRole('button', { name: '失败并作废' })).toBeVisible()
  await expect(page.getByRole('button', { name: '失败并重新排队' })).toHaveCount(0)
  await saveShot(page, 'p-a16', 'seller_fulfillment_entry_no_requeue')
})
