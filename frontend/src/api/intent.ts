import { request } from './request'
import type { Intent } from '../types/intent'

// 提交购买意向，返回 { code, position, status }
export function submitIntent(data: { buyerName: string; buyerPhone: string }) {
  return request<{ code: string; position: number; status: string }>({
    url: '/intents',
    method: 'POST',
    data,
  })
}

// 凭口令码查询进度
export function queryIntent(code: string) {
  return request<Intent>({ url: `/intents/${code}`, method: 'GET' })
}

// 凭口令码修改信息
export function modifyIntent(code: string, data: { buyerName?: string; buyerPhone?: string }) {
  return request<Intent>({ url: `/intents/${code}`, method: 'PUT', data })
}

// 凭口令码撤销
export function cancelIntent(code: string) {
  return request<void>({ url: `/intents/${code}`, method: 'DELETE' })
}

// 查看意向队列（后台）
export function getIntentQueue() {
  return request<Intent[]>({ url: '/admin/intents', method: 'GET' })
}

// 选择队首开始交易
export function startTrade(intentId: number) {
  return request<void>({ url: `/admin/intents/${intentId}/start`, method: 'POST' })
}

// 确认当前交易尝试成功；从后台队列的 currentTradeAttemptId 读取，不可复用旧 ID。
export function confirmSuccess(intentId: number, tradeAttemptId: number) {
  return request<void>({ url: `/admin/intents/${intentId}/success`, method: 'POST', data: { tradeAttemptId } })
}

// 确认交易失败：action = REQUEUE | DISCARD
export function confirmFail(intentId: number, action: 'REQUEUE' | 'DISCARD', tradeAttemptId: number) {
  return request<Intent | null>({ url: `/admin/intents/${intentId}/fail`, method: 'POST', data: { action, tradeAttemptId } })
}
