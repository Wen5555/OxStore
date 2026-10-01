import axios, { AxiosError, type AxiosRequestConfig } from 'axios'
import { message } from 'antd'
import type { ApiResponse } from '../types/common'

const instance = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 请求拦截：注入 JWT
instance.interceptors.request.use((config) => {
  const token = localStorage.getItem('shop_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：统一处理业务错误码
instance.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse<unknown>
    if (body.code !== 0) {
      message.error(body.message || '请求失败')
      return Promise.reject(new Error(body.message))
    }
    return response
  },
  (error: AxiosError<ApiResponse<unknown>>) => {
    const body = error.response?.data
    const msg = body?.message || '网络错误'
    message.error(msg)
    if (error.response?.status === 401) {
      localStorage.removeItem('shop_token')
      window.location.href = '/admin/login'
    }
    return Promise.reject(error)
  },
)

export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const response = await instance.request<ApiResponse<T>>(config)
  return response.data.data
}

export default request
