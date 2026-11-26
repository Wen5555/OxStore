import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, Pagination, Space, Spin, Table, Tag, Typography } from 'antd'
import { Link } from 'react-router-dom'
import { getMyLegacyIntents } from '../../api/challengeB'
import type { LegacyPage, LegacyRecord } from '../../types/challengeB'

const PAGE_SIZE = 10

function formatDate(value: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    QUEUING: '已关闭（原排队中）',
    IN_TRANSACTION: '已关闭（原交易中）',
    DONE: '原交易成功',
    FAILED: '原交易失败',
    CLOSED: '已关闭',
  }
  return labels[status] ?? status
}

export default function BuyerLegacyIntentPage() {
  const [result, setResult] = useState<LegacyPage>()
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setLoadError(false)
    getMyLegacyIntents(page, PAGE_SIZE)
      .then((data) => { if (active) setResult(data) })
      .catch((error) => {
        console.error('获取旧意向归档失败:', error)
        if (active) setLoadError(true)
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, retryCount])

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Typography.Title level={2} style={{ margin: 0 }}>旧意向归档</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            仅供追溯的历史记录，不属于新订单，也不能继续操作。
          </Typography.Paragraph>
          <Link to="/me/account">返回买家账户</Link>
        </div>
        <Card>
          {loading ? <div style={{ padding: 48, textAlign: 'center' }}><Spin /></div> :
            loadError ? <Alert type="error" showIcon message="旧意向归档加载失败。" action={<Button onClick={() => setRetryCount((count) => count + 1)}>重试</Button>} /> :
            !result?.items.length ? <Empty description="暂无旧意向记录" /> : (
              <>
                <Table<LegacyRecord>
                  rowKey="legacyIntentId"
                  dataSource={result.items}
                  pagination={false}
                  columns={[
                    { title: '旧意向编号', dataIndex: 'legacyIntentId', key: 'legacyIntentId' },
                    { title: '商品编号', dataIndex: 'productId', key: 'productId' },
                    { title: '商品快照', dataIndex: 'productNameSnapshot', key: 'productNameSnapshot' },
                    { title: '原状态', dataIndex: 'originalStatus', key: 'originalStatus', render: status => <Tag>{statusLabel(status)}</Tag> },
                    { title: '提交时间', dataIndex: 'submittedAt', key: 'submittedAt', render: formatDate },
                    { title: '处理时间', dataIndex: 'processedAt', key: 'processedAt', render: formatDate },
                    { title: '关闭时间', dataIndex: 'closedAt', key: 'closedAt', render: formatDate },
                    { title: '记录性质', dataIndex: 'readOnly', key: 'readOnly', render: () => '只读归档' },
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
