import axios, { AxiosError, type AxiosRequestConfig } from 'axios'
import { message } from 'antd'
import type { CartItemError } from '../types/challengeB'
import type { ApiResponse } from '../types/common'

const cartItemErrorReasons = new Set<string>([
  'OFFLINE',
  'NOT_FOUND',
  'INSUFFICIENT_STOCK',
  'CART_ITEM_REMOVED',
  'CONFIRMATION_CHANGED',
])

export class ApiError extends Error {
  public readonly itemErrors: CartItemError[]

  constructor(
    public readonly code: number | undefined,
    messageText: string,
    public readonly traceId?: string,
    public readonly data?: unknown,
  ) {
    super(messageText)
    this.name = 'ApiError'
    this.itemErrors = getCartItemErrors(data)
  }
}

function getCartItemErrors(data: unknown): CartItemError[] {
  if (!data || typeof data !== 'object' || !('errors' in data) || !Array.isArray(data.errors)) return []
  return data.errors.filter((item): item is CartItemError => {
    if (!item || typeof item !== 'object') return false
    return 'cartItemId' in item
      && typeof item.cartItemId === 'string'
      && 'reason' in item
      && typeof item.reason === 'string'
      && cartItemErrorReasons.has(item.reason)
      && 'message' in item
      && typeof item.message === 'string'
  })
}

function isChallengeBRequest(url?: string) {
  const path = url?.replace(/^\/api(?=\/)/, '').split('?')[0] ?? ''
  return path.startsWith('/me/')
    || /^\/admin\/(orders|legacy-intents)(\/|$)/.test(path)
    || /^\/admin\/products(\/|$)/.test(path)
}

function apiErrorMessage(code: number | undefined, fallback: string, url?: string) {
  if (code === 40903 && url === '/auth/register') return '用户名已存在，请更换用户名。'
  switch (code) {
    case 40001: return '请检查必填字段和输入格式。'
    case 40002: return '请求格式无效，请检查输入后重试。'
    case 40003: return '分页参数无效，请刷新页面后重试。'
    case 40101: return '登录状态已失效，请重新登录。'
    case 40102: return '用户名或密码错误。'
    case 40302: return '当前账号无权执行此操作。'
    case 40401:
    case 40402:
    case 40403:
    case 40404: return '请求的商品、类目、意向或顾客不存在。'
    case 40901: return '请求与当前数据状态冲突，请刷新后重试。'
    case 40902: return '该意向已不是队首或已有交易处理中，请刷新队列。'
    case 40903: return '用户名已存在，请更换用户名。'
    case 40906: return '拍卖已截止或已结拍，不能继续出价。'
    case 40907: return fallback || '出价低于当前最低可出价。'
    case 40908: return '当前商品不支持此操作。'
    case 41301: return '图片不能超过 5MB。'
    case 41501: return '图片格式仅支持 JPG、PNG。'
    case 42201: return '商品描述包含不支持的内容，请修改后重试。'
    case 50000: return '服务暂时不可用，请稍后重试。'
    default: return fallback
  }
}

function errorMessage(code: number | undefined, fallback: string, url?: string) {
  const isMappedAuctionError = [40906, 40907, 40908].includes(code ?? 0)
    && /\/auction(s)?(\/|$)/.test(url?.split('?')[0] ?? '')
  if (isChallengeBRequest(url) && !isMappedAuctionError) return fallback
  return apiErrorMessage(code, fallback, url)
}

function currentPath() {
  return `${window.location.pathname}${window.location.search}${window.location.hash}`
}

function redirectToLogin(isSellerRequest: boolean, text: string) {
  const loginPath = isSellerRequest ? '/admin/login' : '/login'
  if (window.location.pathname === loginPath) {
    message.error(text)
    return
  }

  const returnTo = currentPath()
  sessionStorage.setItem('auth_redirect_message', text)
  window.location.assign(`${loginPath}?returnTo=${encodeURIComponent(returnTo)}`)
}

function createApiError(
  code: number | undefined,
  serverMessage: string | undefined,
  data: unknown,
  traceId: string | undefined,
  url: string | undefined,
  status?: number,
) {
  const itemErrors = getCartItemErrors(data)
  const isSellerRequest = url?.startsWith('/admin/') ?? false
  const hasToken = Boolean(localStorage.getItem(isSellerRequest ? 'seller_token' : 'customer_token'))
  const fallbackMessage = status === 401
    ? isSellerRequest ? '请先登录后台' : hasToken ? '请重新登录' : '请先登录'
    : '网络错误'
  const text = itemErrors.length > 0
    ? serverMessage || fallbackMessage
    : errorMessage(code, serverMessage || fallbackMessage, url)
  if (traceId) console.error('API 请求失败', { code, traceId })

  if (code === 40101 || status === 401) {
    const isAuthRequest = url?.endsWith('/auth/login') || url?.endsWith('/auth/register')
    if (!isAuthRequest) {
      localStorage.removeItem(isSellerRequest ? 'seller_token' : 'customer_token')
      redirectToLogin(isSellerRequest, text)
    } else {
      message.error(text)
    }
  } else if (itemErrors.length === 0) {
    message.error(text)
  }

  return new ApiError(code, text, traceId, data)
}

const instance = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

instance.interceptors.request.use((config) => {
  const isSellerRequest = config.url?.startsWith('/admin/') ?? false
  const token = localStorage.getItem(isSellerRequest ? 'seller_token' : 'customer_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

instance.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse<unknown>
    if (body.code !== 0) {
      return Promise.reject(createApiError(
        body.code,
        body.message,
        body.data,
        body.traceId,
        response.config.url,
        response.status,
      ))
    }
    return response
  },
  (error: AxiosError<ApiResponse<unknown>>) => {
    const body = error.response?.data
    return Promise.reject(createApiError(
      body?.code,
      body?.message,
      body?.data,
      body?.traceId,
      error.config?.url,
      error.response?.status,
    ))
  },
)

export interface RequestResult<T> {
  data: T
  message: string
}

export async function requestWithMessage<T>(config: AxiosRequestConfig): Promise<RequestResult<T>> {
  const response = await instance.request<ApiResponse<T>>(config)
  return { data: response.data.data, message: response.data.message }
}

export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const result = await requestWithMessage<T>(config)
  return result.data
}

export default request
