export type IntentStatus = 'QUEUING' | 'IN_TRANSACTION'

export interface Intent {
  id: number
  productId: number
  customerId: number
  customerUsername: string
  status: IntentStatus
  submittedAt: string
  position: number
}
