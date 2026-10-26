import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, Pagination, Space, Spin, Table, Tag, Typography } from 'antd'
import { getMyOrderHistory } from '../../api/catalog'
import type { OrderHistoryItem, Page } from '../../types/common'

const PAGE_SIZE = 10

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

export default function BuyerHistoryPage() {
  const [result, setResult] = useState<Page<OrderHistoryItem>>()
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setLoadError(false)
    getMyOrderHistory(page, PAGE_SIZE)
      .then((data) => { if (active) setResult(data) })
      .catch((error) => {
        console.error('获取购买历史失败:', error)
        if (active) setLoadError(true)
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, retryCount])

  return (
    <main style={{ maxWidth: 1000, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Typography.Title level={2} style={{ margin: 0 }}>我的购买历史</Typography.Title>
        <Card>
          {loading ? <div style={{ padding: 48, textAlign: 'center' }}><Spin /></div> :
            loadError ? <Alert type="error" showIcon message="购买历史加载失败。" action={<Button onClick={() => setRetryCount((count) => count + 1)}>重试</Button>} /> :
            !result?.items.length ? <Empty description="暂无已完成的购买记录" /> : (
              <>
                <Table<OrderHistoryItem>
                  rowKey="id"
                  dataSource={result.items}
                  pagination={false}
                  columns={[
                    { title: '商品', dataIndex: 'productName', key: 'productName' },
                    { title: '下单时间', dataIndex: 'submittedAt', key: 'submittedAt', render: formatDate },
                    { title: '结果', dataIndex: 'status', key: 'status', render: (status: OrderHistoryItem['status']) => <Tag color={status === 'SUCCESS' ? 'green' : 'red'}>{status === 'SUCCESS' ? '成功' : '失败'}</Tag> },
                    { title: '交易时间', dataIndex: 'transactionAt', key: 'transactionAt', render: formatDate },
                  ]}
                />
                <Pagination style={{ marginTop: 20 }} current={page} pageSize={PAGE_SIZE} total={result.total} onChange={setPage} />
              </>
            )}
        </Card>
      </Space>
    </main>
  )
}
