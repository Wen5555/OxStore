# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: auction-r2-fullstack-unsold.spec.ts >> 真实全栈：无人出价经定时结拍流拍且重复扫描幂等
- Location: e2e/auction-r2-fullstack-unsold.spec.ts:35:1

# Error details

```
Error: locator.click: Error: strict mode violation: getByRole('button', { name: '发布商品' }) resolved to 2 elements:
    1) <button type="button" class="ant-btn css-dev-only-do-not-override-mncuj7 ant-btn-default ant-btn-color-default ant-btn-variant-outlined">…</button> aka getByRole('button', { name: 'upload 发布商品' })
    2) <button type="button" class="ant-btn css-dev-only-do-not-override-mncuj7 ant-btn-primary ant-btn-color-primary ant-btn-variant-solid">…</button> aka getByRole('button', { name: '发布商品', exact: true })

Call log:
  - waiting for getByRole('button', { name: '发布商品' })

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - strong [ref=e6]: OxStore 卖家后台
    - generic [ref=e7]:
      - button "shop 商品管理" [ref=e9] [cursor=pointer]:
        - img "shop" [ref=e11]
        - generic [ref=e14]: 商品管理
      - button "trophy 拍卖管理" [ref=e16] [cursor=pointer]:
        - img "trophy" [ref=e18]
        - generic [ref=e21]: 拍卖管理
      - button "upload 发布商品" [ref=e23] [cursor=pointer]:
        - img "upload" [ref=e25]
        - generic [ref=e28]: 发布商品
      - button "user 全部顾客" [ref=e30] [cursor=pointer]:
        - img "user" [ref=e32]
        - generic [ref=e35]: 全部顾客
      - button "lock 修改密码" [ref=e37] [cursor=pointer]:
        - img "lock" [ref=e39]
        - generic [ref=e42]: 修改密码
      - button "bell 拍卖提醒" [ref=e44] [cursor=pointer]:
        - img "bell" [ref=e46]
        - generic [ref=e49]: 拍卖提醒
  - main [ref=e50]:
    - main [ref=e51]:
      - generic [ref=e52]:
        - generic [ref=e54]:
          - heading "商品管理" [level=2] [ref=e55]
          - button "发布商品" [ref=e56] [cursor=pointer]
        - generic [ref=e61]:
          - img "暂无数据" [ref=e63]
          - generic [ref=e75]: 暂无商品
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
  29  |   await input.click()
  30  |   await page.keyboard.insertText(stamp)
  31  |   await page.keyboard.press('Enter')
  32  |   await page.keyboard.press('Escape')
  33  | }
  34  | 
  35  | test('真实全栈：无人出价经定时结拍流拍且重复扫描幂等', async ({ page }) => {
  36  |   test.setTimeout(180_000)
  37  |   await sellerLogin(page)
  38  | 
> 39  |   await page.getByRole('button', { name: '发布商品' }).click()
      |                                                    ^ Error: locator.click: Error: strict mode violation: getByRole('button', { name: '发布商品' }) resolved to 2 elements:
  40  |   await expect(page.getByText('普通在售')).toBeVisible()
  41  |   await page.getByRole('radio', { name: '拍卖' }).check()
  42  |   await expect(page.getByText('最低加价幅度')).toBeVisible()
  43  |   await page.getByLabel('商品名称').fill(productName)
  44  |   await page.getByLabel('价格').fill('10')
  45  |   await page.getByLabel('二级类目').click()
  46  |   await page.locator('.ant-cascader-menu-item').first().click()
  47  |   await page.locator('.ant-cascader-menu').nth(1).locator('.ant-cascader-menu-item').first().click()
  48  |   await page.getByLabel('最低加价幅度').fill('2')
  49  |   await fillDeadline(page, endsAtDisplay)
  50  |   await saveShot(page, 'ui', 'seller_publish_unsold_auction')
  51  |   await page.getByRole('button', { name: '发布商品', exact: true }).click()
  52  |   await expect(page.getByText('商品发布成功')).toBeVisible({ timeout: 20_000 })
  53  | 
  54  |   await page.getByRole('button', { name: '拍卖管理' }).click()
  55  |   await expect(page.getByText(productName)).toBeVisible()
  56  |   await expect(page.getByText('进行中', { exact: true })).toBeVisible()
  57  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  58  |   await saveShot(page, 'ui', 'seller_live_no_bids')
  59  | 
  60  |   await expect(async () => {
  61  |     await page.goto('/admin/auctions')
  62  |     await expect(page.getByText(productName)).toBeVisible()
  63  |     await expect(page.getByText('已流拍', { exact: true })).toBeVisible()
  64  |   }).toPass({ timeout: 120_000 })
  65  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  66  |   await expect(page.getByRole('button', { name: '查看商品' })).toBeVisible()
  67  |   await expect(page.getByText(productName)).toBeVisible()
  68  |   await saveShot(page, 'ui', 'seller_list_unsold')
  69  | 
  70  |   await page.getByRole('button', { name: '查看商品' }).click()
  71  |   await expect(page.getByText('本次拍卖流拍，无人中标。')).toBeVisible()
  72  |   await expect(page.getByRole('button', { name: /出\s*价/ })).toBeDisabled()
  73  |   await expect(page.getByText('拍卖已结束，不能继续出价。')).toBeVisible()
  74  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  75  |   await saveShot(page, 'ui', 'product_detail_unsold')
  76  | 
  77  |   await page.goto('/admin/auction-notifications')
  78  |   await expect(page.getByText(productName)).toBeVisible()
  79  |   await expect(page.getByText(/拍卖流拍/)).toBeVisible()
  80  |   await expect(page.getByText(/拍卖已成交/)).toHaveCount(0)
  81  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  82  |   await expect(page.getByRole('button', { name: '查看商品' })).toBeVisible()
  83  |   await saveShot(page, 'ui', 'seller_notification_unsold')
  84  |   const firstCount = await page.getByText(/拍卖流拍/).count()
  85  |   expect(firstCount).toBe(1)
  86  | 
  87  |   await page.waitForTimeout(12_000)
  88  |   await page.goto('/admin/auction-notifications')
  89  |   await expect(page.getByText(/拍卖流拍/)).toHaveCount(1)
  90  |   await expect(page.getByText(/拍卖已成交/)).toHaveCount(0)
  91  |   await expect(page.getByRole('button', { name: '处理履约' })).toHaveCount(0)
  92  |   await saveShot(page, 'ui', 'seller_notification_after_repeat_scan')
  93  | 
  94  |   const token = await page.evaluate(() => localStorage.getItem('seller_token'))
  95  |   const headers = { Authorization: `Bearer ${token}` }
  96  |   const listing = await page.request.get('/api/admin/auctions?page=1&size=20', { headers })
  97  |   expect(listing.ok()).toBeTruthy()
  98  |   const listingJson = await listing.json()
  99  |   const item = (listingJson.data?.items ?? []).find((row: { productName: string }) => row.productName === productName)
  100 |   expect(item, 'admin auction list should contain the unsold product').toBeTruthy()
  101 |   expect(item.auctionStatus).toBe('ENDED_UNSOLD')
  102 |   expect(item.winnerIntentId ?? null).toBeNull()
  103 |   expect(item.winnerAlias ?? null).toBeNull()
  104 |   expect(item.bidCount).toBe(0)
  105 |   expect(item.currentPrice ?? null).toBeNull()
  106 | 
  107 |   const snapshot = await page.request.get(`/api/products/${item.productId}/auction`)
  108 |   expect(snapshot.ok()).toBeTruthy()
  109 |   const snap = (await snapshot.json()).data
  110 |   expect(snap.auctionStatus).toBe('ENDED_UNSOLD')
  111 |   expect(snap.bidCount).toBe(0)
  112 |   expect(snap.currentPrice ?? null).toBeNull()
  113 |   expect(snap.leaderAlias ?? null).toBeNull()
  114 | 
  115 |   const reminders = await page.request.get('/api/admin/auction-notifications?page=1&size=20', { headers })
  116 |   expect(reminders.ok()).toBeTruthy()
  117 |   const notes = ((await reminders.json()).data?.items ?? []).filter(
  118 |     (row: { productId: number }) => row.productId === item.productId)
  119 |   expect(notes).toHaveLength(1)
  120 |   expect(notes[0].type).toBe('AUCTION_UNSOLD')
  121 |   expect(notes[0].finalPrice ?? null).toBeNull()
  122 | 
  123 |   const sidecar = {
  124 |     productId: item.productId,
  125 |     auctionStatus: item.auctionStatus,
  126 |     bidCount: item.bidCount,
  127 |     winnerIntentId: item.winnerIntentId ?? null,
  128 |     notificationCount: notes.length,
  129 |     notificationType: notes[0].type,
  130 |   }
  131 |   fs.writeFileSync(path.join(evidenceDir(), 'playwright-api.json'), `${JSON.stringify(sidecar, null, 2)}\n`)
  132 | })
  133 | 
```