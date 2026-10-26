export type IntentStatus = 'QUEUING' | 'IN_TRANSACTION'

export interface Intent {
  intentId: number
  productId: number
  customerId: number | null
  username: string
  phone: string
  status: IntentStatus
  submittedAt: string
  position: number
}
