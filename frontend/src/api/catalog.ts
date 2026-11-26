import { request } from './request'
import type { CategoryTreeItem, Page } from '../types/common'
import { mapProductDetail, mapProductSummary, type ProductDetailResponse, type ProductSummaryResponse } from '../types/product'

export function getCategoryTree() {
  return request<CategoryTreeItem[]>({ url: '/categories/tree', method: 'GET' })
}

export function getProducts(params: { category2Id?: number; q?: string; page: number; size: number }) {
  return request<Page<ProductSummaryResponse>>({ url: '/products', method: 'GET', params })
    .then((page) => ({ ...page, items: page.items.map(mapProductSummary) }))
}

export function getProduct(productId: string | number) {
  return request<ProductDetailResponse>({ url: `/products/${encodeURIComponent(String(productId))}`, method: 'GET' })
    .then(mapProductDetail)
}

export function getMyOrderHistory(page: number, size: number) {
  return request<Page<import('../types/common').OrderHistoryItem>>({
    url: '/me/order-history',
    method: 'GET',
    params: { page, size },
  })
}
