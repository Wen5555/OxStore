import { request, requestWithMessage } from './request'
import type { Order, OrderAction, OrderStatus, OrderPage } from '../types/challengeB'

export function getMyOrders(page: number, size: number) {
  return request<OrderPage>({ url: '/me/orders', method: 'GET', params: { page, size } })
}

export function getMyOrder(orderId: string) {
  return request<Order>({ url: `/me/orders/${encodeURIComponent(orderId)}`, method: 'GET' })
}

export function cancelMyOrder(orderId: string, expectedStatus: OrderStatus, reason?: string) {
  return requestWithMessage<Order>({
    url: `/me/orders/${encodeURIComponent(orderId)}/cancel`,
    method: 'POST',
    data: { expectedStatus, ...(reason?.trim() ? { reason: reason.trim() } : {}) },
  })
}

export function getAdminOrders(page: number, size: number) {
  return request<OrderPage>({ url: '/admin/orders', method: 'GET', params: { page, size } })
}

export function getAdminOrder(orderId: string) {
  return request<Order>({ url: `/admin/orders/${encodeURIComponent(orderId)}`, method: 'GET' })
}

export function advanceAdminOrder(orderId: string, action: OrderAction, expectedStatus: OrderStatus) {
  return request<Order>({
    url: `/admin/orders/${encodeURIComponent(orderId)}/actions`,
    method: 'POST',
    data: { action, expectedStatus },
  })
}

export function cancelAdminOrder(orderId: string, expectedStatus: OrderStatus, reason?: string) {
  return requestWithMessage<Order>({
    url: `/admin/orders/${encodeURIComponent(orderId)}/cancel`,
    method: 'POST',
    data: { expectedStatus, ...(reason?.trim() ? { reason: reason.trim() } : {}) },
  })
}
