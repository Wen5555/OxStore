import { useEffect, useRef } from 'react'
import { getAuctionSnapshot } from '../api/auction'
import type { AuctionBidEvent, AuctionSettledEvent, AuctionSnapshot } from '../types/auction'

export type AuctionEvent = AuctionSnapshot | AuctionBidEvent | AuctionSettledEvent

export function useAuctionEvents(productId: number | undefined, onEvent: (event: AuctionEvent) => void) {
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  useEffect(() => {
    if (!productId) return
    const controller = new AbortController()
    let reconnectTimer: number | undefined
    let lastBidSeq = 0

    const connect = async (reconnecting = false) => {
      try {
        if (reconnecting) {
          const snapshot = await getAuctionSnapshot(productId)
          lastBidSeq = snapshot.lastBidSeq
          onEventRef.current(snapshot)
        }

        const headers: HeadersInit = { Accept: 'text/event-stream' }
        const token = localStorage.getItem('customer_token')
        if (token) headers.Authorization = `Bearer ${token}`
        const response = await fetch(`/api/products/${productId}/auction/stream`, {
          headers,
          signal: controller.signal,
        })
        if (!response.ok || !response.body) throw new Error(`SSE connection failed: ${response.status}`)
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
              const event = JSON.parse(data.slice(5).trim()) as AuctionEvent
              if ('bidSeq' in event) {
                if (event.bidSeq <= lastBidSeq) return
                lastBidSeq = event.bidSeq
              }
              onEventRef.current(event)
            } catch (error) {
              console.error('竞价事件格式无效:', error)
            }
          })
        }
      } catch (error) {
        if (!controller.signal.aborted) console.error('竞价实时连接失败:', error)
      } finally {
        if (!controller.signal.aborted) reconnectTimer = window.setTimeout(() => void connect(true), 3000)
      }
    }

    void connect()
    return () => {
      controller.abort()
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
    }
  }, [productId])
}
