import { expect, test, type Page } from '@playwright/test'
import { saveShot } from './evidence'

const adminUser = process.env.OXSTORE_ADMIN_USERNAME || 'admin'
const adminPassword = process.env.OXSTORE_ADMIN_PASSWORD || ''
const buyerPassword = process.env.OXSTORE_BUYER_PASSWORD || 'customer-pass-8'
const productName = process.env.OXSTORE_AUCTION_NAME || ''
const buyerAName = process.env.OXSTORE_BUYER_A || ''
const buyerBName = process.env.OXSTORE_BUYER_B || ''

test.beforeEach(() => {
  test.skip(!process.env.OXSTORE_FULLSTACK, '真实全栈未启动；mock 通过不可算全链路通过')
  test.skip(!productName || !adminPassword || !buyerAName || !buyerBName, '缺少全栈种子账号或拍品')
})

async function sellerLogin(page: Page) {
  await page.goto('/admin/login')
  await page.getByLabel('账号').fill(adminUser)
  await page.getByLabel('密码').fill(adminPassword)
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await expect(page.getByText('OxStore 卖家后台')).toBeVisible()
}

async function buyerLogin(page: Page, username: string) {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码').fill(buyerPassword)
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await expect(page.getByRole('button', { name: /我的账户/ })).toBeVisible()
}

test('真实全栈：买家竞价/OUTBID/SSE、卖家结果与结拍提醒', async ({ browser }) => {
  test.setTimeout(180_000)
  const seller = await browser.newPage()
  const buyerA = await browser.newPage()
  const buyerB = await browser.newPage()

  try {
    await sellerLogin(seller)
    await seller.getByRole('button', { name: '拍卖管理' }).click()
    await expect(seller.getByText(productName)).toBeVisible()
    await saveShot(seller, 'p-a16', 'fullstack_seller_live_list')

    await buyerLogin(buyerA, buyerAName)
    await buyerA.getByText(productName).first().click()
    await expect(buyerA.getByRole('button', { name: /出\s*价/ })).toBeEnabled()
    await buyerA.getByRole('spinbutton').fill('10')
    await buyerA.getByRole('button', { name: /出\s*价/ }).click()
    await expect(buyerA.getByText('出价成功')).toBeVisible({ timeout: 20_000 })
    await expect(buyerA.getByText('当前领先', { exact: true })).toBeVisible()
    await saveShot(buyerA, 'p-a15', 'fullstack_buyer_a_leading')

    await buyerLogin(buyerB, buyerBName)
    await buyerB.getByText(productName).first().click()
    await expect(buyerB.getByText('出价次数：1')).toBeVisible()
    await buyerB.getByRole('spinbutton').fill('12')
    await buyerB.getByRole('button', { name: /出\s*价/ }).click()
    await expect(buyerB.getByText('出价成功')).toBeVisible({ timeout: 20_000 })
    await expect(buyerA.getByText('出价次数：2')).toBeVisible({ timeout: 15_000 })
    await expect(buyerA.getByText(/当前领先者：/)).toBeVisible()
    await saveShot(buyerA, 'p-a15', 'fullstack_buyer_a_after_b_bid_sse_price')
    await saveShot(buyerB, 'p-a15', 'fullstack_buyer_b_leading')
    // Soft: keep collecting P-A16 settlement evidence even if OUTBID tag does not update.
    await expect.soft(buyerA.getByText('已被超越', { exact: true })).toBeVisible({ timeout: 8_000 })
    await saveShot(buyerA, 'p-a15', 'fullstack_buyer_a_outbid_sse')

    await expect(async () => {
      await seller.goto('/admin/auctions')
      await expect(seller.getByRole('button', { name: '处理履约' })).toBeVisible()
    }).toPass({ timeout: 120_000 })
    await saveShot(seller, 'p-a16', 'fullstack_seller_sold')
    await seller.getByRole('button', { name: '处理履约' }).click()
    await expect(seller.getByText('已结拍，中标人已进入交易中')).toBeVisible()
    await saveShot(seller, 'p-a16', 'fullstack_seller_fulfillment')

    await buyerB.goto('/me/auction-notifications')
    await expect(buyerB.getByText(/恭喜你中标/)).toBeVisible({ timeout: 20_000 })
    await expect(buyerB.getByText(productName).first()).toBeVisible()
    await saveShot(buyerB, 'p-a15', 'fullstack_buyer_won_notification')
  } finally {
    await Promise.allSettled([seller.close(), buyerA.close(), buyerB.close()])
  }
})
