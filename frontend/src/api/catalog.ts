import { request } from './request'
import type { CategoryTreeItem, Page } from '../types/common'
import type { Product } from '../types/product'

export function getCategoryTree() {
  return request<CategoryTreeItem[]>({ url: '/categories/tree', method: 'GET' })
}

export function getProducts(params: { category2Id?: number; q?: string; page: number; size: number }) {
  return request<Page<Product>>({ url: '/products', method: 'GET', params })
}

export function getProduct(productId: number) {
  return request<Product>({ url: `/products/${productId}`, method: 'GET' })
}

export function submitPurchaseIntent(productId: number) {
  return request<{ intentId: number; productId: number; status: 'QUEUING'; createdAt: string }>({
    url: `/products/${productId}/intents`,
    method: 'POST',
  })
}

export function getMyOrderHistory(page: number, size: number) {
  return request<Page<import('../types/common').OrderHistoryItem>>({
    url: '/me/order-history',
    method: 'GET',
    params: { page, size },
  })
}
