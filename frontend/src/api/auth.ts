import { request } from './request'

export interface LoginResult {
  token: string
  username: string
}

export function login(data: { username: string; password: string }) {
  return request<LoginResult>({ url: '/admin/auth/login', method: 'POST', data })
}

export function changePassword(data: { oldPassword: string; newPassword: string }) {
  return request<void>({ url: '/admin/auth/password', method: 'PUT', data })
}
