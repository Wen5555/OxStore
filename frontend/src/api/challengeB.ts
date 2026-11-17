import { request, requestWithMessage } from './request'
import type {
  Cart,
  CartItem,
  FavoritePage,
  FavoriteState,
  FavoriteWrite,
  LegacyPage,
  SetCartQuantityRequest,
} from '../types/challengeB'

function idempotencyKey() {
  return crypto.randomUUID()
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
    headers: { 'Idempotency-Key': idempotencyKey() },
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
