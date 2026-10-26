import { request } from './request'

export interface LoginResult {
  token: string
  userId: number
  role: 'CUSTOMER' | 'SELLER'
  username: string
}

export function register(data: { username: string; password: string; phone: string; location?: string }) {
  return request<{ customerId: number; username: string; phone: string; location: string | null }>({
    url: '/auth/register',
    method: 'POST',
    data,
  })
}

export function login(data: { username: string; password: string }) {
  return request<LoginResult>({ url: '/auth/login', method: 'POST', data })
}

export function sellerLogin(data: { username: string; password: string }) {
  return request<LoginResult>({ url: '/admin/auth/login', method: 'POST', data })
}

export function changePassword(data: { oldPassword: string; newPassword: string }) {
  return request<void>({ url: '/admin/auth/password', method: 'PUT', data })
}
