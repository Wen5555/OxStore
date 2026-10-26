import { request } from './request'
import type { Customer, OrderHistoryItem, Page } from '../types/common'
import { mapProductDetail, type ProductDetailResponse } from '../types/product'

export async function getAdminProducts(page: number, size: number) {
  const result = await request<Page<ProductDetailResponse>>({ url: '/admin/products', method: 'GET', params: { page, size } })
  return { ...result, items: result.items.map(mapProductDetail) }
}

export async function getAdminProduct(productId: number) {
  const firstPage = await getAdminProducts(1, 100)
  const firstMatch = firstPage.items.find((product) => product.id === productId)
  if (firstMatch) return firstMatch
  for (let page = 2; page <= firstPage.pages; page += 1) {
    const result = await getAdminProducts(page, 100)
    const match = result.items.find((product) => product.id === productId)
    if (match) return match
  }
  throw new Error('商品不存在')
}

export function createProduct(data: FormData) {
  return request<ProductDetailResponse>({ url: '/admin/products', method: 'POST', data }).then(mapProductDetail)
}

export function updateProduct(productId: number, data: { stock?: number; category2Id?: number }) {
  return request<ProductDetailResponse>({ url: `/admin/products/${productId}`, method: 'PATCH', data }).then(mapProductDetail)
}

export function setProductOffline(productId: number) {
  return request<ProductDetailResponse>({ url: `/admin/products/${productId}/offline`, method: 'POST' }).then(mapProductDetail)
}

export function setProductOnline(productId: number) {
  return request<ProductDetailResponse>({ url: `/admin/products/${productId}/online`, method: 'POST' }).then(mapProductDetail)
}

export function getAdminCustomers(page: number, size: number) {
  return request<Page<Customer>>({ url: '/admin/customers', method: 'GET', params: { page, size } })
}

export function getCustomerOrderHistory(customerId: number, page: number, size: number) {
  return request<Page<OrderHistoryItem>>({
    url: `/admin/customers/${customerId}/order-history`,
    method: 'GET',
    params: { page, size },
  })
}
