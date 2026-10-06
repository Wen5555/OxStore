import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Image,
  Popconfirm,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd'
import { useNavigate } from 'react-router-dom'
import {
  freezeProduct,
  getAdminCurrentProduct,
  unfreezeProduct,
} from '../../api/product'
import type { Product, ProductStatus } from '../../types/product'

const { Paragraph, Text, Title } = Typography

const statusLabels: Record<ProductStatus, string> = {
  ONLINE: '在售',
  RESTORED_ONLINE: '恢复在售',
  FROZEN: '已冻结',
  SOLD: '已售出',
}

function formatDate(value: string | null) {
  if (!value) return '-'

  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

export default function CurrentProductPage() {
  const navigate = useNavigate()
  const [product, setProduct] = useState<Product | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  const loadProduct = async (showSpinner = true) => {
    try {
      if (showSpinner) setLoading(true)
      setLoadError(false)
      setProduct(await getAdminCurrentProduct())
    } catch (error) {
      console.error('获取当前商品失败:', error)
      setLoadError(true)
    } finally {
      if (showSpinner) setLoading(false)
    }
  }

  useEffect(() => {
    void loadProduct()
  }, [])

  const handleStatusChange = async (action: 'freeze' | 'unfreeze') => {
    try {
      setActionLoading(true)
      if (action === 'freeze') {
        await freezeProduct()
        message.success('商品已冻结')
      } else {
        await unfreezeProduct()
        message.success('商品已解冻')
      }
      await loadProduct(false)
    } catch (error) {
      console.error('更新商品状态失败:', error)
    } finally {
      setActionLoading(false)
    }
  }

  const isManuallyFrozen = product?.status === 'FROZEN' && product.freezeSource === 'MANUAL'
  const canFreeze = product?.status === 'ONLINE' || product?.status === 'RESTORED_ONLINE'

  return (
    <main style={{ maxWidth: 1040, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <Title level={2} style={{ margin: 0 }}>当前商品</Title>
          <Space wrap>
            <Button onClick={() => void loadProduct()}>刷新</Button>
            <Button onClick={() => navigate('/admin/products/history')}>商品历史</Button>
            <Button type="primary" onClick={() => navigate('/admin/products/publish')}>发布商品</Button>
          </Space>
        </div>

        {loading ? (
          <div style={{ padding: 64, textAlign: 'center' }}><Spin size="large" /></div>
        ) : loadError ? (
          <Card>
            <Empty description="当前商品加载失败">
              <Button type="primary" onClick={() => void loadProduct()}>重试</Button>
            </Empty>
          </Card>
        ) : !product ? (
          <Card>
            <Empty description="目前没有在售商品">
              <Button type="primary" onClick={() => navigate('/admin/products/publish')}>发布商品</Button>
            </Empty>
          </Card>
        ) : (
          <Card>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 360px), 1fr))', gap: 28 }}>
              <div style={{ minHeight: 280, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f5f5f5' }}>
                {product.imagePath ? (
                  <Image
                    src={product.imagePath}
                    alt={product.name}
                    width="100%"
                    height={360}
                    style={{ objectFit: 'contain' }}
                  />
                ) : <Text type="secondary">暂无商品图片</Text>}
              </div>

              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <div>
                  <Space wrap>
                    <Title level={3} style={{ margin: 0 }}>{product.name}</Title>
                    <Tag color={product.status === 'FROZEN' ? 'orange' : product.status === 'SOLD' ? 'default' : 'green'}>
                      {statusLabels[product.status]}
                    </Tag>
                  </Space>
                  <Title level={2} style={{ margin: '12px 0 0', color: '#cf1322' }}>
                    ¥{Number(product.price).toFixed(2)}
                  </Title>
                </div>

                <Descriptions column={1} bordered size="small">
                  <Descriptions.Item label="商品编号">#{product.id}</Descriptions.Item>
                  <Descriptions.Item label="发布时间">{formatDate(product.publishedAt)}</Descriptions.Item>
                  <Descriptions.Item label="状态更新时间">{formatDate(product.statusUpdatedAt)}</Descriptions.Item>
                  {product.status === 'FROZEN' && (
                    <Descriptions.Item label="冻结来源">
                      {product.freezeSource === 'TRADE' ? '交易冻结' : '卖家手动冻结'}
                    </Descriptions.Item>
                  )}
                  {product.status === 'SOLD' && (
                    <Descriptions.Item label="售出时间">{formatDate(product.soldAt)}</Descriptions.Item>
                  )}
                </Descriptions>

                <div>
                  <Text strong>商品描述</Text>
                  <Paragraph style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
                    {product.description || <Text type="secondary">暂无描述</Text>}
                  </Paragraph>
                </div>

                {product.status === 'FROZEN' && product.freezeSource === 'TRADE' && (
                  <Alert
                    type="warning"
                    showIcon
                    message="商品因交易流程冻结，需完成当前交易后才能恢复。"
                  />
                )}

                <Space wrap>
                  <Button onClick={() => navigate(`/admin/products/${product.id}/records`)}>查看完整记录</Button>
                  {canFreeze && (
                    <Popconfirm
                      title="确认冻结当前商品？"
                      description="冻结后买家将不能提交新的购买意向。"
                      okText="确认冻结"
                      cancelText="取消"
                      onConfirm={() => handleStatusChange('freeze')}
                    >
                      <Button danger loading={actionLoading}>冻结商品</Button>
                    </Popconfirm>
                  )}
                  {isManuallyFrozen && (
                    <Popconfirm
                      title="确认恢复商品在售？"
                      okText="确认解冻"
                      cancelText="取消"
                      onConfirm={() => handleStatusChange('unfreeze')}
                    >
                      <Button type="primary" loading={actionLoading}>解冻并恢复在售</Button>
                    </Popconfirm>
                  )}
                </Space>
              </Space>
            </div>
          </Card>
        )}
      </Space>
    </main>
  )
}
