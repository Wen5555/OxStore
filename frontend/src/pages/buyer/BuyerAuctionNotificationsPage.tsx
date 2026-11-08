import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, List, Pagination, Space, Spin, Tag, Typography, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { getCustomerAuctionNotifications, markCustomerAuctionNotificationRead } from '../../api/auction'
import type { AuctionNotification } from '../../types/auction'
import type { Page } from '../../types/common'
import { useAuctionNotificationEvents } from '../../hooks/useAuctionNotificationEvents'

const PAGE_SIZE = 10

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

export default function BuyerAuctionNotificationsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<Page<AuctionNotification>>()
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useAuctionNotificationEvents('customer', (notification) => {
    setData((current) => {
      if (!current || current.items.some((item) => item.notificationId === notification.notificationId)) return current
      return { ...current, items: [notification, ...current.items].slice(0, PAGE_SIZE), total: current.total + 1 }
    })
  })

  const load = () => {
    setLoading(true)
    setError(false)
    getCustomerAuctionNotifications(page, PAGE_SIZE)
      .then(setData)
      .catch((reason) => { console.error('获取拍卖提醒失败:', reason); setError(true) })
      .finally(() => setLoading(false))
  }

  useEffect(load, [page])

  const openNotification = async (item: AuctionNotification) => {
    if (!item.readAt) {
      try {
        await markCustomerAuctionNotificationRead(item.notificationId)
        setData((current) => current && {
          ...current,
          items: current.items.map((notification) => notification.notificationId === item.notificationId
            ? { ...notification, readAt: new Date().toISOString() } : notification),
        })
      } catch (reason) {
        console.error('标记拍卖提醒已读失败:', reason)
        message.error('提醒状态更新失败，请稍后重试')
        return
      }
    }
    navigate(`/products/${item.productId}`)
  }

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Typography.Title level={2} style={{ margin: 0 }}>拍卖提醒</Typography.Title>
        <Card>
          {loading ? <div style={{ padding: 48, textAlign: 'center' }}><Spin /></div> :
            error ? <Alert type="error" showIcon message="拍卖提醒加载失败。" action={<Button onClick={load}>重试</Button>} /> :
            !data?.items.length ? <Empty description="暂无拍卖中标提醒" /> : (
              <>
                <List
                  dataSource={data.items}
                  renderItem={(item) => (
                    <List.Item actions={[<Button key="view" type="link" onClick={() => void openNotification(item)}>查看商品</Button>]}>
                      <List.Item.Meta
                        title={<Space><Typography.Text strong={!item.readAt}>{item.productName}</Typography.Text>{!item.readAt && <Tag color="blue">未读</Tag>}</Space>}
                        description={`恭喜你中标，成交价 ¥${Number(item.finalPrice ?? 0).toFixed(2)}，时间：${formatDate(item.createdAt)}`}
                      />
                    </List.Item>
                  )}
                />
                <Pagination style={{ marginTop: 20 }} current={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
              </>
            )}
        </Card>
      </Space>
    </main>
  )
}
