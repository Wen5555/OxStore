import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, Pagination, Popconfirm, Space, Spin, Tag, Typography, message } from 'antd'
import { useParams } from 'react-router-dom'
import { confirmFail, confirmSuccess, getProductIntentQueue, startTrade } from '../../api/intent'
import { getAdminProduct } from '../../api/admin'
import type { Product } from '../../types/product'
import { ApiError } from '../../api/request'
import type { Intent } from '../../types/intent'
import { useAuctionEvents } from '../../hooks/useAuctionEvents'
import { getAuctionSnapshot } from '../../api/auction'
import type { AuctionSnapshot } from '../../types/auction'

const PAGE_SIZE = 10

function toAuctionSummary(snapshot: AuctionSnapshot) {
  return {
    auctionStatus: snapshot.auctionStatus,
    currentPrice: snapshot.currentPrice ?? snapshot.startPrice,
    nextMinBid: snapshot.nextMinBid,
    endsAt: snapshot.endsAt,
    bidCount: snapshot.bidCount,
  }
}

export default function ProductIntentQueuePage() {
  const { id } = useParams()
  const productId = Number(id)
  const [items, setItems] = useState<Intent[]>([])
  const [currentIntent, setCurrentIntent] = useState<Intent>()
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const [action, setAction] = useState('')
  const [product, setProduct] = useState<Product>()

  useAuctionEvents(product?.sellingMode === 'AUCTION' ? product.id : undefined, (event) => {
    setProduct((current) => {
      if (!current || current.id !== productId || current.sellingMode !== 'AUCTION') return current
      const auction = 'productName' in event
        ? event
        : 'currentPrice' in event ? {
            ...current.auction,
            currentPrice: event.currentPrice,
            nextMinBid: event.nextMinBid,
            bidCount: event.bidCount,
          } : current.auction
      return {
        ...current,
        auction: {
          auctionStatus: auction?.auctionStatus ?? current.auction?.auctionStatus ?? 'LIVE',
          currentPrice: auction?.currentPrice ?? current.auction?.currentPrice ?? current.price,
          nextMinBid: auction?.nextMinBid ?? current.auction?.nextMinBid ?? current.price,
          endsAt: auction?.endsAt ?? current.auction?.endsAt ?? '',
          bidCount: auction?.bidCount ?? current.auction?.bidCount ?? 0,
        },
      }
    })

  })

  useEffect(() => {
    if (!product || product.sellingMode !== 'AUCTION') return
    let active = true
    const refreshAuction = async () => {
      try {
        const snapshot = await getAuctionSnapshot(product.id)
        if (!active) return
        setProduct((current) => current && {
          ...current,
          auction: toAuctionSummary(snapshot),
        })
      } catch (error) {
        console.error('刷新拍卖进度失败:', error)
      }
    }
    void refreshAuction()
    const timer = window.setInterval(() => { void refreshAuction() }, 3000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [product?.id, product?.sellingMode])

  const load = async () => {
    if (!Number.isInteger(productId) || productId <= 0) {
      setLoadError(true)
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setLoadError(false)
      const [result, firstPage, productResult] = await Promise.all([
        getProductIntentQueue(productId, page, PAGE_SIZE),
        page === 1 ? Promise.resolve(null) : getProductIntentQueue(productId, 1, PAGE_SIZE),
        getAdminProduct(productId),
      ])
      setItems(result.items)
      setTotal(result.total)
      setCurrentIntent((firstPage?.items ?? result.items).find((intent) => intent.status === 'IN_TRANSACTION'))
      setProduct(productResult)
    } catch (error) {
      console.error('获取商品意向队列失败:', error)
      setLoadError(true)
    } finally {
      setLoading(false)
    }

  }

  useEffect(() => { void load() }, [productId, page, retryCount])

  useEffect(() => {
    if (product?.sellingMode === 'AUCTION'
      && product.auction
      && product.auction.auctionStatus !== 'LIVE') {
      void load()
    }
  }, [product?.auction?.auctionStatus])

  const queue = items.filter((intent) => intent.status === 'QUEUING')

  const perform = async (operation: 'start' | 'success' | 'REQUEUE' | 'DISCARD') => {
    try {
      setAction(operation)
      if (operation === 'start' && queue[0]) {
        await startTrade(queue[0].intentId)
        message.success('已开始处理队首意向')
      } else if (operation === 'success' && currentIntent) {
        await confirmSuccess(currentIntent.intentId)
        message.success('已确认交易成功')
      } else if ((operation === 'REQUEUE' || operation === 'DISCARD') && currentIntent) {
        await confirmFail(currentIntent.intentId, operation)
        message.success(operation === 'REQUEUE' ? '已记录失败并重新排队' : '已记录失败并作废意向')
      }
      await load()
    } catch (error) {
      console.error('更新交易状态失败:', error)
      if (error instanceof ApiError && [40901, 40902, 40904, 40905].includes(error.code ?? 0)) {
        await load()
      }
    } finally {
      setAction('')
    }
  }

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Typography.Title level={2}>商品意向队列</Typography.Title>
        {loading ? <div style={{ padding: 48, textAlign: 'center' }}><Spin size="large" /></div> : (
          <>
            {product?.sellingMode === 'AUCTION' && product.auction && (
              <Card title="竞价结算">
                <Space wrap>
                  <Typography.Text>当前价：¥{Number(product.auction.currentPrice).toFixed(2)}</Typography.Text>
                  <Typography.Text>出价次数：{product.auction.bidCount}</Typography.Text>
                  <Typography.Text>截止：{new Date(product.auction.endsAt).toLocaleString()}</Typography.Text>
                  <Typography.Text>状态：{product.auction.auctionStatus}</Typography.Text>
                  {product.auction.auctionStatus === 'ENDED_SOLD' && (
                    <Typography.Text type="success">已结拍，中标人已进入交易中</Typography.Text>
                  )}
                  {product.auction.auctionStatus === 'ENDED_UNSOLD' && (
                    <Typography.Text type="warning">已流拍，无人出价</Typography.Text>
                  )}
                </Space>
              </Card>
            )}
            {loadError && <Alert type="error" showIcon message="商品意向队列加载失败。" action={<Button onClick={() => setRetryCount((count) => count + 1)}>重试</Button>} />}
            {!loadError && <>
            <Card title="交易中">
              {currentIntent ? (
                <Space direction="vertical">
                  <Space wrap><Tag color="blue">交易中</Tag><Typography.Text strong>{currentIntent.username}</Typography.Text></Space>
                  <Space wrap>
                    <Button type="primary" loading={action === 'success'} onClick={() => void perform('success')}>确认成功</Button>
                    {product?.sellingMode !== 'AUCTION' && (
                      <Popconfirm title="将该意向重新排到队尾？" onConfirm={() => void perform('REQUEUE')} okText="重新排队" cancelText="取消">
                        <Button danger loading={action === 'REQUEUE'}>失败并重新排队</Button>
                      </Popconfirm>
                    )}
                    <Popconfirm title="作废该意向？" onConfirm={() => void perform('DISCARD')} okText="作废" cancelText="取消">
                      <Button danger loading={action === 'DISCARD'}>失败并作废</Button>
                    </Popconfirm>
                  </Space>
                </Space>
              ) : <Empty description="当前没有进行中的交易" />}
            </Card>
            {product?.sellingMode !== 'AUCTION' && <Card title={`排队及交易意向（${total}）`} extra={page === 1 && queue.length > 0 && !currentIntent ? <Button type="primary" loading={action === 'start'} onClick={() => void perform('start')}>开始处理队首</Button> : undefined}>
              {!queue.length ? <Empty description="暂无排队意向" /> : (
                <Space direction="vertical" style={{ width: '100%' }}>
                  {queue.map((intent) => <div key={intent.intentId}><Tag color="orange">第 {intent.position} 位</Tag><Typography.Text strong>{intent.username}</Typography.Text></div>)}
                </Space>
              )}
              {total > PAGE_SIZE && <Pagination style={{ marginTop: 20 }} current={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} />}
            </Card>}
            </>}
          </>
        )}
      </Space>
    </main>
  )
}
