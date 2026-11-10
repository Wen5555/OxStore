import { expect, test, type Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { evidenceDir, saveShot } from './evidence'

const adminUser = process.env.OXSTORE_ADMIN_USERNAME || 'admin'
const adminPassword = process.env.OXSTORE_ADMIN_PASSWORD || ''
const productName = process.env.OXSTORE_AUCTION_NAME || ''
const endsAtDisplay = process.env.OXSTORE_UNSOLD_ENDS_AT_DISPLAY || ''

test.beforeEach(() => {
  test.skip(!process.env.OXSTORE_FULLSTACK || !process.env.OXSTORE_UNSOLD,
    '真实全栈流拍未启动；mock 通过不可算全链路通过')
  test.skip(!productName || !adminPassword || !endsAtDisplay, '缺少流拍全栈商品名、卖家口令或截止时间')
})

async function sellerLogin(page: Page) {
  await page.goto('/admin/login')
  await page.getByLabel('账号').fill(adminUser)
  await page.getByLabel('密码').fill(adminPassword)
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await expect(page.getByText('OxStore 卖家后台')).toBeVisible()
}

async function fillDeadline(page: Page, stamp: string) {
  const picker = page.locator('.ant-picker').last()
  await picker.click()
  const input = picker.locator('input')
  await input.fill(stamp)
  const ok = page.locator('.ant-picker-ok button')
  if (await ok.isVisible()) {
    await ok.click()
  } else {
    await page.keyboard.press('Enter')
  }
  await page.keyboard.press('Escape')
  await expect(input).toHaveValue(stamp)
}

test('真实全栈：无人出价经定时结拍流拍且重复扫描幂等', async ({ page }) => {
  test.setTimeout(180_000)
  await sellerLogin(page)

  await page.goto('/admin/products')
  await page.getByRole('button', { name: '发布商品', exact: true }).click()
  await expect(page.getByText('普通在售')).toBeVisible()
  await page.getByRole('radio', { name: '拍卖' }).check()
  await expect(page.getByText('最低加价幅度')).toBeVisible()
  await page.getByLabel('商品名称').fill(productName)
  await page.getByLabel('价格').fill('10')
  await page.getByLabel('二级类目').click()
  await page.locator('.ant-cascader-menu-item').first().click()
  await page.locator('.ant-cascader-menu').nth(1).locator('.ant-cascader-menu-item').first().click()
  await page.getByLabel('最低加价幅度').fill('2')
  await fillDeadline(page, endsAtDisplay)
  await saveShot(page, 'ui', 'seller_publish_unsold_auction')
  await page.getByRole('button', { name: '发布商品', exact: true }).click()
  await expect(page.getByText('商品发布成功')).toBeVisible({ timeout: 20_000 })

  await page.getByRole('button', { name: '拍卖管理' }).click()
  await expect(page.getByText(productName)).toBeVisible()
  await expect(page.getByText('进行中', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  await saveShot(page, 'ui', 'seller_live_no_bids')

  await expect(async () => {
    await page.goto('/admin/auctions')
    await expect(page.getByText(productName)).toBeVisible()
    await expect(page.getByText('已流拍', { exact: true })).toBeVisible()
  }).toPass({ timeout: 120_000 })
  await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '查看商品' })).toBeVisible()
  await expect(page.getByText(productName)).toBeVisible()
  await saveShot(page, 'ui', 'seller_list_unsold')

  await page.getByRole('button', { name: '查看商品' }).click()
  await expect(page.getByText(/本次拍卖流拍，无人中标。|商品当前不可查看/)).toBeVisible({ timeout: 15_000 })
  await saveShot(page, 'ui', 'product_detail_unsold')
  // Keep the contracted copy as a real failure if the public detail 404s OFFLINE auctions.
  await expect.soft(page.getByText('本次拍卖流拍，无人中标。')).toBeVisible({ timeout: 2_000 })
  await expect.soft(page.getByRole('button', { name: /出\s*价/ })).toBeDisabled({ timeout: 2_000 })
  await expect.soft(page.getByText('拍卖已结束，不能继续出价。')).toBeVisible({ timeout: 2_000 })
  await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)

  await page.goto('/admin/products')
  await expect(page.getByText(productName)).toBeVisible()
  await expect(page.getByText('已下架', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  await saveShot(page, 'ui', 'seller_products_offline')

  await page.goto('/admin/auction-notifications')
  await expect(page.getByText(productName)).toBeVisible()
  await expect(page.getByText(/拍卖流拍/)).toBeVisible()
  await expect(page.getByText(/拍卖已成交/)).toHaveCount(0)
  await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '查看商品' })).toBeVisible()
  await saveShot(page, 'ui', 'seller_notification_unsold')
  const firstCount = await page.getByText(/拍卖流拍/).count()
  expect(firstCount).toBe(1)

  await page.waitForTimeout(12_000)
  await page.goto('/admin/auction-notifications')
  await expect(page.getByText(/拍卖流拍/)).toHaveCount(1)
  await expect(page.getByText(/拍卖已成交/)).toHaveCount(0)
  await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  await saveShot(page, 'ui', 'seller_notification_after_repeat_scan')

  const token = await page.evaluate(() => localStorage.getItem('seller_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const listing = await page.request.get('/api/admin/auctions?page=1&size=20', { headers })
  expect(listing.ok()).toBeTruthy()
  const listingJson = await listing.json()
  const item = (listingJson.data?.items ?? []).find((row: { productName: string }) => row.productName === productName)
  expect(item, 'admin auction list should contain the unsold product').toBeTruthy()
  expect(item.auctionStatus).toBe('ENDED_UNSOLD')
  expect(item.winnerIntentId ?? null).toBeNull()
  expect(item.winnerAlias ?? null).toBeNull()
  expect(item.bidCount).toBe(0)
  expect(item.currentPrice ?? null).toBeNull()

  const snapshot = await page.request.get(`/api/products/${item.productId}/auction`)
  expect(snapshot.ok()).toBeTruthy()
  const snap = (await snapshot.json()).data
  expect(snap.auctionStatus).toBe('ENDED_UNSOLD')
  expect(snap.bidCount).toBe(0)
  expect(snap.currentPrice ?? null).toBeNull()
  expect(snap.leaderAlias ?? null).toBeNull()

  const reminders = await page.request.get('/api/admin/auction-notifications?page=1&size=20', { headers })
  expect(reminders.ok()).toBeTruthy()
  const notes = ((await reminders.json()).data?.items ?? []).filter(
    (row: { productId: number }) => row.productId === item.productId)
  expect(notes).toHaveLength(1)
  expect(notes[0].type).toBe('AUCTION_UNSOLD')
  expect(notes[0].finalPrice ?? null).toBeNull()

  const sidecar = {
    productId: item.productId,
    auctionStatus: item.auctionStatus,
    bidCount: item.bidCount,
    winnerIntentId: item.winnerIntentId ?? null,
    notificationCount: notes.length,
    notificationType: notes[0].type,
  }
  fs.writeFileSync(path.join(evidenceDir(), 'playwright-api.json'), `${JSON.stringify(sidecar, null, 2)}\n`)
})
