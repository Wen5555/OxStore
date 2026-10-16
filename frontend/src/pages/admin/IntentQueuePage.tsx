import { useEffect, useState } from 'react'
import { Button, Card, Empty, Popconfirm, Space, Spin, Tag, Typography, message } from 'antd'
import {
  confirmFail,
  confirmSuccess,
  getIntentQueue,
  startTrade,
} from '../../api/intent'
import type { Intent } from '../../types/intent'

const { Text } = Typography

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

export default function IntentQueuePage() {
  const [intents, setIntents] = useState<Intent[]>([])
  const [loading, setLoading] = useState(true)
  const [action, setAction] = useState('')

  const loadQueue = async () => {
    try {
      setLoading(true)
      setIntents(await getIntentQueue())
    } catch (error) {
      console.error('获取意向队列失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadQueue()
  }, [])

  const currentIntent = intents.find(
    (intent) => intent.status === 'IN_TRANSACTION' || intent.position === 0,
  ) ?? null
  const waitingIntents = intents
    .filter((intent) => intent.status === 'QUEUING')
    .sort((left, right) => (left.position ?? Infinity) - (right.position ?? Infinity))

  const handleStart = async () => {
    const nextIntent = waitingIntents[0]
    if (!nextIntent || currentIntent) return

    try {
      setAction('start')
      await startTrade(nextIntent.id)
      message.success('已开始处理队首意向')
      await loadQueue()
    } catch (error) {
      console.error('开始交易失败:', error)
    } finally {
      setAction('')
    }
  }

  const handleSuccess = async () => {
    if (!currentIntent?.currentTradeAttemptId) return

    try {
      setAction('success')
      await confirmSuccess(currentIntent.id, currentIntent.currentTradeAttemptId)
      message.success('已确认交易成功')
      await loadQueue()
    } catch (error) {
      console.error('确认交易成功失败:', error)
    } finally {
      setAction('')
    }
  }

  const handleFail = async (failAction: 'REQUEUE' | 'DISCARD') => {
    if (!currentIntent?.currentTradeAttemptId) return

    try {
      setAction(failAction)
      const nextIntent = await confirmFail(
        currentIntent.id,
        failAction,
        currentIntent.currentTradeAttemptId,
      )

      setIntents((current) => [
        ...(nextIntent ? [nextIntent] : []),
        ...current.filter((intent) => intent.id !== currentIntent.id && intent.id !== nextIntent?.id),
      ])
      message.success(nextIntent ? '已记录失败并递补下一位' : '已记录失败，队列已清空')
      await loadQueue()
    } catch (error) {
      console.error('确认交易失败:', error)
    } finally {
      setAction('')
    }
  }

  if (loading) {
    return <div style={{ padding: 48, textAlign: 'center' }}><Spin size="large" /></div>
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ margin: 0 }}>购买意向队列</h1>
          <Button onClick={loadQueue} loading={loading}>刷新</Button>
        </div>

        <Card title="交易中">
          {currentIntent ? (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Space wrap>
                <Tag color="blue">交易中</Tag>
                <Text strong>{currentIntent.buyerName}</Text>
                <Text>{currentIntent.buyerPhone}</Text>
                <Text type="secondary">意向编号 #{currentIntent.id}</Text>
                <Text type="secondary">提交时间：{formatDate(currentIntent.submittedAt)}</Text>
              </Space>
              <Space wrap>
                <Button
                  type="primary"
                  onClick={handleSuccess}
                  loading={action === 'success'}
                  disabled={currentIntent.currentTradeAttemptId === null}
                >
                  确认成功
                </Button>
                <Popconfirm
                  title="确认交易失败并递补下一位？"
                  onConfirm={() => handleFail('REQUEUE')}
                  okText="递补到队尾"
                  cancelText="取消"
                >
                  <Button danger loading={action === 'REQUEUE'} disabled={currentIntent.currentTradeAttemptId === null}>
                    失败并重新排队
                  </Button>
                </Popconfirm>
                <Popconfirm
                  title="确认交易失败并移除此意向？"
                  onConfirm={() => handleFail('DISCARD')}
                  okText="失败并移除"
                  cancelText="取消"
                >
                  <Button danger loading={action === 'DISCARD'} disabled={currentIntent.currentTradeAttemptId === null}>
                    失败并放弃
                  </Button>
                </Popconfirm>
              </Space>
              {currentIntent.currentTradeAttemptId === null && (
                <Text type="warning">当前交易缺少尝试记录，暂不能确认结果。</Text>
              )}
            </Space>
          ) : (
            <Empty description="当前没有进行中的交易" />
          )}
        </Card>

        <Card
          title={`排队意向（${waitingIntents.length}）`}
          extra={waitingIntents.length > 0 && !currentIntent ? (
            <Button type="primary" onClick={handleStart} loading={action === 'start'}>
              开始处理队首
            </Button>
          ) : null}
        >
          {waitingIntents.length > 0 ? (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              {waitingIntents.map((intent) => (
                <div key={intent.id} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, borderBottom: '1px solid #f0f0f0', paddingBottom: 12 }}>
                  <Space wrap>
                    <Tag color="orange">第 {intent.position ?? '-'} 位</Tag>
                    <Text strong>{intent.buyerName}</Text>
                    <Text>{intent.buyerPhone}</Text>
                    <Text type="secondary">提交时间：{formatDate(intent.submittedAt)}</Text>
                  </Space>
                  <Text type="secondary">#{intent.id}</Text>
                </div>
              ))}
            </Space>
          ) : (
            <Empty description="暂无排队意向" />
          )}
        </Card>
      </Space>
    </div>
  )
}
