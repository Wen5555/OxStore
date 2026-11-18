import { request, requestWithMessage } from './request'
import type {
  Cart,
  CartItem,
  FavoritePage,
  FavoriteState,
  FavoriteWrite,
  LegacyPage,
  CheckoutConfirmation,
  MoveToFavoritesResult,
  Order,
  SetCartQuantityRequest,
} from '../types/challengeB'

export function createIdempotencyKey() {
  if (typeof globalThis.crypto?.randomUUID === 'function') {
    return globalThis.crypto.randomUUID()
  }

  const bytes = new Uint8Array(16)
  if (typeof globalThis.crypto?.getRandomValues === 'function') {
    globalThis.crypto.getRandomValues(bytes)
  } else {
    for (let index = 0; index < bytes.length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 256)
    }
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80

  const hex = [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function getFavoriteState(productId: string | number) {
  return request<FavoriteState>({ url: `/me/favorites/${productId}`, method: 'GET' })
}

export function addFavorite(productId: string | number) {
  return requestWithMessage<FavoriteWrite>({ url: `/me/favorites/${productId}`, method: 'PUT' })
}

export function removeFavorite(productId: string | number) {
  return requestWithMessage<null>({ url: `/me/favorites/${productId}`, method: 'DELETE' })
}

export function getMyFavorites(page: number) {
  return request<FavoritePage>({ url: '/me/favorites', method: 'GET', params: { page, size: 10 } })
}

export function addCartItem(productId: string | number) {
  return requestWithMessage<CartItem>({
    url: '/me/cart/items',
    method: 'POST',
    data: { productId: String(productId) },
    headers: { 'Idempotency-Key': createIdempotencyKey() },
  })
}

export function getMyCart() {
  return request<Cart>({ url: '/me/cart', method: 'GET' })
}

export function setCartItemQuantity(cartItemId: string, quantity: SetCartQuantityRequest['quantity']) {
  return requestWithMessage<CartItem | null>({
    url: `/me/cart/items/${encodeURIComponent(cartItemId)}`,
    method: 'PATCH',
    data: { quantity },
  })
}

export function removeCartItem(cartItemId: string) {
  return requestWithMessage<null>({
    url: `/me/cart/items/${encodeURIComponent(cartItemId)}`,
    method: 'DELETE',
  })
}

export function clearMyCart() {
  return requestWithMessage<null>({ url: '/me/cart', method: 'DELETE' })
}

export function createCheckoutConfirmation(cartItemIds: string[]) {
  return request<CheckoutConfirmation>({
    url: '/me/checkout/confirmations',
    method: 'POST',
    data: { cartItemIds },
  })
}

export function submitMyOrder(confirmationToken: string, idempotencyKey: string) {
  return requestWithMessage<Order>({
    url: '/me/orders',
    method: 'POST',
    data: { confirmationToken },
    headers: { 'Idempotency-Key': idempotencyKey },
  })
}

export function moveCartItemsToFavorites(cartItemIds: string[], idempotencyKey: string) {
  return requestWithMessage<MoveToFavoritesResult>({
    url: '/me/cart/move-to-favorites',
    method: 'POST',
    data: { cartItemIds },
    headers: { 'Idempotency-Key': idempotencyKey },
  })
}

export function getMyLegacyIntents(page: number, size: number) {
  return request<LegacyPage>({ url: '/me/legacy-intents', method: 'GET', params: { page, size } })
}

export function getAdminLegacyIntents(
  page: number,
  size: number,
  filters: { productId?: string; customerId?: string },
) {
  return request<LegacyPage>({
    url: '/admin/legacy-intents',
    method: 'GET',
    params: {
      page,
      size,
      ...(filters.productId ? { productId: filters.productId } : {}),
      ...(filters.customerId ? { customerId: filters.customerId } : {}),
    },
  })
}
