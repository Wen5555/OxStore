import { useEffect, useState } from 'react'
import { Alert, Button, Card, Descriptions, Empty, Input, Modal, Pagination, Space, Spin, Table, Tag, Typography, message } from 'antd'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/request'
import { cancelMyOrder, getMyOrder, getMyOrders } from '../../api/orders'
import type { Order, OrderPage, OrderStatus } from '../../types/challengeB'

const PAGE_SIZE = 10

const statusLabels: Record<OrderStatus, string> = {
  PLACED: '客户下单',
  CONFIRMED: '商家确认',
  PREPARED: '备货完成',
  SHIPPED: '开始发货',
  COMPLETED: '交易完成',
  CANCELLED: '已取消',
}

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

function statusColor(status: OrderStatus) {
  if (status === 'COMPLETED') return 'green'
  if (status === 'CANCELLED') return 'default'
  if (status === 'SHIPPED') return 'blue'
  return 'processing'
}

export default function BuyerHistoryPage() {
  const [result, setResult] = useState<OrderPage>()
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const [detail, setDetail] = useState<Order>()
  const [detailLoading, setDetailLoading] = useState(false)
  const [cancelTarget, setCancelTarget] = useState<Order>()
  const [cancelReason, setCancelReason] = useState('')
  const [cancelSubmitting, setCancelSubmitting] = useState(false)

  const load = async () => {
    setLoading(true)
    setLoadError(false)
    try {
      setResult(await getMyOrders(page, PAGE_SIZE))
    } catch (error) {
      console.error('获取订单历史失败:', error)
      setLoadError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [page, retryCount])

  const openDetail = async (orderId: string) => {
    setDetailLoading(true)
    setDetail(undefined)
    try {
      setDetail(await getMyOrder(orderId))
    } catch (error) {
      console.error('获取订单详情失败:', error)
    } finally {
      setDetailLoading(false)
    }
  }

  const performCancel = async () => {
    if (!cancelTarget) return
    const order = cancelTarget
    setCancelSubmitting(true)
    try {
      const result = await cancelMyOrder(order.orderId, order.status, cancelReason)
      message.success(result.message)
      setCancelTarget(undefined)
      setCancelReason('')
      await load()
      if (detail?.orderId === order.orderId) await openDetail(order.orderId)
    } catch (error) {
      console.error('取消订单失败:', error)
      if (error instanceof ApiError && [40904, 40911].includes(error.code ?? 0)) {
        await load()
        setCancelTarget(undefined)
        setCancelReason('')
      }
    } finally {
      setCancelSubmitting(false)
    }
  }

  return (
    <main style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Typography.Title level={2} style={{ margin: 0 }}>订单历史</Typography.Title>
          <Link to="/me/account">返回买家账户</Link>
        </div>
        <Card>
          {loading ? <div style={{ padding: 48, textAlign: 'center' }}><Spin /></div> :
            loadError ? <Alert type="error" showIcon message="订单历史加载失败。" action={<Button onClick={() => setRetryCount((count) => count + 1)}>重试</Button>} /> :
            !result?.items.length ? <Empty description="暂无订单" /> : (
              <>
                <Table<Order>
                  rowKey="orderId"
                  dataSource={result.items}
                  pagination={false}
                  scroll={{ x: 900 }}
                  columns={[
                    { title: '订单号', dataIndex: 'orderNo', key: 'orderNo' },
                    {
                      title: '商品',
                      key: 'items',
                      render: (_, order) => order.items.map((item) => `${item.productName} × ${item.quantity}`).join('、'),
                    },
                    { title: '总金额', dataIndex: 'totalAmount', key: 'totalAmount', render: (amount: string) => `¥${amount}` },
                    {
                      title: '状态',
                      dataIndex: 'status',
                      key: 'status',
                      render: (status: OrderStatus) => <Tag color={statusColor(status)}>{statusLabels[status]}</Tag>,
                    },
                    { title: '下单时间', dataIndex: 'createdAt', key: 'createdAt', render: formatDate },
                    {
                      title: '操作',
                      key: 'actions',
                      render: (_, order) => (
                        <Space wrap>
                          <Button type="link" onClick={() => void openDetail(order.orderId)}>详情</Button>
                          {order.allowedActions.includes('CANCEL') && (
                            <Button
                              danger
                              type="link"
                              onClick={() => {
                                setCancelReason('')
                                setCancelTarget(order)
                              }}
                            >
                              取消订单
                            </Button>
                          )}
                        </Space>
                      ),
                    },
                  ]}
                />
                <Pagination style={{ marginTop: 20 }} current={page} pageSize={PAGE_SIZE} total={result.total} onChange={setPage} />
              </>
            )}
        </Card>
      </Space>

      <Modal
        title="订单详情"
        open={Boolean(detail) || detailLoading}
        footer={<Button onClick={() => setDetail(undefined)}>关闭</Button>}
        onCancel={() => setDetail(undefined)}
        width={760}
      >
        {detailLoading ? <div style={{ padding: 32, textAlign: 'center' }}><Spin /></div> : detail && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="订单号">{detail.orderNo}</Descriptions.Item>
              <Descriptions.Item label="状态"><Tag color={statusColor(detail.status)}>{statusLabels[detail.status]}</Tag></Descriptions.Item>
              <Descriptions.Item label="下单时间">{formatDate(detail.createdAt)}</Descriptions.Item>
              <Descriptions.Item label="订单总额">¥{detail.totalAmount}</Descriptions.Item>
              <Descriptions.Item label="取消发起方">
                {detail.cancelledBy === 'CUSTOMER' ? '客户' : detail.cancelledBy === 'SELLER' ? '商家' : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="取消时间">{detail.cancelledAt ? formatDate(detail.cancelledAt) : '—'}</Descriptions.Item>
              <Descriptions.Item label="取消原因">{detail.cancelReason || '—'}</Descriptions.Item>
            </Descriptions>
            <Table
              rowKey="productId"
              size="small"
              pagination={false}
              dataSource={detail.items}
              columns={[
                { title: '商品快照', dataIndex: 'productName', key: 'productName' },
                { title: '单价', dataIndex: 'unitPrice', key: 'unitPrice', render: (price: string) => `¥${price}` },
                { title: '数量', dataIndex: 'quantity', key: 'quantity' },
                { title: '小计', dataIndex: 'lineAmount', key: 'lineAmount', render: (amount: string) => `¥${amount}` },
              ]}
            />
          </Space>
        )}
      </Modal>

      <Modal
        title="取消整张订单"
        open={Boolean(cancelTarget)}
        onCancel={() => setCancelTarget(undefined)}
        onOk={() => void performCancel()}
        okText="确认取消"
        cancelText="返回"
        okButtonProps={{ danger: true }}
        confirmLoading={cancelSubmitting}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Typography.Text>
            确认取消订单 {cancelTarget?.orderNo}？取消后不能恢复，不会把商品加回购物车。
          </Typography.Text>
          <Input.TextArea
            maxLength={500}
            showCount
            value={cancelReason}
            onChange={(event) => setCancelReason(event.target.value)}
            placeholder="取消原因（选填）"
            rows={3}
          />
        </Space>
      </Modal>
    </main>
  )
}
