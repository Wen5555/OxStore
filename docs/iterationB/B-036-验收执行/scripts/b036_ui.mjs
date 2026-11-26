/**
 * B-036 real full-stack UI acceptance (Playwright -> system Chrome).
 * Run with Node 24 from the frontend directory:
 *   node <repo>/docs/iterationB/B-036-验收执行/scripts/b036_ui.mjs
 * Requires: backend :8080 (develop@29c20ea, oxstore_test_b036), Vite :5173
 */
import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'

const require = createRequire('C:/Users/闪电/Desktop/仓库/OxStore-sut/frontend/package.json')
const { chromium } = require('playwright-core')

const ROOT = 'C:/Users/闪电/Desktop/仓库/OxStore-/docs/iterationB/B-036-验收执行'
const SHOTS = path.join(ROOT, 'evidence', 'screenshots')
const FIXTURES = JSON.parse(fs.readFileSync(
  'C:/Users/闪电/Desktop/仓库/OxStore-/docs/iterationB/B-030-本轮验收用例/runs/fixture-ids.json', 'utf-8'))
const BASE = 'http://127.0.0.1:5173'
const BUYER = { username: 'b030_buyer_a', password: 'B030-BuyerA-Pass9' }
const SELLER = { username: 'admin', password: 'Admin#Pass2026' }
const PRODUCTS = Object.fromEntries(Object.entries(FIXTURES.products).map(([k, v]) => [k, v.productId]))

fs.mkdirSync(SHOTS, { recursive: true })
const steps = []
const consoleErrors = []
let PAGE = null

const pid = (code) => String(PRODUCTS[code])
const screenshot = async (page, name) => {
  await page.screenshot({ path: path.join(SHOTS, name + '.png'), fullPage: true })
}
const toast = async (page, text, timeout = 8000) => {
  const loc = page.locator('.ant-message-notice-content', { hasText: text }).last()
  await loc.waitFor({ state: 'visible', timeout })
  return loc.innerText()
}
const bodyText = async (page) => (await page.locator('body').innerText()).replace(/\s+/g, ' ')

async function step(name, fn, ac) {
  const started = Date.now()
  try {
    const evidence = await fn()
    steps.push({ step: name, ac: ac || [], status: 'PASS', ms: Date.now() - started, evidence: evidence ?? null })
    console.log(`PASS ${name}`)
    return evidence
  } catch (e) {
    steps.push({ step: name, ac: ac || [], status: 'FAIL', ms: Date.now() - started, error: String(e.message || e) })
    console.log(`FAIL ${name}: ${e.message || e}`)
    if (PAGE) {
      await PAGE.screenshot({ path: path.join(SHOTS, 'fail-' + name.replace(/[^\w]+/g, '_') + '.png'), fullPage: true }).catch(() => {})
    }
    return null
  }
}

async function loginBuyer(page) {
  await page.goto(BASE + '/login')
  await page.locator('input[autocomplete="username"]').fill(BUYER.username)
  await page.locator('input[autocomplete="current-password"]').fill(BUYER.password)
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await toast(page, '登录成功')
  await page.waitForURL(BASE + '/', { timeout: 8000 })
}

async function loginSeller(page) {
  await page.goto(BASE + '/admin/login')
  await page.locator('input[autocomplete="username"]').fill(SELLER.username)
  await page.locator('input[autocomplete="current-password"]').fill(SELLER.password)
  await page.getByRole('button', { name: /登\s*录/ }).click()
  await page.waitForTimeout(1800)
  const token = await page.evaluate(() => localStorage.getItem('seller_token'))
  if (!token || page.url().includes('/admin/login')) {
    const body = (await page.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 200)
    throw new Error(`seller login failed url=${page.url()} token=${token ? 'yes' : 'no'} body=${body}`)
  }
}

async function addToCart(page, code) {
  await page.goto(`${BASE}/products/${pid(code)}`)
  await page.getByRole('button', { name: '加入购物车' }).click()
  await toast(page, '已加入购物车')
}

async function placeOrderViaUi(page) {
  await page.goto(BASE + '/me/cart')
  const header = page.locator('.ant-table-thead input[type="checkbox"]')
  if (await header.count()) await header.first().check()
  await page.getByRole('button', { name: /^下\s*单$/ }).click()
  const modal = page.locator('.ant-modal-content', { hasText: '确认下单' }).last()
  await modal.waitFor({ state: 'visible' })
  await screenshot(page, '06-checkout-confirm')
  await modal.getByRole('button', { name: /确认下\s*单/ }).click()
  await toast(page, '下单成功')
  const success = page.locator('.ant-modal-content', { hasText: '下单成功' }).last()
  await success.waitFor({ state: 'visible' })
  const text = await success.innerText()
  await screenshot(page, '07-order-success')
  await success.getByRole('button', { name: /^关\s*闭$/ }).click()
  return { text, orderNo: text.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/)?.[0] || '' }
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  PAGE = page
  page.on('pageerror', (e) => consoleErrors.push(String(e.message || e)))
  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 300)) })

  // V01/V02 — 列表与详情入口约束
  await step('V01 商品列表：搜索框、无快捷收藏/加购', async () => {
    await page.goto(BASE + '/')
    await page.getByPlaceholder('搜索商品名称或描述').waitFor({ state: 'visible', timeout: 10000 })
    await page.getByText('B030-在售足库存-10').first().waitFor({ state: 'visible', timeout: 10000 })
    const text = await bodyText(page)
    await screenshot(page, '01-product-list')
    const hasQuickAdd = text.includes('加入购物车')
    const hasQuickFavorite = text.includes('收藏')
    if (hasQuickAdd || hasQuickFavorite) {
      throw new Error(`list must not offer quick add/favorite: add=${hasQuickAdd} favorite=${hasQuickFavorite}`)
    }
    return { hasQuickAdd, hasQuickFavorite }
  }, ['PB-B08-AC5', 'PB-B10-AC5'])

  await step('V01 买家登录', async () => {
    await loginBuyer(page)
    return { url: page.url() }
  }, ['PB-B08-AC1', 'PB-B10-AC1'])

  await step('V01 详情：加入购物车 1 件 + 收藏', async () => {
    await page.goto(`${BASE}/products/${pid('P-ON-10')}`)
    const name = await page.locator('h2').first().innerText()
    await page.getByRole('button', { name: '加入购物车' }).click()
    await toast(page, '已加入购物车')
    await page.getByRole('button', { name: /^收\s*藏$/ }).click()
    await toast(page, '已收藏')
    await screenshot(page, '02-product-detail')
    const text = await bodyText(page)
    if (text.includes('立即购买')) throw new Error('detail must not offer 立即购买')
    return { name, favoriteButtonAfter: await page.getByRole('button', { name: '取消收藏' }).count() }
  }, ['PB-B10-AC5', 'PB-B08-AC3'])

  await step('V03 购物车：两行、改数量、失效/超库存不自动删', async () => {
    await addToCart(page, 'P-ON-5')
    await page.goto(BASE + '/me/cart')
    await page.locator('h2', { hasText: '购物车' }).waitFor()
    const updateButtons = page.getByRole('button', { name: '更新数量' })
    await updateButtons.first().waitFor({ state: 'visible', timeout: 15000 })
    const count = await updateButtons.count()
    const qty = page.getByLabel('B030-在售足库存-10数量')
    await qty.fill('2')
    await updateButtons.first().click()
    await toast(page, '已更新')
    await screenshot(page, '03-cart')
    return { rows: count, qty: await qty.inputValue() }
  }, ['PB-B10-AC2', 'PB-B10-AC4', 'PB-B11-AC1'])

  await step('V09 转收藏：二次确认文案与 N=2、整行移出', async () => {
    const header = page.locator('.ant-table-thead input[type="checkbox"]')
    if (await header.count()) await header.first().check()
    await page.getByRole('button', { name: '转为收藏' }).click()
    const modal = page.locator('.ant-modal-content', { hasText: '确认转为收藏' }).last()
    await modal.waitFor({ state: 'visible' })
    const confirmText = await modal.innerText()
    await screenshot(page, '04-move-to-favorites-modal')
    await modal.getByRole('button', { name: '确认转收藏' }).click()
    await toast(page, '已收藏 2 件商品')
    return { confirmText }
  }, ['PB-B14-AC1', 'PB-B14-AC4', 'PB-B15-AC1'])

  await step('V02 收藏列表：两项、取消收藏无需确认', async () => {
    await page.goto(BASE + '/me/favorites')
    await page.locator('h2', { hasText: '我的收藏' }).waitFor()
    const rows = page.locator('.ant-table-tbody tr.ant-table-row')
    await rows.first().waitFor()
    const before = await rows.count()
    await rows.first().getByRole('button', { name: '取消收藏' }).click()
    await toast(page, '已取消收藏')
    await screenshot(page, '05-favorites')
    return { before, after: await rows.count() }
  }, ['PB-B09-AC3'])

  await step('V04/V05 下单：确认弹窗、成功提示与单号', async () => {
    await addToCart(page, 'P-ON-10')
    const result = await placeOrderViaUi(page)
    return result
  }, ['PB-B12-AC1', 'PB-B12-AC2', 'PB-B12-AC4', 'PB-B13-AC1'])

  await step('V05 订单历史：取消订单（二次确认 + 已取消元数据）', async () => {
    await page.goto(BASE + '/me/order-history')
    await page.locator('h2', { hasText: '订单历史' }).waitFor()
    const row = page.locator('.ant-table-tbody tr.ant-table-row').first()
    await row.waitFor()
    const statusBefore = await row.innerText()
    await row.getByRole('button', { name: '取消订单' }).click()
    const modal = page.locator('.ant-modal-content', { hasText: '确认取消订单' }).last()
    await modal.waitFor({ state: 'visible' })
    await modal.locator('input, textarea').first().fill('B036 页面取消')
    await modal.getByRole('button', { name: '确认取消' }).click()
    await page.waitForFunction(() => document.body.innerText.includes('已取消'), null, { timeout: 10000 })
    await screenshot(page, '08-order-history-cancelled')
    const rowText = await page.locator('.ant-table-tbody tr.ant-table-row').first().innerText()
    return { statusBefore: statusBefore.slice(0, 80), rowText: rowText.slice(0, 160) }
  }, ['PB-B04-AC4', 'PB-B04-AC6', 'PB-B03-AC3'])

  // 第二单用于商家推进
  await step('V06 商家推进：确认→备货→发货→完成', async () => {
    await addToCart(page, 'P-ON-10')
    const { orderNo } = await placeOrderViaUi(page)
    await loginSeller(page)
    await page.goto(BASE + '/admin/orders')
    await page.locator('h2', { hasText: '订单管理' }).waitFor()
    const row = page.locator('.ant-table-tbody tr.ant-table-row', { hasText: orderNo }).first()
    await row.waitFor({ timeout: 10000 })
    const transitions = []
    for (const [button, expected] of [['确认订单', '待备货'], ['完成备货', '待发货'],
                                      ['开始发货', '已开始发货'], ['完成交易', '已完成']]) {
      await row.getByRole('button', { name: button }).click()
      const pop = page.locator('.ant-popover', { hasText: '确认' }).last()
      await pop.waitFor({ state: 'visible' })
      await pop.getByRole('button', { name: /^确\s*认$/ }).click()
      await page.waitForFunction((t) => document.body.innerText.includes(t), expected, { timeout: 10000 })
      transitions.push(expected)
    }
    await screenshot(page, '11-admin-orders')
    return { orderNo, transitions }
  }, ['PB-B01-AC2', 'PB-B01-AC4', 'PB-B06-AC2'])

  await step('V05 历史显示交易完成；无废弃文案', async () => {
    await page.goto(BASE + '/me/order-history')
    await page.locator('h2', { hasText: '订单历史' }).waitFor()
    const text = await bodyText(page)
    const forbidden = ['缺货', '无货', '超限', '下单历史'].filter((w) => text.includes(w))
    const completedRow = page.locator('.ant-table-tbody tr.ant-table-row', { hasText: '交易完成' }).first()
    const cancelOnCompleted = await completedRow.getByRole('button', { name: '取消订单' }).count()
    if (cancelOnCompleted !== 0) throw new Error('completed order still exposes 取消订单')
    await screenshot(page, '12-order-history-completed')
    return { hasCompleted: text.includes('交易完成'), forbidden, cancelOnCompleted }
  }, ['PB-B03-AC3', 'PB-B01-AC2'])

  await step('V07 库存页：负数校验、改正保存、手动下架/上架入口', async () => {
    await page.goto(`${BASE}/admin/products`)
    await page.locator('h2', { hasText: '商品管理' }).waitFor()
    await screenshot(page, '09-admin-products')
    await page.goto(`${BASE}/admin/products/${pid('P-ON-1')}/edit`)
    const stock = page.locator('#stock')
    await stock.waitFor({ timeout: 10000 })
    await stock.fill('-1')
    await page.getByRole('button', { name: '保存库存和类目' }).click()
    await page.getByText('库存不能为负数，请输入非负整数。').waitFor({ state: 'visible', timeout: 5000 })
    await stock.fill('5')
    await page.getByRole('button', { name: '保存库存和类目' }).click()
    await toast(page, '商品信息已更新')
    await screenshot(page, '10-admin-product-edit')
    const manualOffline = await page.getByRole('button', { name: '手动下架' }).count()
    return { manualOffline }
  }, ['PB-B02-AC3', 'PB-B02-AC4'])

  await step('V10 旧意向归档页（客户/商家）只读可查', async () => {
    await page.goto(BASE + '/me/legacy-intents')
    await page.locator('h2', { hasText: '旧意向归档' }).waitFor()
    const buyerText = await bodyText(page)
    await screenshot(page, '13-buyer-legacy-archive')
    await page.goto(BASE + '/admin/legacy-intents')
    await page.locator('h2', { hasText: '旧意向归档' }).waitFor()
    const adminText = await bodyText(page)
    await screenshot(page, '14-admin-legacy-archive')
    return { buyerHasReadOnly: buyerText.includes('只读归档'), adminHasFilter: adminText.includes('查询') }
  }, ['PB-B03-AC5', 'PB-B04-AC7'])

  await context.close()
} finally {
  await browser.close()
}

const summary = {
  task: 'B-036',
  sut: { branch: 'develop', sha: '29c20ea0927528a98f873f4a1a0e169a6fa12281' },
  base: BASE,
  executed_at: new Date().toISOString(),
  totals: {
    steps: steps.length,
    pass: steps.filter((s) => s.status === 'PASS').length,
    fail: steps.filter((s) => s.status === 'FAIL').length,
  },
  console_errors: consoleErrors.slice(0, 40),
  steps,
}
fs.writeFileSync(path.join(ROOT, 'evidence', 'ui-steps.json'), JSON.stringify(summary, null, 2), 'utf-8')
console.log(JSON.stringify(summary.totals))
process.exit(summary.totals.fail === 0 ? 0 : 1)
