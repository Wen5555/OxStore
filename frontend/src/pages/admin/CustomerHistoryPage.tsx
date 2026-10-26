import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, Pagination, Space, Spin, Table, Tag, Typography } from 'antd'
import { useParams } from 'react-router-dom'
import { getCustomerOrderHistory } from '../../api/admin'
import type { OrderHistoryItem, Page } from '../../types/common'

const PAGE_SIZE = 10
const formatDate = (value: string) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

export default function CustomerHistoryPage() {
  const { customerId } = useParams()
  const id = Number(customerId)
  const [data, setData] = useState<Page<OrderHistoryItem>>()
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    if (!Number.isInteger(id) || id <= 0) {
      setLoadError(true)
      setLoading(false)
      return
    }
    let active = true
    setLoading(true)
    setLoadError(false)
    getCustomerOrderHistory(id, page, PAGE_SIZE)
      .then((result) => { if (active) setData(result) })
      .catch((error) => {
        console.error('获取顾客购买历史失败:', error)
        if (active) setLoadError(true)
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [id, page, retryCount])

  return (
    <main style={{ maxWidth: 1000, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Typography.Title level={2}>顾客购买历史</Typography.Title>
        <Card>
          {loading ? <div style={{ padding: 48, textAlign: 'center' }}><Spin /></div> :
            loadError ? <Alert type="error" showIcon message="顾客购买历史加载失败。" action={<Button onClick={() => setRetryCount((count) => count + 1)}>重试</Button>} /> :
            !data?.items.length ? <Empty description="暂无成功或失败的购买记录" /> : (
              <>
                <Table<OrderHistoryItem>
                  rowKey="orderId"
                  dataSource={data.items}
                  pagination={false}
                  columns={[
                    { title: '商品', dataIndex: 'productName', key: 'productName' },
                    { title: '下单时间', dataIndex: 'submittedAt', key: 'submittedAt', render: formatDate },
                    { title: '结果', dataIndex: 'status', key: 'status', render: (status: OrderHistoryItem['status']) => <Tag color={status === 'SUCCESS' ? 'green' : 'red'}>{status === 'SUCCESS' ? '成功' : '失败'}</Tag> },
                    { title: '交易时间', dataIndex: 'transactedAt', key: 'transactedAt', render: formatDate },
                  ]}
                />
                <Pagination style={{ marginTop: 20 }} current={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} />
              </>
            )}
        </Card>
      </Space>
    </main>
  )
}
