import { useEffect, useState } from 'react'
import { Alert, Button, Card, Descriptions, Empty, Modal, Pagination, Popconfirm, Space, Spin, Table, Tag, Typography, Input, message } from 'antd'
import { ApiError } from '../../api/request'
import { advanceAdminOrder, cancelAdminOrder, getAdminOrder, getAdminOrders } from '../../api/orders'
import type { Order, OrderAction, OrderPage, OrderStatus } from '../../types/challengeB'

const PAGE_SIZE = 10

const statusLabels: Record<OrderStatus, string> = {
  PLACED: '待确认',
  CONFIRMED: '待备货',
  PREPARED: '待发货',
  SHIPPED: '已开始发货',
  COMPLETED: '已完成',
  CANCELLED: '已取消',
}

const actionLabels: Record<OrderAction, string> = {
  CONFIRM: '确认订单',
  PREPARE: '完成备货',
  SHIP: '开始发货',
  COMPLETE: '完成交易',
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

export default function AdminOrdersPage() {
  const [data, setData] = useState<OrderPage>()
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const [busyAction, setBusyAction] = useState<string>()
  const [detail, setDetail] = useState<Order>()
  const [detailLoading, setDetailLoading] = useState(false)
  const [cancelTarget, setCancelTarget] = useState<Order>()
  const [cancelReason, setCancelReason] = useState('')

  const load = async () => {
    setLoading(true)
    setLoadError(false)
    try {
      setData(await getAdminOrders(page, PAGE_SIZE))
    } catch (error) {
      console.error('获取订单管理列表失败:', error)
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
      setDetail(await getAdminOrder(orderId))
    } catch (error) {
      console.error('获取订单详情失败:', error)
    } finally {
      setDetailLoading(false)
    }
  }

  const performAction = async (order: Order, action: OrderAction) => {
    const key = `${order.orderId}:${action}`
    setBusyAction(key)
    try {
      await advanceAdminOrder(order.orderId, action, order.status)
      message.success(action === 'COMPLETE' ? '订单已完成' : '订单状态已更新')
      await load()
      if (detail?.orderId === order.orderId) await openDetail(order.orderId)
    } catch (error) {
      console.error('更新订单状态失败:', error)
      if (error instanceof ApiError && [40904, 40911].includes(error.code ?? 0)) {
        await load()
        if (detail?.orderId === order.orderId) await openDetail(order.orderId)
      }
    } finally {
      setBusyAction(undefined)
    }
  }

  const performCancellation = async () => {
    if (!cancelTarget) return
    const order = cancelTarget
    setBusyAction(`${order.orderId}:CANCEL`)
    try {
      const result = await cancelAdminOrder(order.orderId, order.status, cancelReason)
      message.success(result.message)
      setCancelTarget(undefined)
      setCancelReason('')
      await load()
      if (detail?.orderId === order.orderId) await openDetail(order.orderId)
    } catch (error) {
      console.error('取消订单失败:', error)
      if (error instanceof ApiError && [40904, 40911].includes(error.code ?? 0)) {
        await load()
        if (detail?.orderId === order.orderId) await openDetail(order.orderId)
        setCancelTarget(undefined)
        setCancelReason('')
      }
    } finally {
      setBusyAction(undefined)
    }
  }

  const actionButtons = (order: Order) => (
    <Space wrap>
      <Button type="link" onClick={() => void openDetail(order.orderId)}>详情</Button>
      {order.allowedActions.filter((action): action is OrderAction => action !== 'CANCEL').map((action) => (
        <Popconfirm
          key={action}
          title={`确认${actionLabels[action]}？`}
          onConfirm={() => void performAction(order, action)}
          okText="确认"
          cancelText="返回"
        >
          <Button type="link" loading={busyAction === `${order.orderId}:${action}`}>
            {actionLabels[action]}
          </Button>
        </Popconfirm>
      ))}
      {order.allowedActions.includes('CANCEL') && (
        <Button danger type="link" onClick={() => {
          setCancelReason('')
          setCancelTarget(order)
        }}>
          取消订单
        </Button>
      )}
    </Space>
  )

  return (
    <main style={{ maxWidth: 1300, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Typography.Title level={2} style={{ margin: 0 }}>订单管理</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            按订单状态执行商家操作。订单只读展示下单快照，不包含物流或凭证信息。
          </Typography.Paragraph>
        </div>
        <Card>
          {loadError ? (
            <Alert type="error" showIcon message="订单列表加载失败。" action={
              <Button onClick={() => setRetryCount((count) => count + 1)}>重试</Button>
            } />
          ) : !loading && !data?.items.length ? (
            <Empty description="暂无订单" />
          ) : (
            <>
              <Table<Order>
                rowKey="orderId"
                loading={loading}
                dataSource={data?.items ?? []}
                pagination={false}
                scroll={{ x: 1100 }}
                columns={[
                  { title: '订单号', dataIndex: 'orderNo', key: 'orderNo' },
                  { title: '顾客编号', dataIndex: 'customerId', key: 'customerId' },
                  {
                    title: '商品摘要',
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
                  { title: '创建时间', dataIndex: 'createdAt', key: 'createdAt', render: formatDate },
                  { title: '操作', key: 'actions', render: (_, order) => actionButtons(order) },
                ]}
              />
              {Boolean(data?.total) && (
                <Pagination
                  style={{ marginTop: 20 }}
                  current={page}
                  pageSize={PAGE_SIZE}
                  total={data?.total}
                  onChange={setPage}
                />
              )}
            </>
          )}
        </Card>
      </Space>

      <Modal
        title="订单详情"
        open={Boolean(detail) || detailLoading}
        footer={<Button onClick={() => setDetail(undefined)}>关闭</Button>}
        onCancel={() => setDetail(undefined)}
        confirmLoading={detailLoading}
        width={760}
      >
        {detailLoading ? <div style={{ padding: 32, textAlign: 'center' }}><Spin /></div> : detail && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="订单号">{detail.orderNo}</Descriptions.Item>
              <Descriptions.Item label="订单状态">
                <Tag color={statusColor(detail.status)}>{statusLabels[detail.status]}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="顾客编号">{detail.customerId}</Descriptions.Item>
              <Descriptions.Item label="创建时间">{formatDate(detail.createdAt)}</Descriptions.Item>
              <Descriptions.Item label="订单总额">¥{detail.totalAmount}</Descriptions.Item>
              <Descriptions.Item label="取消发起方">{detail.cancelledBy ?? '—'}</Descriptions.Item>
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
        onOk={() => void performCancellation()}
        okText="确认取消"
        cancelText="返回"
        okButtonProps={{ danger: true }}
        confirmLoading={busyAction === `${cancelTarget?.orderId}:CANCEL`}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <Typography.Text>
            确认取消订单 {cancelTarget?.orderNo}？取消将按订单快照回补库存，不能部分取消。
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
