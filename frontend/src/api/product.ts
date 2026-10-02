import { request } from './request'
import type { Product, ProductHistoryDetail, ProductRecords } from '../types/product'
import type { Page } from '../types/common'
// 获取当前商品（在售/冻结/无商品）
export function getCurrentProduct() {
  return request<Product | null>({ url: '/products/current', method: 'GET' })
}

// 发布商品（multipart）
export function publishProduct(data: FormData) {
  return request<Product>({ url: '/admin/products', method: 'POST', data })
}

// 查看当前商品（后台）
export function getAdminCurrentProduct() {
  return request<Product | null>({ url: '/admin/products/current', method: 'GET' })
}

// 历史商品列表
export function getProductHistory(page: number, size: number) {
  return request<Page<Product>>({
    url: '/admin/products/history',
    method: 'GET',
    params: { page, size },
  })
}
// 任意状态商品的卖家专用记录
export function getProductRecords(id: number) {
  return request<ProductRecords>({ url: `/admin/products/${id}/records`, method: 'GET' })
}
// 仅已售商品历史详情
export function getProductHistoryDetail(id: number) {
  return request<ProductHistoryDetail>({ url: `/admin/products/history/${id}`, method: 'GET' })
}
// 手动冻结
export function freezeProduct() {
  return request<void>({ url: '/admin/products/current/freeze', method: 'POST' })
}

// 手动解冻
export function unfreezeProduct() {
  return request<void>({ url: '/admin/products/current/unfreeze', method: 'POST' })
}
