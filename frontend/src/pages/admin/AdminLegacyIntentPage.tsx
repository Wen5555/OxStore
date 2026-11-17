import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, Form, Input, Pagination, Space, Spin, Table, Tag, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { getAdminLegacyIntents } from '../../api/challengeB'
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

export default function AdminLegacyIntentPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [form] = Form.useForm<{ productId?: string; customerId?: string }>()
  const [result, setResult] = useState<LegacyPage>()
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const productId = searchParams.get('productId') ?? ''
  const customerId = searchParams.get('customerId') ?? ''

  useEffect(() => {
    form.setFieldsValue({ productId, customerId })
  }, [form, productId, customerId])

  useEffect(() => {
    let active = true
    setLoading(true)
    setLoadError(false)
    getAdminLegacyIntents(page, PAGE_SIZE, {
      ...(productId ? { productId } : {}),
      ...(customerId ? { customerId } : {}),
    })
      .then((data) => { if (active) setResult(data) })
      .catch((error) => {
        console.error('获取旧意向归档失败:', error)
        if (active) setLoadError(true)
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, productId, customerId, retryCount])

  const search = (values: { productId?: string; customerId?: string }) => {
    const next = new URLSearchParams()
    if (values.productId?.trim()) next.set('productId', values.productId.trim())
    if (values.customerId?.trim()) next.set('customerId', values.customerId.trim())
    setPage(1)
    setSearchParams(next)
  }

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Typography.Title level={2} style={{ margin: 0 }}>旧意向归档</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            历史快照只读保留，不进入新订单流转。
          </Typography.Paragraph>
        </div>
        <Card>
          <Form form={form} layout="inline" onFinish={search}>
            <Form.Item label="商品编号" name="productId">
              <Input inputMode="numeric" />
            </Form.Item>
            <Form.Item label="顾客编号" name="customerId">
              <Input inputMode="numeric" />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit">查询</Button>
                <Button onClick={() => {
                  form.resetFields()
                  setPage(1)
                  setSearchParams(new URLSearchParams())
                }}>清除筛选</Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
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
                    { title: '意向编号', dataIndex: 'legacyIntentId', key: 'legacyIntentId' },
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
