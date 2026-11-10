import type { AuctionStatus, SellingMode } from './product'

export interface AuctionRecentBid {
  bidSeq: number
  amount: number
  bidderAlias: string
  bidAt: string
}

export interface AuctionSnapshot {
  productId: number
  productName: string
  sellingMode: SellingMode
  auctionStatus: AuctionStatus
  startPrice: number
  minIncrement: number
  currentPrice: number
  nextMinBid: number
  bidCount: number
  endsAt: string
  settledAt: string | null
  serverTime: string
  leaderAlias: string | null
  lastBidSeq: number
  recentBids: AuctionRecentBid[]
  canBid: boolean
  myStatus: AuctionMyStatus | null
}

export type AuctionMyStatus = 'NONE' | 'LEADING' | 'OUTBID' | 'WON' | 'LOST'

export interface AuctionBidResponse {
  bidId: number
  auctionId: number
  bidSeq: number
  amount: number
  currentPrice: number
  nextMinBid: number
  bidCount: number
  leaderAlias?: string | null
  bidAt: string
}

export interface AuctionBidEvent {
  productId: number
  bidSeq: number
  amount: number
  currentPrice: number
  nextMinBid: number
  bidCount: number
  leaderAlias: string
  bidAt: string
  youAreLeading: boolean | null
}

export interface AuctionSettledEvent {
  productId: number
  auctionStatus: AuctionStatus
  finalPrice?: number
  settledAt?: string
  winnerAlias?: string | null
  youWon?: boolean | null
}

export type AuctionNotificationType = 'AUCTION_SOLD' | 'AUCTION_UNSOLD' | 'AUCTION_WON'

export interface AuctionNotification {
  notificationId: number
  auctionId: number
  productId: number
  type: AuctionNotificationType
  productName: string
  finalPrice: number | null
  createdAt: string
  readAt: string | null
}

export interface AuctionAdminItem {
  productId: number
  productName: string
  auctionStatus: AuctionStatus
  startPrice: number
  currentPrice: number | null
  bidCount: number
  endsAt: string
  settledAt: string | null
  winnerAlias: string | null
  winnerIntentId: number | null
}
