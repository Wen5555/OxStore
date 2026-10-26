import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, Pagination, Space, Table, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { getAdminCustomers } from '../../api/admin'
import type { Customer, Page } from '../../types/common'

const PAGE_SIZE = 10
const formatDate = (value: string) => {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

export default function CustomersPage() {
  const [data, setData] = useState<Page<Customer>>()
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const navigate = useNavigate()

  useEffect(() => {
    let active = true
    setLoading(true)
    setLoadError(false)
    getAdminCustomers(page, PAGE_SIZE)
      .then((result) => { if (active) setData(result) })
      .catch((error) => {
        console.error('获取顾客列表失败:', error)
        if (active) setLoadError(true)
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, retryCount])

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Typography.Title level={2}>全部顾客</Typography.Title>
        <Card>
          {loadError ? <Alert type="error" showIcon message="顾客列表加载失败。" action={<Button onClick={() => setRetryCount((count) => count + 1)}>重试</Button>} /> :
          !loading && !data?.items.length ? <Empty description="暂无注册顾客" /> : (
            <Table<Customer>
              rowKey="customerId"
              loading={loading}
              dataSource={data?.items ?? []}
              pagination={false}
              columns={[
                { title: '用户名', dataIndex: 'username', key: 'username' },
                { title: '电话', dataIndex: 'phone', key: 'phone' },
                { title: '默认交易地点', dataIndex: 'location', key: 'location', render: (value: string | null) => value || '未设置' },
                { title: '注册时间', dataIndex: 'registeredAt', key: 'registeredAt', render: formatDate },
                { title: '操作', key: 'action', render: (_, customer) => <Button type="link" onClick={() => navigate(`/admin/customers/${customer.customerId}/order-history`)}>购买历史</Button> },
              ]}
            />
          )}
          {Boolean(data?.total) && <Pagination style={{ marginTop: 20 }} current={page} pageSize={PAGE_SIZE} total={data?.total} onChange={setPage} />}
        </Card>
      </Space>
    </main>
  )
}
