import { expect, test } from '@playwright/test'

const apiResponse = (data: unknown, message = 'ok') => ({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({ code: 0, message, data }),
})

type MockOrder = {
  orderId: string
  orderNo: string
  customerId: string
  status: string
  items: Array<{ productId: string; productName: string; unitPrice: string; quantity: string; lineAmount: string }>
  totalAmount: string
  createdAt: string
  cancelledBy: string | null
  cancelledAt: string | null
  cancelReason: string | null
  allowedActions: string[]
}

test('seller order page follows allowed actions, refreshes state and confirms cancellation', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('seller_token', 'seller-token'))
  const firstOrder: MockOrder = {
    orderId: '701',
    orderNo: 'OX-701',
    customerId: '17',
    status: 'PREPARED',
    items: [{ productId: '42', productName: '订单测试商品', unitPrice: '88.00', quantity: '1', lineAmount: '88.00' }],
    totalAmount: '88.00',
    createdAt: '2026-11-17T09:00:00',
    cancelledBy: null,
    cancelledAt: null,
    cancelReason: null,
    allowedActions: ['SHIP', 'CANCEL'],
  }
  const completedOrder = {
    ...firstOrder,
    orderId: '702',
    orderNo: 'OX-702',
    status: 'COMPLETED',
    allowedActions: [],
  }
  let actionRequest: { action: string; expectedStatus: string } | undefined
  let cancellationRequest: { expectedStatus: string; reason?: string } | undefined

  await page.route('**/api/admin/orders**', async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
    if (path.endsWith('/actions')) {
      actionRequest = route.request().postDataJSON()
      firstOrder.status = 'SHIPPED'
      firstOrder.allowedActions = ['COMPLETE', 'CANCEL']
      await route.fulfill(apiResponse(firstOrder))
      return
    }
    if (path.endsWith('/cancel')) {
      cancellationRequest = route.request().postDataJSON()
      firstOrder.status = 'CANCELLED'
      firstOrder.allowedActions = []
      firstOrder.cancelledBy = 'SELLER'
      firstOrder.cancelledAt = '2026-11-17T09:05:00'
      firstOrder.cancelReason = cancellationRequest?.reason ?? null
      await route.fulfill(apiResponse(firstOrder, '订单已取消'))
      return
    }
    if (path.endsWith('/701')) {
      await route.fulfill(apiResponse(firstOrder))
      return
    }
    if (path.endsWith('/702')) {
      await route.fulfill(apiResponse(completedOrder))
      return
    }
    await route.fulfill(apiResponse({
      items: [firstOrder, completedOrder],
      page: 1,
      size: 10,
      total: 2,
      pages: 1,
    }))
  })

  await page.goto('/admin/orders')
  const activeRow = page.getByRole('row').filter({ hasText: 'OX-701' })
  const completedRow = page.getByRole('row').filter({ hasText: 'OX-702' })
  await expect(activeRow.getByText('待发货')).toBeVisible()
  await expect(completedRow.getByText('已完成')).toBeVisible()
  await expect(completedRow.getByRole('button', { name: '取消订单' })).toHaveCount(0)
  await expect(completedRow.getByRole('button', { name: '完成交易' })).toHaveCount(0)

  await activeRow.getByRole('button', { name: '开始发货' }).click()
  await page.getByRole('button', { name: /确\s*认/ }).click()
  await expect(activeRow.getByText('已开始发货')).toBeVisible()
  expect(actionRequest).toEqual({ action: 'SHIP', expectedStatus: 'PREPARED' })

  await activeRow.getByRole('button', { name: '取消订单' }).click()
  await page.getByPlaceholder('取消原因（选填）').fill('库存核对后取消')
  await page.getByRole('button', { name: '确认取消' }).click()
  await expect(activeRow.getByText('已取消')).toBeVisible()
  await expect(activeRow.getByRole('button', { name: '取消订单' })).toHaveCount(0)
  expect(cancellationRequest).toEqual({ expectedStatus: 'SHIPPED', reason: '库存核对后取消' })

  await activeRow.getByRole('button', { name: '详情' }).click()
  const detailDialog = page.getByRole('dialog').filter({ hasText: '订单详情' })
  await expect(detailDialog.getByText('OX-701')).toBeVisible()
  await expect(detailDialog.getByText('库存核对后取消')).toBeVisible()
})
