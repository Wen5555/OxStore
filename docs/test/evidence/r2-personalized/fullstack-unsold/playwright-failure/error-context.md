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
  - Expect "soft toBeVisible" getByText('本次拍卖流拍，无人中标。') with timeout 5000ms
  - waiting for getByText('本次拍卖流拍，无人中标。')

```

```yaml
- main:
  - img "暂无数据"
  - text: 商品当前不可查看
  - link "返回商品列表":
    - /url: /
```

```
Error: expect(locator).toBeDisabled() failed

Locator: getByRole('button', { name: /出\s*价/ })
Expected: disabled
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "soft toBeDisabled" getByRole('button', { name: /出\s*价/ }) with timeout 5000ms
  - waiting for getByRole('button', { name: /出\s*价/ })

```

```yaml
- main:
  - img "暂无数据"
  - text: 商品当前不可查看
  - link "返回商品列表":
    - /url: /
```

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('拍卖已结束，不能继续出价。')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "soft toBeVisible" getByText('拍卖已结束，不能继续出价。') with timeout 5000ms
  - waiting for getByText('拍卖已结束，不能继续出价。')

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
  77  |   await expect(page.getByText(/本次拍卖流拍，无人中标。|商品当前不可查看/)).toBeVisible({ timeout: 15_000 })
  78  |   await saveShot(page, 'ui', 'product_detail_unsold')
  79  |   // Keep the contracted copy as a real failure if the public detail 404s OFFLINE auctions.
  80  |   await expect.soft(page.getByText('本次拍卖流拍，无人中标。')).toBeVisible()
  81  |   await expect.soft(page.getByRole('button', { name: /出\s*价/ })).toBeDisabled()
> 82  |   await expect.soft(page.getByText('拍卖已结束，不能继续出价。')).toBeVisible()
      |                                                      ^ Error: expect(locator).toBeVisible() failed
  83  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  84  | 
  85  |   await page.goto('/admin/products')
  86  |   await expect(page.getByText(productName)).toBeVisible()
  87  |   await expect(page.getByText('已下架', { exact: true })).toBeVisible()
  88  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  89  |   await saveShot(page, 'ui', 'seller_products_offline')
  90  | 
  91  |   await page.goto('/admin/auction-notifications')
  92  |   await expect(page.getByText(productName)).toBeVisible()
  93  |   await expect(page.getByText(/拍卖流拍/)).toBeVisible()
  94  |   await expect(page.getByText(/拍卖已成交/)).toHaveCount(0)
  95  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  96  |   await expect(page.getByRole('button', { name: '查看商品' })).toBeVisible()
  97  |   await saveShot(page, 'ui', 'seller_notification_unsold')
  98  |   const firstCount = await page.getByText(/拍卖流拍/).count()
  99  |   expect(firstCount).toBe(1)
  100 | 
  101 |   await page.waitForTimeout(12_000)
  102 |   await page.goto('/admin/auction-notifications')
  103 |   await expect(page.getByText(/拍卖流拍/)).toHaveCount(1)
  104 |   await expect(page.getByText(/拍卖已成交/)).toHaveCount(0)
  105 |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  106 |   await saveShot(page, 'ui', 'seller_notification_after_repeat_scan')
  107 | 
  108 |   const token = await page.evaluate(() => localStorage.getItem('seller_token'))
  109 |   const headers = { Authorization: `Bearer ${token}` }
  110 |   const listing = await page.request.get('/api/admin/auctions?page=1&size=20', { headers })
  111 |   expect(listing.ok()).toBeTruthy()
  112 |   const listingJson = await listing.json()
  113 |   const item = (listingJson.data?.items ?? []).find((row: { productName: string }) => row.productName === productName)
  114 |   expect(item, 'admin auction list should contain the unsold product').toBeTruthy()
  115 |   expect(item.auctionStatus).toBe('ENDED_UNSOLD')
  116 |   expect(item.winnerIntentId ?? null).toBeNull()
  117 |   expect(item.winnerAlias ?? null).toBeNull()
  118 |   expect(item.bidCount).toBe(0)
  119 |   expect(item.currentPrice ?? null).toBeNull()
  120 | 
  121 |   const snapshot = await page.request.get(`/api/products/${item.productId}/auction`)
  122 |   expect(snapshot.ok()).toBeTruthy()
  123 |   const snap = (await snapshot.json()).data
  124 |   expect(snap.auctionStatus).toBe('ENDED_UNSOLD')
  125 |   expect(snap.bidCount).toBe(0)
  126 |   expect(snap.currentPrice ?? null).toBeNull()
  127 |   expect(snap.leaderAlias ?? null).toBeNull()
  128 | 
  129 |   const reminders = await page.request.get('/api/admin/auction-notifications?page=1&size=20', { headers })
  130 |   expect(reminders.ok()).toBeTruthy()
  131 |   const notes = ((await reminders.json()).data?.items ?? []).filter(
  132 |     (row: { productId: number }) => row.productId === item.productId)
  133 |   expect(notes).toHaveLength(1)
  134 |   expect(notes[0].type).toBe('AUCTION_UNSOLD')
  135 |   expect(notes[0].finalPrice ?? null).toBeNull()
  136 | 
  137 |   const sidecar = {
  138 |     productId: item.productId,
  139 |     auctionStatus: item.auctionStatus,
  140 |     bidCount: item.bidCount,
  141 |     winnerIntentId: item.winnerIntentId ?? null,
  142 |     notificationCount: notes.length,
  143 |     notificationType: notes[0].type,
  144 |   }
  145 |   fs.writeFileSync(path.join(evidenceDir(), 'playwright-api.json'), `${JSON.stringify(sidecar, null, 2)}\n`)
  146 | })
  147 | 
```