import { useEffect, useState } from 'react'
import { Alert, Button, Card, Descriptions, Empty, Image, Pagination, Space, Spin, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { getProductHistory, getProductHistoryDetail, getProductRecords } from '../../api/product'
import type { Page } from '../../types/common'
import type { Intent } from '../../types/intent'
import type { Product, ProductHistoryDetail, ProductRecords, ProductStatus, ProductStatusEvent, TradeAttempt } from '../../types/product'

const { Text } = Typography
const pageSize = 10

const productStatusLabels: Record<ProductStatus, string> = {
  ONLINE: '在售',
  RESTORED_ONLINE: '恢复在售',
  FROZEN: '已冻结',
  SOLD: '已售出',
}

const intentStatusLabels: Record<Intent['status'], string> = {
  QUEUING: '排队中',
  IN_TRANSACTION: '交易中',
  SUCCESS: '交易成功',
  FAILED: '交易失败',
  CANCELLED: '已撤销',
  UNSOLD: '未成交',
}

const eventLabels: Record<ProductStatusEvent['eventType'], string> = {
  PUBLISHED: '商品发布',
  MANUAL_FREEZE: '手动冻结',
  MANUAL_UNFREEZE: '手动解冻',
  TRADE_STARTED: '开始交易',
  TRADE_FAILED: '交易失败',
  TRADE_SUCCEEDED: '交易成功',
}

function formatDate(value: string | null) {
  if (!value) return '-'

  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

export default function ProductHistoryPage() {
  const { id: productId } = useParams<{ id: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const isRecordsRoute = location.pathname.endsWith('/records')
  const [page, setPage] = useState(1)
  const [history, setHistory] = useState<Page<Product> | null>(null)
  const [detail, setDetail] = useState<ProductHistoryDetail | ProductRecords | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    let active = true

    const load = async () => {
      try {
        setLoading(true)
        setLoadError(false)
        if (productId !== undefined) {
          const parsedId = Number(productId)
          if (!Number.isInteger(parsedId) || parsedId <= 0) {
            setDetail(null)
            return
          }
          const result = isRecordsRoute
            ? await getProductRecords(parsedId)
            : await getProductHistoryDetail(parsedId)
          if (active) setDetail(result)
        } else {
          const result = await getProductHistory(page, pageSize)
          if (active) setHistory(result)
        }
      } catch (error) {
        console.error('加载商品历史失败:', error)
        if (active) setLoadError(true)
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => { active = false }
  }, [isRecordsRoute, productId, page])

  const productColumns: ColumnsType<Product> = [
    { title: '商品名称', dataIndex: 'name', key: 'name' },
    {
      title: '价格',
      dataIndex: 'price',
      key: 'price',
      render: (price: number) => `¥${Number(price).toFixed(2)}`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: Product['status']) => <Tag>{status}</Tag>,
    },
    { title: '发布时间', dataIndex: 'publishedAt', key: 'publishedAt' },
    {
      title: '操作',
      key: 'actions',
      render: (_, product) => (
        <Button type="link" onClick={() => navigate(`/admin/products/history/${product.id}`)}>
          查看详情
        </Button>
      ),
    },
  ]

  const intentColumns: ColumnsType<Intent> = [
    { title: '姓名', dataIndex: 'buyerName', key: 'buyerName' },
    { title: '手机号', dataIndex: 'buyerPhone', key: 'buyerPhone' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (status: Intent['status']) => <Tag>{intentStatusLabels[status]}</Tag> },
    { title: '排队位置', dataIndex: 'position', key: 'position', render: (position: number | null) => position ?? '-' },
    { title: '首次提交时间', dataIndex: 'submittedAt', key: 'submittedAt', render: (value: string) => formatDate(value) },
    { title: '最近处理时间', dataIndex: 'processedAt', key: 'processedAt', render: (value: string | null) => formatDate(value) },
  ]

  const attemptColumns: ColumnsType<TradeAttempt> = [
    { title: '尝试编号', dataIndex: 'id', key: 'id' },
    { title: '意向编号', dataIndex: 'intentId', key: 'intentId' },
    { title: '开始时间', dataIndex: 'startedAt', key: 'startedAt', render: (value: string) => formatDate(value) },
    { title: '结束时间', dataIndex: 'finishedAt', key: 'finishedAt', render: (value: string | null) => formatDate(value) },
    {
      title: '结果',
      dataIndex: 'result',
      key: 'result',
      render: (result: TradeAttempt['result']) => result === 'SUCCESS' ? '成功' : result === 'FAILED' ? '失败' : '进行中',
    },
    {
      title: '失败处理',
      dataIndex: 'failAction',
      key: 'failAction',
      render: (action: TradeAttempt['failAction']) => action === 'REQUEUE' ? '重新排队' : action === 'DISCARD' ? '放弃' : '-',
    },
  ]

  const eventColumns: ColumnsType<ProductStatusEvent> = [
    { title: '事件', dataIndex: 'eventType', key: 'eventType', render: (event: ProductStatusEvent['eventType']) => eventLabels[event] },
    {
      title: '状态变化',
      key: 'statusChange',
      render: (_, event) => `${event.fromStatus ? productStatusLabels[event.fromStatus] : '无'} → ${productStatusLabels[event.toStatus]}`,
    },
    { title: '交易尝试', dataIndex: 'tradeAttemptId', key: 'tradeAttemptId', render: (id: number | null) => id ? `#${id}` : '-' },
    { title: '发生时间', dataIndex: 'occurredAt', key: 'occurredAt', render: (value: string) => formatDate(value) },
  ]

  if (loading) {
    return <div style={{ padding: 48, textAlign: 'center' }}><Spin size="large" /></div>
  }

  if (productId !== undefined) {
    if (!detail) {
      return (
        <Card style={{ maxWidth: 900, margin: 24 }}>
          <Empty description={loadError ? '加载商品详情失败' : '未找到该商品详情'}>
            <Button onClick={() => navigate(isRecordsRoute ? '/admin/products/current' : '/admin/products/history')}>
              {isRecordsRoute ? '返回当前商品' : '返回历史列表'}
            </Button>
          </Empty>
        </Card>
      )
    }

    const fullRecords = 'tradeAttempts' in detail ? detail : null

    return (
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Button onClick={() => navigate(isRecordsRoute ? '/admin/products/current' : '/admin/products/history')}>
            {isRecordsRoute ? '返回当前商品' : '返回历史列表'}
          </Button>
          {fullRecords?.legacyRecordsMayBeIncomplete && (
            <Alert
              type="warning"
              showIcon
              message="该商品的部分历史记录可能不完整"
              description={fullRecords.historyCompleteSince
                ? `完整记录从 ${formatDate(fullRecords.historyCompleteSince)} 起适用。`
                : '系统未提供历史记录完整性的起始时间。'}
            />
          )}
          <Card title={fullRecords ? '商品完整记录' : '商品历史详情'}>
            <Descriptions bordered column={1}>
              <Descriptions.Item label="商品名称">{detail.product.name}</Descriptions.Item>
              <Descriptions.Item label="价格">¥{Number(detail.product.price).toFixed(2)}</Descriptions.Item>
              <Descriptions.Item label="状态">{productStatusLabels[detail.product.status]}</Descriptions.Item>
              <Descriptions.Item label="描述">{detail.product.description || '-'}</Descriptions.Item>
              <Descriptions.Item label="发布时间">{formatDate(detail.product.publishedAt)}</Descriptions.Item>
              <Descriptions.Item label="状态更新时间">{formatDate(detail.product.statusUpdatedAt)}</Descriptions.Item>
              <Descriptions.Item label="售出时间">{formatDate(detail.product.soldAt)}</Descriptions.Item>
              <Descriptions.Item label="商品图片">
                {detail.product.imagePath ? <Image src={detail.product.imagePath} alt={detail.product.name} width={180} /> : <Text type="secondary">无图片</Text>}
              </Descriptions.Item>
            </Descriptions>
          </Card>
          <Card title={`相关购买意向（${detail.intents.length}）`}>
            <Table<Intent>
              rowKey="id"
              columns={intentColumns}
              dataSource={detail.intents}
              pagination={false}
              locale={{ emptyText: '暂无相关购买意向' }}
              scroll={{ x: 700 }}
            />
          </Card>
          {fullRecords && (
            <>
              <Card title={`交易尝试（${fullRecords.tradeAttempts.length}）`}>
                <Table<TradeAttempt>
                  rowKey="id"
                  columns={attemptColumns}
                  dataSource={fullRecords.tradeAttempts}
                  pagination={false}
                  locale={{ emptyText: '暂无交易尝试' }}
                  scroll={{ x: 800 }}
                />
              </Card>
              <Card title={`商品状态事件（${fullRecords.statusEvents.length}）`}>
                <Table<ProductStatusEvent>
                  rowKey="id"
                  columns={eventColumns}
                  dataSource={fullRecords.statusEvents}
                  pagination={false}
                  locale={{ emptyText: '暂无状态事件' }}
                  scroll={{ x: 700 }}
                />
              </Card>
            </>
          )}
        </Space>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
      {loadError ? (
        <Card title="商品历史">
          <Empty description="商品历史加载失败">
            <Button onClick={() => window.location.reload()}>重试</Button>
          </Empty>
        </Card>
      ) : <Card title="商品历史">
        <Table<Product>
          rowKey="id"
          columns={productColumns}
          dataSource={history?.list ?? []}
          pagination={false}
          locale={{ emptyText: '暂无商品历史' }}
          scroll={{ x: 700 }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={history?.total ?? 0}
            onChange={setPage}
            showSizeChanger={false}
          />
        </div>
      </Card>}
    </div>
  )
}
