import { expect, test } from '@playwright/test'
import { saveShot } from './evidence'

const apiResponse = (data: unknown, status = 200) => ({
  status,
  contentType: 'application/json',
  body: JSON.stringify({ code: 0, message: 'ok', data }),
})

const liveSnapshot = {
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
  leaderAlias: 'a***r',
  lastBidSeq: 1,
  recentBids: [{ bidSeq: 1, amount: 10, bidderAlias: 'a***r', bidAt: '2026-11-09T10:59:00' }],
  canBid: true,
  myStatus: 'LEADING',
}

function productDetail(id = 88, extras: Record<string, unknown> = {}) {
  return {
    productId: id,
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
    ...extras,
  }
}

test('买家出价后快照同步，被超越时显示 OUTBID', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  let snapshot = { ...liveSnapshot, myStatus: 'LEADING', canBid: true }
  await page.route('**/api/products/88', (route) => route.fulfill(apiResponse(productDetail())))
  await page.route('**/api/products/88/auction/stream', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: `event: snapshot\ndata: ${JSON.stringify(snapshot)}\n\n` }),
  )
  await page.route('**/api/products/88/auction/bids', async (route) => {
    snapshot = {
      ...snapshot,
      currentPrice: 12,
      nextMinBid: 14,
      bidCount: 2,
      lastBidSeq: 2,
      leaderAlias: 'b***r',
      myStatus: 'LEADING',
    }
    await route.fulfill(apiResponse({
      bidId: 2, auctionId: 9, bidSeq: 2, amount: 12, currentPrice: 12, nextMinBid: 14, bidCount: 2,
      bidAt: '2026-11-09T11:01:00',
    }, 201))
  })
  await page.route('**/api/products/88/auction', (route) => route.fulfill(apiResponse(snapshot)))

  await page.goto('/products/88')
  await expect(page.getByText('当前领先', { exact: true })).toBeVisible()
  await page.getByRole('spinbutton').fill('12')
  await page.getByRole('button', { name: /出\s*价/ }).click()
  await expect(page.getByText('出价次数：2')).toBeVisible()
  await saveShot(page, 'p-a15', 'buyer_bid_leading')

  snapshot = { ...snapshot, myStatus: 'OUTBID', leaderAlias: 'c***z', canBid: true }
  await page.reload()
  await expect(page.getByText('已被超越', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /出\s*价/ })).toBeEnabled()
  await saveShot(page, 'p-a15', 'buyer_outbid')
})

test('SSE 断流后重拉快照并继续接收出价事件', async ({ page }) => {
  test.setTimeout(20_000)
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  let connections = 0
  let snapshotRequests = 0
  const first = { ...liveSnapshot }
  const afterReconnect = {
    ...liveSnapshot,
    currentPrice: 12,
    nextMinBid: 14,
    bidCount: 2,
    lastBidSeq: 2,
    leaderAlias: 'b***r',
    myStatus: 'OUTBID',
  }
  const bid = {
    productId: 88, bidSeq: 2, amount: 12, currentPrice: 12, nextMinBid: 14, bidCount: 2,
    leaderAlias: 'b***r', bidAt: '2026-11-09T11:02:00', youAreLeading: false,
  }
  await page.route('**/api/products/88', (route) => route.fulfill(apiResponse(productDetail())))
  await page.route('**/api/products/88/auction', async (route) => {
    snapshotRequests += 1
    await route.fulfill(apiResponse(snapshotRequests === 1 ? first : afterReconnect))
  })
  await page.route('**/api/products/88/auction/stream', async (route) => {
    connections += 1
    if (connections === 1) {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `event: snapshot\ndata: ${JSON.stringify(first)}\n\n`,
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        `event: snapshot\ndata: ${JSON.stringify(afterReconnect)}\n\n`,
        `event: bid\nid: 2\ndata: ${JSON.stringify(bid)}\n\n`,
      ].join(''),
    })
  })

  await page.goto('/products/88')
  await expect(page.getByText('出价次数：1')).toBeVisible()
  await expect.poll(() => connections, { timeout: 12_000 }).toBeGreaterThanOrEqual(2)
  await expect.poll(() => snapshotRequests).toBeGreaterThanOrEqual(2)
  await expect(page.getByText('出价次数：2')).toBeVisible()
  await expect(page.getByText('已被超越', { exact: true })).toBeVisible()
  await saveShot(page, 'p-a15', 'sse_reconnect_snapshot')
})

test('截止或结拍后出价按钮禁用', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('customer_token', 'customer-token'))
  const settled = {
    ...liveSnapshot,
    auctionStatus: 'ENDED_UNSOLD',
    canBid: false,
    myStatus: 'NONE',
    currentPrice: null,
    bidCount: 0,
    lastBidSeq: 0,
    leaderAlias: null,
    recentBids: [],
  }
  await page.route('**/api/products/91', (route) =>
    route.fulfill(apiResponse(productDetail(91, { name: '流拍展示商品', productId: 91 }))),
  )
  await page.route('**/api/products/91/auction', (route) => route.fulfill(apiResponse({ ...settled, productId: 91, productName: '流拍展示商品' })))
  await page.route('**/api/products/91/auction/stream', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: `event: snapshot\ndata: ${JSON.stringify({ ...settled, productId: 91 })}\n\n`,
    }),
  )

  await page.goto('/products/91')
  await expect(page.getByText('本次拍卖流拍，无人中标。')).toBeVisible()
  await expect(page.getByRole('button', { name: /出\s*价/ })).toBeDisabled()
  await expect(page.getByText('拍卖已结束，不能继续出价。')).toBeVisible()
  await saveShot(page, 'p-a15', 'deadline_reject_unsold')
})

test('未登录点击出价会进入登录页，列表可区分拍卖商品', async ({ page }) => {
  await page.route('**/api/categories/tree', (route) =>
    route.fulfill(apiResponse([{ id: 1, name: '家居', children: [{ id: 2, name: '灯具', children: [] }] }])),
  )
  await page.route('**/api/products?**', (route) =>
    route.fulfill(apiResponse({
      items: [{
        productId: 88,
        name: '实时拍卖商品',
        price: 10,
        mainImagePath: null,
        category2Id: 2,
        category2Name: '灯具',
        sellingMode: 'AUCTION',
        auction: { auctionStatus: 'LIVE', currentPrice: 10, nextMinBid: 12, endsAt: '2026-11-09T12:00:00', bidCount: 1 },
      }],
      page: 1, size: 10, total: 1, pages: 1,
    })),
  )
  await page.route('**/api/products/88', (route) => route.fulfill(apiResponse(productDetail())))
  await page.route('**/api/products/88/auction', (route) =>
    route.fulfill(apiResponse({ ...liveSnapshot, canBid: false, myStatus: null })),
  )
  await page.route('**/api/products/88/auction/stream', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: `event: snapshot\ndata: ${JSON.stringify({ ...liveSnapshot, canBid: false, myStatus: null })}\n\n`,
    }),
  )

  await page.goto('/')
  await expect(page.getByText('当前最低出价：¥12.00')).toBeVisible()
  await expect(page.getByRole('button', { name: /登\s*录/ })).toBeVisible()
  await saveShot(page, 'p-a15', 'list_distinguishes_auction')
  await page.getByText('实时拍卖商品').first().click()
  await expect(page.getByText('请先登录后出价。')).toBeVisible()
  await expect(page.getByRole('button', { name: /出\s*价/ })).toBeDisabled()
  await saveShot(page, 'p-a15', 'unauth_bid_button_disabled')
  await page.goto('/')
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await expect(page).toHaveURL(/\/login$/)
  await saveShot(page, 'p-a15', 'unauth_header_login')
})
