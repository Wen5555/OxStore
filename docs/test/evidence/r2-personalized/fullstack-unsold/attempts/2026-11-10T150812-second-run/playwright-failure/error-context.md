# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: auction-r2-fullstack-unsold.spec.ts >> 真实全栈：无人出价经定时结拍流拍且重复扫描幂等
- Location: e2e/auction-r2-fullstack-unsold.spec.ts:40:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('本次拍卖流拍，无人中标。')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByText('本次拍卖流拍，无人中标。') with timeout 5000ms
  - waiting for getByText('本次拍卖流拍，无人中标。')

```

```yaml
- main:
  - img "暂无数据"
  - text: 商品当前不可查看
  - link "返回商品列表":
    - /url: /
```

# Test source

```ts
  1   | import { expect, test, type Page } from '@playwright/test'
  2   | import fs from 'node:fs'
  3   | import path from 'node:path'
  4   | import { evidenceDir, saveShot } from './evidence'
  5   | 
  6   | const adminUser = process.env.OXSTORE_ADMIN_USERNAME || 'admin'
  7   | const adminPassword = process.env.OXSTORE_ADMIN_PASSWORD || ''
  8   | const productName = process.env.OXSTORE_AUCTION_NAME || ''
  9   | const endsAtDisplay = process.env.OXSTORE_UNSOLD_ENDS_AT_DISPLAY || ''
  10  | 
  11  | test.beforeEach(() => {
  12  |   test.skip(!process.env.OXSTORE_FULLSTACK || !process.env.OXSTORE_UNSOLD,
  13  |     '真实全栈流拍未启动；mock 通过不可算全链路通过')
  14  |   test.skip(!productName || !adminPassword || !endsAtDisplay, '缺少流拍全栈商品名、卖家口令或截止时间')
  15  | })
  16  | 
  17  | async function sellerLogin(page: Page) {
  18  |   await page.goto('/admin/login')
  19  |   await page.getByLabel('账号').fill(adminUser)
  20  |   await page.getByLabel('密码').fill(adminPassword)
  21  |   await page.getByRole('button', { name: /登\s*录/ }).click()
  22  |   await expect(page.getByText('OxStore 卖家后台')).toBeVisible()
  23  | }
  24  | 
  25  | async function fillDeadline(page: Page, stamp: string) {
  26  |   const picker = page.locator('.ant-picker').last()
  27  |   await picker.click()
  28  |   const input = picker.locator('input')
  29  |   await input.fill(stamp)
  30  |   const ok = page.locator('.ant-picker-ok button')
  31  |   if (await ok.isVisible()) {
  32  |     await ok.click()
  33  |   } else {
  34  |     await page.keyboard.press('Enter')
  35  |   }
  36  |   await page.keyboard.press('Escape')
  37  |   await expect(input).toHaveValue(stamp)
  38  | }
  39  | 
  40  | test('真实全栈：无人出价经定时结拍流拍且重复扫描幂等', async ({ page }) => {
  41  |   test.setTimeout(180_000)
  42  |   await sellerLogin(page)
  43  | 
  44  |   await page.goto('/admin/products')
  45  |   await page.getByRole('button', { name: '发布商品', exact: true }).click()
  46  |   await expect(page.getByText('普通在售')).toBeVisible()
  47  |   await page.getByRole('radio', { name: '拍卖' }).check()
  48  |   await expect(page.getByText('最低加价幅度')).toBeVisible()
  49  |   await page.getByLabel('商品名称').fill(productName)
  50  |   await page.getByLabel('价格').fill('10')
  51  |   await page.getByLabel('二级类目').click()
  52  |   await page.locator('.ant-cascader-menu-item').first().click()
  53  |   await page.locator('.ant-cascader-menu').nth(1).locator('.ant-cascader-menu-item').first().click()
  54  |   await page.getByLabel('最低加价幅度').fill('2')
  55  |   await fillDeadline(page, endsAtDisplay)
  56  |   await saveShot(page, 'ui', 'seller_publish_unsold_auction')
  57  |   await page.getByRole('button', { name: '发布商品', exact: true }).click()
  58  |   await expect(page.getByText('商品发布成功')).toBeVisible({ timeout: 20_000 })
  59  | 
  60  |   await page.getByRole('button', { name: '拍卖管理' }).click()
  61  |   await expect(page.getByText(productName)).toBeVisible()
  62  |   await expect(page.getByText('进行中', { exact: true })).toBeVisible()
  63  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  64  |   await saveShot(page, 'ui', 'seller_live_no_bids')
  65  | 
  66  |   await expect(async () => {
  67  |     await page.goto('/admin/auctions')
  68  |     await expect(page.getByText(productName)).toBeVisible()
  69  |     await expect(page.getByText('已流拍', { exact: true })).toBeVisible()
  70  |   }).toPass({ timeout: 120_000 })
  71  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  72  |   await expect(page.getByRole('button', { name: '查看商品' })).toBeVisible()
  73  |   await expect(page.getByText(productName)).toBeVisible()
  74  |   await saveShot(page, 'ui', 'seller_list_unsold')
  75  | 
  76  |   await page.getByRole('button', { name: '查看商品' }).click()
> 77  |   await expect(page.getByText('本次拍卖流拍，无人中标。')).toBeVisible()
      |                                                ^ Error: expect(locator).toBeVisible() failed
  78  |   await expect(page.getByRole('button', { name: /出\s*价/ })).toBeDisabled()
  79  |   await expect(page.getByText('拍卖已结束，不能继续出价。')).toBeVisible()
  80  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  81  |   await saveShot(page, 'ui', 'product_detail_unsold')
  82  | 
  83  |   await page.goto('/admin/auction-notifications')
  84  |   await expect(page.getByText(productName)).toBeVisible()
  85  |   await expect(page.getByText(/拍卖流拍/)).toBeVisible()
  86  |   await expect(page.getByText(/拍卖已成交/)).toHaveCount(0)
  87  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  88  |   await expect(page.getByRole('button', { name: '查看商品' })).toBeVisible()
  89  |   await saveShot(page, 'ui', 'seller_notification_unsold')
  90  |   const firstCount = await page.getByText(/拍卖流拍/).count()
  91  |   expect(firstCount).toBe(1)
  92  | 
  93  |   await page.waitForTimeout(12_000)
  94  |   await page.goto('/admin/auction-notifications')
  95  |   await expect(page.getByText(/拍卖流拍/)).toHaveCount(1)
  96  |   await expect(page.getByText(/拍卖已成交/)).toHaveCount(0)
  97  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  98  |   await saveShot(page, 'ui', 'seller_notification_after_repeat_scan')
  99  | 
  100 |   const token = await page.evaluate(() => localStorage.getItem('seller_token'))
  101 |   const headers = { Authorization: `Bearer ${token}` }
  102 |   const listing = await page.request.get('/api/admin/auctions?page=1&size=20', { headers })
  103 |   expect(listing.ok()).toBeTruthy()
  104 |   const listingJson = await listing.json()
  105 |   const item = (listingJson.data?.items ?? []).find((row: { productName: string }) => row.productName === productName)
  106 |   expect(item, 'admin auction list should contain the unsold product').toBeTruthy()
  107 |   expect(item.auctionStatus).toBe('ENDED_UNSOLD')
  108 |   expect(item.winnerIntentId ?? null).toBeNull()
  109 |   expect(item.winnerAlias ?? null).toBeNull()
  110 |   expect(item.bidCount).toBe(0)
  111 |   expect(item.currentPrice ?? null).toBeNull()
  112 | 
  113 |   const snapshot = await page.request.get(`/api/products/${item.productId}/auction`)
  114 |   expect(snapshot.ok()).toBeTruthy()
  115 |   const snap = (await snapshot.json()).data
  116 |   expect(snap.auctionStatus).toBe('ENDED_UNSOLD')
  117 |   expect(snap.bidCount).toBe(0)
  118 |   expect(snap.currentPrice ?? null).toBeNull()
  119 |   expect(snap.leaderAlias ?? null).toBeNull()
  120 | 
  121 |   const reminders = await page.request.get('/api/admin/auction-notifications?page=1&size=20', { headers })
  122 |   expect(reminders.ok()).toBeTruthy()
  123 |   const notes = ((await reminders.json()).data?.items ?? []).filter(
  124 |     (row: { productId: number }) => row.productId === item.productId)
  125 |   expect(notes).toHaveLength(1)
  126 |   expect(notes[0].type).toBe('AUCTION_UNSOLD')
  127 |   expect(notes[0].finalPrice ?? null).toBeNull()
  128 | 
  129 |   const sidecar = {
  130 |     productId: item.productId,
  131 |     auctionStatus: item.auctionStatus,
  132 |     bidCount: item.bidCount,
  133 |     winnerIntentId: item.winnerIntentId ?? null,
  134 |     notificationCount: notes.length,
  135 |     notificationType: notes[0].type,
  136 |   }
  137 |   fs.writeFileSync(path.join(evidenceDir(), 'playwright-api.json'), `${JSON.stringify(sidecar, null, 2)}\n`)
  138 | })
  139 | 
```