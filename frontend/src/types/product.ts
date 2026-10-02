import type { Intent } from './intent'

export type ProductStatus = 'ONLINE' | 'RESTORED_ONLINE' | 'FROZEN' | 'SOLD'
export type FreezeSource = 'MANUAL' | 'TRADE'

export interface Product {
  id: number
  name: string
  description: string
  imagePath: string
  price: number
  status: ProductStatus
  freezeSource: FreezeSource | null
  publishedAt: string
  soldAt: string | null
  statusUpdatedAt: string | null
}

export interface TradeAttempt {
  id: number
  intentId: number
  startedAt: string
  finishedAt: string | null
  result: 'SUCCESS' | 'FAILED' | null
  failAction: 'REQUEUE' | 'DISCARD' | null
}

export interface ProductStatusEvent {
  id: number
  tradeAttemptId: number | null
  eventType: 'PUBLISHED' | 'MANUAL_FREEZE' | 'MANUAL_UNFREEZE' | 'TRADE_STARTED' | 'TRADE_FAILED' | 'TRADE_SUCCEEDED'
  fromStatus: ProductStatus | null
  toStatus: ProductStatus
  freezeSource: FreezeSource | null
  occurredAt: string
}

export interface ProductRecords {
  product: Product
  intents: Intent[]
  tradeAttempts: TradeAttempt[]
  statusEvents: ProductStatusEvent[]
  legacyRecordsMayBeIncomplete: boolean
  historyCompleteSince: string | null
}

export interface ProductHistoryDetail {
  product: Product
  intents: Intent[]
}
