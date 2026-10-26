import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, Pagination, Space, Table, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { getAdminProducts } from '../../api/admin'
import type { Page } from '../../types/common'
import type { Product } from '../../types/product'

const PAGE_SIZE = 10
const labels: Record<Product['status'], string> = {
  ONLINE: '在售',
  FROZEN: '交易中/冻结',
  OFFLINE: '已下架',
}

export default function AdminProductsPage() {
  const [data, setData] = useState<Page<Product>>()
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const navigate = useNavigate()

  const load = () => {
    setLoading(true)
    setLoadError(false)
    getAdminProducts(page, PAGE_SIZE)
      .then(setData)
      .catch((error) => {
        console.error('获取商品列表失败:', error)
        setLoadError(true)
      })
      .finally(() => setLoading(false))
  }

  useEffect(load, [page, retryCount])

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <Typography.Title level={2} style={{ margin: 0 }}>商品管理</Typography.Title>
          <Button type="primary" onClick={() => navigate('/admin/products/publish')}>发布商品</Button>
        </div>
        <Card>
          {loadError ? <Alert type="error" showIcon message="商品列表加载失败。" action={<Button onClick={() => setRetryCount((count) => count + 1)}>重试</Button>} /> :
          !loading && !data?.items.length ? <Empty description="暂无商品" /> : (
            <Table<Product>
              rowKey="id"
              loading={loading}
              dataSource={data?.items ?? []}
              pagination={false}
              columns={[
                { title: '商品', dataIndex: 'name', key: 'name' },
                { title: '价格', dataIndex: 'price', key: 'price', render: (value: number) => `¥${Number(value).toFixed(2)}` },
                { title: '库存', dataIndex: 'stock', key: 'stock' },
                { title: '二级类目', dataIndex: 'categoryName', key: 'categoryName' },
                { title: '状态', dataIndex: 'status', key: 'status', render: (status: Product['status']) => <Tag>{labels[status]}</Tag> },
                {
                  title: '操作',
                  key: 'actions',
                  render: (_, product) => (
                    <Space wrap>
                      <Button type="link" onClick={() => navigate(`/admin/products/${product.id}/edit`)}>编辑库存/类目</Button>
                      <Button type="link" onClick={() => navigate(`/admin/products/${product.id}/intents`)}>意向队列</Button>
                    </Space>
                  ),
                },
              ]}
            />
          )}
          {Boolean(data?.total) && <Pagination style={{ marginTop: 20 }} current={page} pageSize={PAGE_SIZE} total={data?.total} onChange={setPage} />}
        </Card>
      </Space>
    </main>
  )
}
