import axios, { AxiosError, type AxiosRequestConfig } from 'axios'
import { message } from 'antd'
import type { ApiResponse } from '../types/common'

export class ApiError extends Error {
  constructor(public readonly code: number | undefined, messageText: string, public readonly traceId?: string) {
    super(messageText)
    this.name = 'ApiError'
  }
}

function apiErrorMessage(code: number | undefined, fallback: string) {
  switch (code) {
    case 40001: return '请检查必填字段和输入格式。'
    case 40002: return '请求格式无效，请检查输入后重试。'
    case 40003: return '分页参数无效，请刷新页面后重试。'
    case 40101: return '登录状态已失效，请重新登录。'
    case 40102: return '用户名或密码错误。'
    case 40301:
    case 40302: return '当前账号无权执行此操作。'
    case 40401:
    case 40402:
    case 40403:
    case 40404: return '请求的商品、类目、意向或顾客不存在。'
    case 40901: return '商品状态已变化，请刷新后重试。'
    case 40902: return '该意向已不是队首或已有交易处理中，请刷新队列。'
    case 40903: return '用户名已存在，请更换用户名。'
    case 40904: return '数据已被其他操作更新，请刷新后重试。'
    case 40905: return '库存不足或库存状态已变化，请刷新后重试。'
    case 41301: return '图片不能超过 5MB。'
    case 41501: return '图片格式仅支持 JPG、PNG。'
    case 42201: return '商品描述包含不支持的内容，请修改后重试。'
    case 50000: return '服务暂时不可用，请稍后重试。'
    default: return fallback
  }
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
      const text = apiErrorMessage(body.code, body.message || '请求失败')
      if (body.traceId) console.error('API 请求失败', { code: body.code, traceId: body.traceId })
      message.error(text)
      return Promise.reject(new ApiError(body.code, text, body.traceId))
    }
    return response
  },
  (error: AxiosError<ApiResponse<unknown>>) => {
    const body = error.response?.data
    const errorCode = body?.code
    const text = apiErrorMessage(errorCode, body?.message || '网络错误')
    if (body?.traceId) console.error('API 请求失败', { code: errorCode, traceId: body.traceId })
    message.error(text)
    if (errorCode === 40101 || error.response?.status === 401) {
      const isSellerRequest = error.config?.url?.startsWith('/admin/') ?? false
      localStorage.removeItem(isSellerRequest ? 'seller_token' : 'customer_token')
      if (isSellerRequest && !error.config?.url?.endsWith('/admin/auth/login')) {
        window.location.href = '/admin/login'
      } else if (!isSellerRequest && !error.config?.url?.endsWith('/auth/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(new ApiError(errorCode, text, body?.traceId))
  },
)

export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const response = await instance.request<ApiResponse<T>>(config)
  return response.data.data
}

export default request
