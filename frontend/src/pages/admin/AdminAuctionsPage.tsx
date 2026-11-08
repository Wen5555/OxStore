import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, Pagination, Select, Space, Spin, Table, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'
import { getAdminAuctions } from '../../api/auction'
import type { AuctionAdminItem } from '../../types/auction'
import type { Page } from '../../types/common'

const PAGE_SIZE = 10
const statusLabels: Record<AuctionAdminItem['auctionStatus'], string> = {
  LIVE: '进行中',
  ENDED_SOLD: '已成交',
  ENDED_UNSOLD: '已流拍',
}

function formatDate(value: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

export default function AdminAuctionsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<Page<AuctionAdminItem>>()
  const [status, setStatus] = useState<string>()
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = () => {
    setLoading(true)
    setError(false)
    getAdminAuctions({ status, page, size: PAGE_SIZE })
      .then(setData)
      .catch((reason) => { console.error('获取拍卖管理列表失败:', reason); setError(true) })
      .finally(() => setLoading(false))
  }

  useEffect(load, [page, status])

  return (
    <main style={{ maxWidth: 1300, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <Typography.Title level={2} style={{ margin: 0 }}>拍卖管理</Typography.Title>
          <Select
            allowClear
            placeholder="全部状态"
            value={status}
            style={{ width: 160 }}
            options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))}
            onChange={(value) => { setStatus(value); setPage(1) }}
          />
        </div>
        <Card>
          {loading ? <div style={{ padding: 48, textAlign: 'center' }}><Spin /></div> :
            error ? <Alert type="error" showIcon message="拍卖管理列表加载失败。" action={<Button onClick={load}>重试</Button>} /> :
            !data?.items.length ? <Empty description="暂无拍卖记录" /> : (
              <>
                <Table<AuctionAdminItem>
                  rowKey="productId"
                  dataSource={data.items}
                  pagination={false}
                  scroll={{ x: 1100 }}
                  columns={[
                    { title: '商品', dataIndex: 'productName', key: 'productName' },
                    { title: '状态', dataIndex: 'auctionStatus', key: 'auctionStatus', render: (value: AuctionAdminItem['auctionStatus']) => <Tag color={value === 'LIVE' ? 'blue' : value === 'ENDED_SOLD' ? 'green' : 'default'}>{statusLabels[value]}</Tag> },
                    { title: '起拍价', dataIndex: 'startPrice', key: 'startPrice', render: (value: number) => `¥${Number(value).toFixed(2)}` },
                    { title: '当前/成交价', dataIndex: 'currentPrice', key: 'currentPrice', render: (value: number | null) => value == null ? '-' : `¥${Number(value).toFixed(2)}` },
                    { title: '出价次数', dataIndex: 'bidCount', key: 'bidCount' },
                    { title: '截止时间', dataIndex: 'endsAt', key: 'endsAt', render: formatDate },
                    { title: '中标人', dataIndex: 'winnerAlias', key: 'winnerAlias', render: (value: string | null) => value || '-' },
                    { title: '操作', key: 'actions', render: (_, item) => item.winnerIntentId
                      ? <Button type="link" onClick={() => navigate(`/admin/products/${item.productId}/intents`)}>处理履约</Button>
                      : <Button type="link" onClick={() => navigate(`/products/${item.productId}`)}>查看商品</Button> },
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
