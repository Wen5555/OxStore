import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, Pagination, Popconfirm, Space, Spin, Tag, Typography, message } from 'antd'
import { useParams } from 'react-router-dom'
import { confirmFail, confirmSuccess, getProductIntentQueue, startTrade } from '../../api/intent'
import { ApiError } from '../../api/request'
import type { Intent } from '../../types/intent'

const PAGE_SIZE = 10

export default function ProductIntentQueuePage() {
  const { id } = useParams()
  const productId = Number(id)
  const [items, setItems] = useState<Intent[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const [action, setAction] = useState('')

  const load = async () => {
    if (!Number.isInteger(productId) || productId <= 0) {
      setLoadError(true)
      setLoading(false)
      return
    }
    try {
      setLoading(true)
      setLoadError(false)
      const result = await getProductIntentQueue(productId, page, PAGE_SIZE)
      setItems(result.items)
      setTotal(result.total)
    } catch (error) {
      console.error('获取商品意向队列失败:', error)
      setLoadError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [productId, page, retryCount])

  const currentIntent = items.find((intent) => intent.status === 'IN_TRANSACTION' || intent.position === 0)
  const queue = items.filter((intent) => intent.status === 'QUEUING')

  const perform = async (operation: 'start' | 'success' | 'REQUEUE' | 'DISCARD') => {
    try {
      setAction(operation)
      if (operation === 'start' && queue[0]) {
        await startTrade(queue[0].id)
        message.success('已开始处理队首意向')
      } else if (operation === 'success' && currentIntent) {
        await confirmSuccess(currentIntent.id)
        message.success('已确认交易成功')
      } else if ((operation === 'REQUEUE' || operation === 'DISCARD') && currentIntent) {
        await confirmFail(currentIntent.id, operation)
        message.success(operation === 'REQUEUE' ? '已记录失败并重新排队' : '已记录失败并作废意向')
      }
      await load()
    } catch (error) {
      console.error('更新交易状态失败:', error)
      if (error instanceof ApiError && [40901, 40902, 40904, 40905].includes(error.code ?? 0)) {
        await load()
      }
    } finally {
      setAction('')
    }
  }

  return (
    <main style={{ maxWidth: 960, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Typography.Title level={2}>商品意向队列</Typography.Title>
        {loading ? <div style={{ padding: 48, textAlign: 'center' }}><Spin size="large" /></div> : (
          <>
            {loadError && <Alert type="error" showIcon message="商品意向队列加载失败。" action={<Button onClick={() => setRetryCount((count) => count + 1)}>重试</Button>} />}
            {!loadError && <>
            <Card title="交易中">
              {currentIntent ? (
                <Space direction="vertical">
                  <Space wrap><Tag color="blue">交易中</Tag><Typography.Text strong>{currentIntent.customerUsername}</Typography.Text></Space>
                  <Space wrap>
                    <Button type="primary" loading={action === 'success'} onClick={() => void perform('success')}>确认成功</Button>
                    <Popconfirm title="将该意向重新排到队尾？" onConfirm={() => void perform('REQUEUE')} okText="重新排队" cancelText="取消">
                      <Button danger loading={action === 'REQUEUE'}>失败并重新排队</Button>
                    </Popconfirm>
                    <Popconfirm title="作废该意向？" onConfirm={() => void perform('DISCARD')} okText="作废" cancelText="取消">
                      <Button danger loading={action === 'DISCARD'}>失败并作废</Button>
                    </Popconfirm>
                  </Space>
                </Space>
              ) : <Empty description="当前没有进行中的交易" />}
            </Card>
            <Card title={`排队意向（${total}）`} extra={queue.length > 0 && !currentIntent ? <Button type="primary" loading={action === 'start'} onClick={() => void perform('start')}>开始处理队首</Button> : undefined}>
              {!queue.length ? <Empty description="暂无排队意向" /> : (
                <Space direction="vertical" style={{ width: '100%' }}>
                  {queue.map((intent) => <div key={intent.id}><Tag color="orange">第 {intent.position} 位</Tag><Typography.Text strong>{intent.customerUsername}</Typography.Text></div>)}
                </Space>
              )}
              {total > PAGE_SIZE && <Pagination style={{ marginTop: 20 }} current={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} />}
            </Card>
            </>}
          </>
        )}
      </Space>
    </main>
  )
}
