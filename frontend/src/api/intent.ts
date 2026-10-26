import { request } from './request'
import type { Intent } from '../types/intent'
import type { Page } from '../types/common'

export function getProductIntentQueue(productId: number, page = 1, size = 10) {
  return request<Page<Intent>>({
    url: '/admin/intents',
    method: 'GET',
    params: { productId, page, size },
  })
}

export function startTrade(intentId: number) {
  return request<void>({ url: `/admin/intents/${intentId}/start`, method: 'POST' })
}

export function confirmSuccess(intentId: number) {
  return request<void>({ url: `/admin/intents/${intentId}/success`, method: 'POST' })
}

export function confirmFail(intentId: number, action: 'REQUEUE' | 'DISCARD') {
  return request<void>({ url: `/admin/intents/${intentId}/fail`, method: 'POST', data: { action } })
}
