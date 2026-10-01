export type IntentStatus =
  | 'QUEUING'
  | 'IN_TRANSACTION'
  | 'SUCCESS'
  | 'FAILED'
  | 'CANCELLED'
  | 'UNSOLD'

export interface Intent {
  id: number
  productId: number
  buyerName: string
  buyerPhone: string
  status: IntentStatus
  submittedAt: string
  position: number | null
  processedAt: string | null
  currentTradeAttemptId: number | null
}
