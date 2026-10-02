import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  Empty,
  Form,
  Input,
  Modal,
  Spin,
  Tag,
  message,
} from 'antd'
import { useNavigate } from 'react-router-dom'
import { getCurrentProduct } from '../../api/product'
import { submitIntent } from '../../api/intent'
import type { Product } from '../../types/product'

interface IntentFormValues {
  buyerName: string
  buyerPhone: string
}

export default function ProductPage() {
  const [product, setProduct] = useState<Product | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const [form] = Form.useForm<IntentFormValues>()
  const [modalOpen, setModalOpen] = useState(false)

  const [intentCode, setIntentCode] = useState('')
  const [position, setPosition] = useState<number | null>(null)

  const navigate = useNavigate()

  // 获取当前商品
  const loadProduct = async () => {
    try {
      setLoading(true)

      const data = await getCurrentProduct()

      setProduct(data)
    } catch (error) {
      console.error('获取商品失败:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProduct()
  }, [])

  // 提交购买意向
  const handleSubmitIntent = async (values: IntentFormValues) => {
    // 冻结状态下禁止提交
    if (product?.status === 'FROZEN') {
      message.warning('商品已冻结，暂时无法提交购买意向')
      return
    }

    try {
      setSubmitting(true)

      const result = await submitIntent({
        buyerName: values.buyerName.trim(),
        buyerPhone: values.buyerPhone.trim(),
      })

      setIntentCode(result.code)
      setPosition(result.position)

      setModalOpen(true)

      message.success('购买意向提交成功')
    } catch (error) {
      console.error('提交购买意向失败:', error)
    } finally {
      setSubmitting(false)
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

  // 没有当前商品
  if (!product) {
    return (
      <div
        style={{
          minHeight: '100vh',
          padding: 40,
          background: '#f5f5f5',
        }}
      >
        <Card style={{ maxWidth: 800, margin: '80px auto' }}>
          <Empty description="目前没有正在出售的商品" />
        </Card>
      </div>
    )
  }

  // 判断商品状态
  const isFrozen = product.status === 'FROZEN'

  const isOnline =
    product.status === 'ONLINE' ||
    product.status === 'RESTORED_ONLINE'

  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#f5f5f5',
        padding: '40px 20px',
      }}
    >
      <div
        style={{
          maxWidth: 1000,
          margin: '0 auto',
        }}
      >
        {/* 页面标题 */}
        <div
          style={{
            textAlign: 'center',
            marginBottom: 30,
          }}
        >
          <h1 style={{ marginBottom: 8 }}>
            OxStore
          </h1>

          <div style={{ color: '#666' }}>
            商品购买意向登记
          </div>
        </div>

        {/* 商品卡片 */}
        <Card>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))',
              gap: 24,
              alignItems: 'center',
            }}
          >
            {/* 商品图片 */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                background: '#fafafa',
                borderRadius: 8,
                width: '100%',
                aspectRatio: '4 / 3',
                overflow: 'hidden',
              }}
            >
              {product.imagePath ? (
                <img
                  src={product.imagePath}
                  alt={product.name}
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover',
                  }}
                />
              ) : (
                <Empty description="暂无商品图片" />
              )}
            </div>

            {/* 商品信息 */}
            <div>
              {/* 商品状态 */}
              {isFrozen ? (
                <Tag
                  color="orange"
                  style={{
                    marginBottom: 15,
                    fontSize: 14,
                    padding: '4px 10px',
                  }}
                >
                  已冻结
                </Tag>
              ) : (
                <Tag
                  color="green"
                  style={{
                    marginBottom: 15,
                    fontSize: 14,
                    padding: '4px 10px',
                  }}
                >
                  在售
                </Tag>
              )}

              <h2
                style={{
                  fontSize: 28,
                  marginBottom: 20,
                }}
              >
                {product.name}
              </h2>

              <div
                style={{
                  fontSize: 30,
                  fontWeight: 'bold',
                  color: '#d4380d',
                  marginBottom: 25,
                }}
              >
                ¥{Number(product.price).toFixed(2)}
              </div>

              <div
                style={{
                  color: '#666',
                  lineHeight: 1.8,
                  marginBottom: 30,
                  whiteSpace: 'pre-wrap',
                }}
              >
                {product.description || '暂无商品描述'}
              </div>

              {/* 冻结状态 */}
              {isFrozen && (
                <Card
                  type="inner"
                  style={{
                    marginBottom: 20,
                    background: '#fff7e6',
                    borderColor: '#ffd591',
                  }}
                >
                  <div
                    style={{
                      textAlign: 'center',
                      color: '#d46b08',
                      fontSize: 16,
                      fontWeight: 'bold',
                    }}
                  >
                    商品已冻结
                  </div>

                  <div
                    style={{
                      textAlign: 'center',
                      color: '#8c8c8c',
                      marginTop: 8,
                    }}
                  >
                    当前暂时无法提交购买意向
                  </div>
                </Card>
              )}

              {/* 在线状态：显示购买意向表单 */}
              {isOnline && (
                <Card
                  type="inner"
                  title="提交购买意向"
                >
                  <Form
                    form={form}
                    layout="vertical"
                    onFinish={handleSubmitIntent}
                    autoComplete="off"
                  >
                    <Form.Item
                      label="姓名"
                      name="buyerName"
                      rules={[
                        {
                          required: true,
                          message: '请输入姓名',
                        },
                        {
                          validator: (_, value) => {
                            if (
                              value &&
                              value.trim().length > 0
                            ) {
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
                        placeholder="请输入您的姓名"
                        maxLength={50}
                      />
                    </Form.Item>

                    <Form.Item
                      label="手机号"
                      name="buyerPhone"
                      rules={[
                        {
                          required: true,
                          message: '请输入手机号',
                        },
                        {
                          pattern: /^\d{11}$/,
                          message: '请输入11位数字',
                        },
                      ]}
                    >
                      <Input
                        placeholder="请输入11位手机号"
                        maxLength={11}
                      />
                    </Form.Item>

                    <Button
                      type="primary"
                      htmlType="submit"
                      loading={submitting}
                      block
                      size="large"
                    >
                      提交购买意向
                    </Button>
                  </Form>
                </Card>
              )}
            </div>
          </div>
        </Card>
      </div>

      {/* 提交成功弹窗 */}
      <Modal
        title="购买意向提交成功"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={[
          <Button
            key="close"
            onClick={() => setModalOpen(false)}
          >
            关闭
          </Button>,

          <Button
            key="query"
            type="primary"
            onClick={() => {
              setModalOpen(false)
              navigate(`/intent/${intentCode}`)
            }}
          >
            查看排队进度
          </Button>,
        ]}
      >
        <div
          style={{
            textAlign: 'center',
            padding: '20px 0',
          }}
        >
          <div
            style={{
              color: '#666',
              marginBottom: 10,
            }}
          >
            您的购买意向口令码
          </div>

          <div
            style={{
              fontSize: 32,
              fontWeight: 'bold',
              letterSpacing: 4,
              marginBottom: 20,
            }}
          >
            {intentCode}
          </div>

          {position !== null && (
            <div style={{ color: '#666' }}>
              当前排队位置：
              <span
                style={{
                  color: '#1677ff',
                  fontWeight: 'bold',
                  marginLeft: 5,
                }}
              >
                {position}
              </span>
            </div>
          )}

          <div
            style={{
              marginTop: 20,
              color: '#999',
            }}
          >
            请保存好您的口令码，可凭口令码查询购买进度。
          </div>
        </div>
      </Modal>
    </div>
  )
}