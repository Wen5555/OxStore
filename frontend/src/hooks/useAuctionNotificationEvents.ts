import { useEffect, useRef } from 'react'
import type { AuctionNotification } from '../types/auction'

export function useAuctionNotificationEvents(
  role: 'customer' | 'seller',
  onNotification: (notification: AuctionNotification) => void,
) {
  const callbackRef = useRef(onNotification)
  callbackRef.current = onNotification

  useEffect(() => {
    const controller = new AbortController()
    const path = role === 'customer'
      ? '/api/me/auction-notifications/stream'
      : '/api/admin/auction-notifications/stream'
    const tokenKey = role === 'customer' ? 'customer_token' : 'seller_token'
    let reconnectTimer: number | undefined

    const connect = async () => {
      try {
        const token = localStorage.getItem(tokenKey)
        if (!token) return
        const response = await fetch(path, {
          headers: { Accept: 'text/event-stream', Authorization: `Bearer ${token}` },
          signal: controller.signal,
        })
        if (!response.ok || !response.body) throw new Error(`提醒实时连接失败: ${response.status}`)
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (!controller.signal.aborted) {
          const { value, done } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const messages = buffer.split('\n\n')
          buffer = messages.pop() ?? ''
          messages.forEach((eventText) => {
            const data = eventText.split('\n').find((line) => line.startsWith('data:'))
            if (!data) return
            try {
              callbackRef.current(JSON.parse(data.slice(5).trim()) as AuctionNotification)
            } catch (error) {
              console.error('拍卖提醒事件格式无效:', error)
            }
          })
        }
      } catch (error) {
        if (!controller.signal.aborted) console.error('拍卖提醒实时连接失败:', error)
      } finally {
        if (!controller.signal.aborted) reconnectTimer = window.setTimeout(() => void connect(), 3000)
      }
    }

    void connect()
    return () => {
      controller.abort()
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
    }
  }, [role])
}
