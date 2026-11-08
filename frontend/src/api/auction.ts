import { request } from './request'
import type { AuctionAdminItem, AuctionNotification, AuctionSnapshot, AuctionBidResponse } from '../types/auction'
import type { Page } from '../types/common'

export function getAuctionSnapshot(productId: number) {
  return request<AuctionSnapshot>({ url: `/products/${productId}/auction`, method: 'GET' })
}

export function placeBid(productId: number, amount: number) {
  return request<AuctionBidResponse>({
    url: `/products/${productId}/auction/bids`,
    method: 'POST',
    data: { amount },
  })
}

export function getCustomerAuctionNotifications(page = 1, size = 10) {
  return request<Page<AuctionNotification>>({
    url: '/me/auction-notifications',
    method: 'GET',
    params: { page, size },
  })
}

export function markCustomerAuctionNotificationRead(notificationId: number) {
  return request<void>({ url: `/me/auction-notifications/${notificationId}/read`, method: 'POST' })
}

export function getSellerAuctionNotifications(page = 1, size = 10) {
  return request<Page<AuctionNotification>>({
    url: '/admin/auction-notifications',
    method: 'GET',
    params: { page, size },
  })
}

export function markSellerAuctionNotificationRead(notificationId: number) {
  return request<void>({ url: `/admin/auction-notifications/${notificationId}/read`, method: 'POST' })
}

export function getAdminAuctions(params: { status?: string; page?: number; size?: number } = {}) {
  return request<Page<AuctionAdminItem>>({
    url: '/admin/auctions',
    method: 'GET',
    params,
  })
}
