import { useEffect, useState } from 'react'
import { Alert, Button, Card, Descriptions, Empty, Image, Space, Spin, Typography, message } from 'antd'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getProduct, submitPurchaseIntent } from '../../api/catalog'
import type { Product } from '../../types/product'

function hasReadableContent(html: string) {
  const element = document.createElement('div')
  element.innerHTML = html
  return Boolean(element.textContent?.replace(/\s/g, '').length || element.querySelector('img'))
}

export default function ProductDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [product, setProduct] = useState<Product>()
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [unavailable, setUnavailable] = useState(false)
  const loggedIn = Boolean(localStorage.getItem('customer_token'))

  useEffect(() => {
    if (!id || !/^\d+$/.test(id)) {
      setUnavailable(true)
      setLoading(false)
      return
    }
    getProduct(Number(id))
      .then(setProduct)
      .catch((error) => {
        console.error('获取商品详情失败:', error)
        setUnavailable(true)
      })
      .finally(() => setLoading(false))
  }, [id])

  const submitIntent = async () => {
    if (!loggedIn) {
      navigate('/login', { state: { from: `/products/${id}` } })
      return
    }
    if (!product || product.status !== 'ONLINE' || !product.canPurchase) return
    try {
      setSubmitting(true)
      await submitPurchaseIntent(product.id)
      message.success('购买意向已提交')
    } catch (error) {
      console.error('提交购买意向失败:', error)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div style={{ padding: 64, textAlign: 'center' }}><Spin size="large" /></div>
  if (unavailable || !product || product.status === 'OFFLINE') return <main style={{ maxWidth: 900, margin: '40px auto', padding: 24 }}><Card><Empty description="商品当前不可查看"><Link to="/">返回商品列表</Link></Empty></Card></main>

  const images = [...(product.images ?? [])].sort((a, b) => a.position - b.position).map((image) => image.url)
  if (images.length === 0 && product.mainImageUrl) images.push(product.mainImageUrl)
  if (images.length === 0) images.push('/placeholder-product.svg')
  const description = product.descriptionHtml ?? ''

  return (
    <main style={{ maxWidth: 1000, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Link to="/">返回商品列表</Link>
        {product.status === 'FROZEN' && <Alert type="warning" showIcon message="商品交易处理中，当前仅可查看，不能提交购买意向。" />}
        <Card>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))', gap: 28 }}>
            <Image.PreviewGroup>
              <div style={{ display: 'grid', gap: 12 }}>
                <Image src={images[0]} alt={product.name} style={{ maxHeight: 420, objectFit: 'contain' }} />
                {images.length > 1 && <Space wrap>{images.slice(1).map((image, index) => <Image key={`${image}-${index}`} src={image} alt={`${product.name} ${index + 2}`} width={72} height={72} style={{ objectFit: 'cover' }} />)}</Space>}
              </div>
            </Image.PreviewGroup>
            <Space direction="vertical" size="middle">
              <Typography.Title level={2} style={{ margin: 0 }}>{product.name}</Typography.Title>
              <Typography.Title level={3} style={{ margin: 0, color: '#cf1322' }}>¥{Number(product.price).toFixed(2)}</Typography.Title>
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="类目">{product.categoryName || '-'}</Descriptions.Item>
                <Descriptions.Item label="库存">{product.stock ?? '-'}</Descriptions.Item>
              </Descriptions>
              {product.status === 'ONLINE' && product.canPurchase ? (
                <Button type="primary" onClick={submitIntent} loading={submitting}>提交购买意向</Button>
              ) : <Typography.Text type="secondary">当前不可提交购买意向</Typography.Text>}
              {!loggedIn && product.status === 'ONLINE' && product.canPurchase && <Typography.Text type="secondary">提交意向前需要登录。</Typography.Text>}
            </Space>
          </div>
          {hasReadableContent(description) && (
            <section style={{ marginTop: 32 }}>
              <Typography.Title level={4}>商品描述</Typography.Title>
              <div className="product-description" dangerouslySetInnerHTML={{ __html: description }} />
            </section>
          )}
        </Card>
      </Space>
    </main>
  )
}
