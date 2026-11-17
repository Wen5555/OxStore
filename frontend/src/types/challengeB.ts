import type { Page } from './common'

export type BusinessId = string
export type PositiveIntegerString = string
export type NonNegativeIntegerString = string
export type MoneyString = string

export type OrderStatus =
  | 'PLACED'
  | 'CONFIRMED'
  | 'PREPARED'
  | 'SHIPPED'
  | 'COMPLETED'
  | 'CANCELLED'

export type OrderAction = 'CONFIRM' | 'PREPARE' | 'SHIP' | 'COMPLETE'
export type OrderAllowedAction = OrderAction | 'CANCEL'
export type CartItemErrorReason =
  | 'OFFLINE'
  | 'NOT_FOUND'
  | 'INSUFFICIENT_STOCK'
  | 'CART_ITEM_REMOVED'
  | 'CONFIRMATION_CHANGED'

export interface CartItemError {
  cartItemId: BusinessId
  productId?: BusinessId
  productName?: string
  reason: CartItemErrorReason
  message: string
  availableStock?: NonNegativeIntegerString
  requestedQuantity?: PositiveIntegerString
}

export interface CartItem {
  cartItemId: BusinessId
  productId: BusinessId
  productName: string
  unitPrice: MoneyString
  mainImageUrl: string | null
  quantity: PositiveIntegerString
  stock: NonNegativeIntegerString
  online: boolean
  invalidLabel: string | null
  defaultCheckoutSelected: boolean
  canCheckoutSelect: boolean
  canFavoriteSelect: boolean
  updatedAt: string
}

export interface Cart {
  items: CartItem[]
}

export interface FavoriteItem {
  favoriteId: BusinessId
  productId: BusinessId
  productName: string
  unitPrice: MoneyString
  mainImageUrl: string | null
  createdAt: string
  valid: boolean
  invalidLabel: string | null
  canOpenDetail: boolean
}

export interface FavoriteState {
  favorited: boolean
  createdAt: string | null
}

export interface FavoriteWrite {
  favoriteId: BusinessId
  productId: BusinessId
  createdAt: string
}

export interface OrderItem {
  productId: BusinessId
  productName: string
  unitPrice: MoneyString
  quantity: PositiveIntegerString
  lineAmount: MoneyString
}

export interface Order {
  orderId: BusinessId
  orderNo: string
  customerId: BusinessId
  status: OrderStatus
  items: OrderItem[]
  totalAmount: MoneyString
  createdAt: string
  cancelledBy: 'CUSTOMER' | 'SELLER' | null
  cancelledAt: string | null
  cancelReason: string | null
  allowedActions: OrderAllowedAction[]
}

export interface ConfirmationItem extends OrderItem {
  cartItemId: BusinessId
}

export interface CheckoutConfirmation {
  confirmationToken: string
  items: ConfirmationItem[]
  totalAmount: MoneyString
  createdAt: string
}

export interface MoveToFavoritesResult {
  movedLineCount: number
  movedCartItemIds: BusinessId[]
  skippedDeletedCartItemIds: BusinessId[]
}

export interface LegacyRecord {
  legacyIntentId: BusinessId
  productId: BusinessId
  productNameSnapshot: string
  originalStatus: string
  submittedAt: string
  processedAt: string | null
  closedAt: string | null
  displayStatus: string
  readOnly: true
}

export type OrderPage = Page<Order>
export type FavoritePage = Page<FavoriteItem>
export type LegacyPage = Page<LegacyRecord>

export interface AddCartItemRequest {
  productId: BusinessId
}

export interface SetCartQuantityRequest {
  quantity: NonNegativeIntegerString
}

export interface SelectCartRequest {
  cartItemIds: BusinessId[]
}

export interface SubmitOrderRequest {
  confirmationToken: string
}

export interface CancelOrderRequest {
  expectedStatus: OrderStatus
  reason?: string
}

export interface OrderActionRequest {
  expectedStatus: OrderStatus
  action: OrderAction
}
