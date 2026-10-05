import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Space,
  Spin,
  Tag,
  message,
} from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import {
  cancelIntent,
  queryIntent,
  modifyIntent,
} from '../../api/intent'
import type { Intent, IntentStatus } from '../../types/intent'

interface IntentFormValues {
  buyerName: string
  buyerPhone: string
}

export default function IntentQueryPage() {
  const { code } = useParams<{ code: string }>()
  const navigate = useNavigate()

  const [intent, setIntent] = useState<Intent | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [canceling, setCanceling] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [codeInput, setCodeInput] = useState('')

  const [form] = Form.useForm<IntentFormValues>()

  // 查询购买意向
  const loadIntent = async () => {
    if (!code) {
      setIntent(null)
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setIntent(null)

      const data = await queryIntent(code)

      setIntent(data)
    } catch (error) {
      console.error('查询购买意向失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadIntent()
  }, [code])

  // 打开修改信息弹窗
  const openEdit = () => {
    if (!intent) return

    form.setFieldsValue({
      buyerName: '',
      buyerPhone: '',
    })

    setEditOpen(true)
  }

  // 修改购买意向
  const handleUpdate = async (values: IntentFormValues) => {
    if (!intent || !code) return

    const buyerName = values.buyerName?.trim()
    const buyerPhone = values.buyerPhone?.trim()
    const changes: { buyerName?: string; buyerPhone?: string } = {}

    if (buyerName) changes.buyerName = buyerName
    if (buyerPhone) changes.buyerPhone = buyerPhone
    if (Object.keys(changes).length === 0) {
      message.warning('请至少填写一项要修改的信息')
      return
    }

    try {
      setSaving(true)

      await modifyIntent(code, changes)

      message.success('信息修改成功')

      setEditOpen(false)

      await loadIntent()
    } catch (error) {
      console.error('修改购买意向失败:', error)
    } finally {
      setSaving(false)
    }
  }

  // 撤销购买意向
  const handleCancel = async () => {
    if (!intent || !code) return

    try {
      setCanceling(true)

      await cancelIntent(code)

      message.success('购买意向已撤销')
      setIntent({ ...intent, status: 'CANCELLED', position: null })
    } catch (error) {
      console.error('撤销购买意向失败:', error)
    } finally {
      setCanceling(false)
    }
  }

  const handleQuery = () => {
    const value = codeInput.trim()
    if (value) navigate(`/intent/${encodeURIComponent(value)}`)
  }

  // 状态标签
  const getStatusTag = (status: IntentStatus) => {
    switch (status) {
      case 'IN_TRANSACTION':
        return <Tag color="blue">交易中</Tag>

      case 'QUEUING':
        return <Tag color="orange">排队中</Tag>

      case 'SUCCESS':
        return <Tag color="green">交易成功</Tag>

      case 'FAILED':
        return <Tag color="red">交易失败</Tag>

      case 'CANCELLED':
        return <Tag>已撤销</Tag>

      default:
        return <Tag>{status}</Tag>
    }
  }

  // 加载中
  if (loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
        }}
      >
        <Spin size="large" />
      </div>
    )
  }

  if (!code) {
    return (
      <div style={{ minHeight: '100vh', padding: 40, background: '#f5f5f5' }}>
        <Card title="查询购买意向" style={{ maxWidth: 560, margin: '80px auto' }}>
          <Space.Compact style={{ width: '100%' }}>
            <Input
              aria-label="购买意向口令码"
              placeholder="请输入购买意向口令码"
              value={codeInput}
              onChange={(event) => setCodeInput(event.target.value)}
              onPressEnter={handleQuery}
            />
            <Button type="primary" onClick={handleQuery} disabled={!codeInput.trim()}>
              查询
            </Button>
          </Space.Compact>
          <div style={{ marginTop: 16, textAlign: 'center' }}>
            <Button type="link" onClick={() => navigate('/')}>返回商品页面</Button>
          </div>
        </Card>
      </div>
    )
  }

  // 没有找到购买意向
  if (!intent) {
    return (
      <div
        style={{
          minHeight: '100vh',
          padding: 40,
          background: '#f5f5f5',
        }}
      >
        <Card
          style={{
            maxWidth: 700,
            margin: '80px auto',
          }}
        >
          <Empty description="未找到该购买意向" />

          <div
            style={{
              textAlign: 'center',
              marginTop: 20,
            }}
          >
            <Button onClick={() => navigate('/intent')}>
              重新输入口令码
            </Button>
            <Button onClick={() => navigate('/')}>
              返回商品页面
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#f5f5f5',
        padding: '40px 20px',
      }}
    >
      <Card
        title="购买意向查询"
        style={{
          maxWidth: 700,
          margin: '40px auto',
        }}
      >
        {/* 口令码 */}
        <div
          style={{
            textAlign: 'center',
            marginBottom: 30,
          }}
        >
          <div
            style={{
              color: '#666',
              marginBottom: 10,
            }}
          >
            您的口令码
          </div>

          <div
            style={{
              fontSize: 32,
              fontWeight: 'bold',
              letterSpacing: 4,
            }}
          >
            {code}
          </div>
        </div>

        {/* 购买意向信息 */}
        <Descriptions
          bordered
          column={1}
          labelStyle={{
            width: 140,
            fontWeight: 500,
          }}
        >
          <Descriptions.Item label="姓名">
            {intent.buyerName}
          </Descriptions.Item>

          <Descriptions.Item label="手机号">
            {intent.buyerPhone}
          </Descriptions.Item>

          <Descriptions.Item label="当前状态">
            {getStatusTag(intent.status)}
          </Descriptions.Item>

          {intent.position !== undefined &&
            intent.position !== null &&
            (intent.status === 'QUEUING' ||
              intent.status === 'IN_TRANSACTION') && (
              <Descriptions.Item label="排队位置">
                {intent.position === 0
                  ? '正在交易'
                  : `第 ${intent.position} 位`}
              </Descriptions.Item>
            )}
        </Descriptions>

        {/* 操作按钮 */}
        <div
          style={{
            marginTop: 30,
            textAlign: 'center',
          }}
        >
          <Space>
            {intent.status === 'QUEUING' && (
              <>
                <Button onClick={openEdit}>
                  修改信息
                </Button>

                <Popconfirm
                  title="确定要撤销购买意向吗？"
                  description="撤销后将无法继续排队。"
                  onConfirm={handleCancel}
                  okText="确定撤销"
                  cancelText="取消"
                >
                  <Button
                    danger
                    loading={canceling}
                  >
                    撤销意向
                  </Button>
                </Popconfirm>
              </>
            )}

            <Button onClick={() => navigate('/')}>
              返回商品页面
            </Button>
          </Space>
        </div>
      </Card>

      {/* 修改信息弹窗 */}
      <Modal
        title="修改购买信息"
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleUpdate}
        >
          <Form.Item
            label="姓名"
            name="buyerName"
            rules={[
              {
                validator: (_, value) => {
                  if (!value || value.trim().length > 0) {
                    return Promise.resolve()
                  }

                  return Promise.reject(
                    new Error('姓名不能全是空格'),
                  )
                },
              },
            ]}
          >
            <Input
              placeholder="请输入姓名"
              maxLength={20}
            />
          </Form.Item>

          <Form.Item
            label="手机号"
            name="buyerPhone"
            rules={[
              {
                validator: (_, value) => {
                  if (!value || /^\d{11}$/.test(value.trim())) {
                    return Promise.resolve()
                  }

                  return Promise.reject(new Error('请输入11位数字'))
                },
              },
            ]}
          >
            <Input
              placeholder="请输入11位手机号"
              maxLength={11}
            />
          </Form.Item>

          <Form.Item
            style={{
              marginBottom: 0,
            }}
          >
            <Space>
              <Button
                onClick={() => setEditOpen(false)}
              >
                取消
              </Button>

              <Button
                type="primary"
                htmlType="submit"
                loading={saving}
              >
                保存修改
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}