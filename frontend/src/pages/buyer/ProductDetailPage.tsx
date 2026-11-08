import { useEffect, useState } from 'react'
import { Alert, Button, Card, Descriptions, Empty, Image, InputNumber, List, Space, Spin, Tag, Typography, message } from 'antd'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getProduct, submitPurchaseIntent } from '../../api/catalog'
import { getAuctionSnapshot, placeBid } from '../../api/auction'
import type { AuctionSnapshot } from '../../types/auction'
import type { Product } from '../../types/product'
import { useAuctionEvents } from '../../hooks/useAuctionEvents'

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
  const [auction, setAuction] = useState<AuctionSnapshot>()
  const [bidAmount, setBidAmount] = useState('')
  const [bidSubmitting, setBidSubmitting] = useState(false)
  const [bidError, setBidError] = useState('')
  const [bidStatus, setBidStatus] = useState('')
  const loggedIn = Boolean(localStorage.getItem('customer_token'))
  useAuctionEvents(product?.sellingMode === 'AUCTION' ? product.id : undefined, (event) => {
    if ('productName' in event) setAuction(event)
    else if ('auctionStatus' in event && !('bidSeq' in event)) {
      setAuction((current) => current && {
        ...current,
        auctionStatus: event.auctionStatus,
        currentPrice: event.finalPrice ?? current.currentPrice,
        settledAt: event.settledAt ?? current.settledAt,
      })
    } else if ('currentPrice' in event) setAuction((current) => current && {
        ...current,
        currentPrice: event.currentPrice,
        nextMinBid: event.nextMinBid,
        bidCount: event.bidCount,
        leaderAlias: event.leaderAlias ?? current?.leaderAlias ?? null,
      })
  })

  useEffect(() => {
    if (!id || !/^\d+$/.test(id)) {
      setUnavailable(true)
      setLoading(false)
      return
    }
    getProduct(Number(id))
      .then(async (loadedProduct) => {
        setProduct(loadedProduct)
        if (loadedProduct.sellingMode === 'AUCTION') {
          setAuction(await getAuctionSnapshot(Number(id)))
        }
      })
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

  const submitBid = async () => {
    if (!loggedIn) {
      navigate('/login', { state: { from: `/products/${id}` } })
      return
    }
    if (!auction) return
    const amount = Number(bidAmount)
    if (!Number.isFinite(amount) || amount < auction.nextMinBid) {
      setBidError(`请输入不低于 ¥${Number(auction.nextMinBid).toFixed(2)} 的出价`)
      return
    }
    try {
      setBidSubmitting(true)
      setBidError('')
      setBidStatus('正在提交出价...')
      const result = await placeBid(auction.productId, amount)
      const latest = await getAuctionSnapshot(auction.productId)
      if (latest.currentPrice !== result.currentPrice || latest.bidCount !== result.bidCount) {
        throw new Error('出价结果未同步，请刷新页面后重试')
      }
      setAuction((current) => current && {
        ...latest,
      })
      setBidAmount('')
      setBidStatus('')
      message.success('出价成功')
    } catch (error) {
      console.error('提交出价失败:', error)
      setBidStatus('')
      message.error(error instanceof Error ? error.message : '出价失败，请稍后重试')
    } finally {
      setBidSubmitting(false)
    }
  }

  if (loading) return <div style={{ padding: 64, textAlign: 'center' }}><Spin size="large" /></div>
  if (unavailable || !product || (product.status === 'OFFLINE' && product.sellingMode !== 'AUCTION')) return <main style={{ maxWidth: 900, margin: '40px auto', padding: 24 }}><Card><Empty description="商品当前不可查看"><Link to="/">返回商品列表</Link></Empty></Card></main>

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
              <Typography.Title level={3} style={{ margin: 0, color: '#cf1322' }}>
                ¥{Number(auction?.currentPrice ?? product.price).toFixed(2)}
              </Typography.Title>
              {product.sellingMode === 'AUCTION' && auction && (
                <Alert
                  type={auction.auctionStatus === 'LIVE' ? 'info' : auction.auctionStatus === 'ENDED_SOLD' ? 'success' : 'warning'}
                  showIcon
                  message="拍卖"
                  description={auction.auctionStatus === 'ENDED_SOLD'
                    ? `已结拍，成交价 ¥${Number(auction.currentPrice).toFixed(2)}。${auction.myStatus === 'WON' ? '恭喜你中标，卖家将进入履约流程。' : auction.myStatus === 'LOST' ? '本次未中标。' : ''}`
                    : auction.auctionStatus === 'ENDED_UNSOLD'
                      ? '本次拍卖流拍，无人中标。'
                      : `起拍价：¥${Number(auction.startPrice).toFixed(2)}；最低加价幅度：¥${Number(auction.minIncrement).toFixed(2)}；本次最低出价：¥${Number(auction.nextMinBid).toFixed(2)}；截止 ${new Date(auction.endsAt).toLocaleString()}`}
                />
              )}
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="类目">{product.categoryName || '-'}</Descriptions.Item>
                <Descriptions.Item label="库存">{product.stock ?? '-'}</Descriptions.Item>
              </Descriptions>
              {product.sellingMode === 'AUCTION' && auction ? (
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Space wrap>
                    <Typography.Text>出价次数：{auction.bidCount}</Typography.Text>
                    <Typography.Text>当前领先者：{auction.leaderAlias || '暂无'}</Typography.Text>
                  </Space>
                  {auction.myStatus && <Tag color={auction.myStatus === 'LEADING' || auction.myStatus === 'WON' ? 'green' : auction.myStatus === 'OUTBID' ? 'orange' : 'default'}>
                    {{ NONE: '尚未出价', LEADING: '当前领先', OUTBID: '已被超越', WON: '恭喜中标', LOST: '未中标' }[auction.myStatus] ?? auction.myStatus}
                  </Tag>}
                  <Space.Compact style={{ width: '100%' }}>
                    <InputNumber
                      min={auction.nextMinBid}
                      value={bidAmount ? Number(bidAmount) : undefined}
                      onChange={(value) => {
                        setBidAmount(value == null ? '' : String(value))
                        setBidError('')
                      }}
                      style={{ width: '100%' }}
                    />
                    <Button
                      type="primary"
                      loading={bidSubmitting}
                      disabled={!auction.canBid}
                      onClick={() => void submitBid()}
                    >
                      出价
                    </Button>
                  </Space.Compact>
                  {!loggedIn && <Typography.Text type="secondary">请先登录后出价。</Typography.Text>}
                  {auction.auctionStatus !== 'LIVE' && <Typography.Text type="secondary">拍卖已结束，不能继续出价。</Typography.Text>}
                  {!auction.canBid && auction.auctionStatus === 'LIVE' && <Typography.Text type="secondary">请登录后参与出价。</Typography.Text>}
                  {bidError && <Typography.Text type="danger">{bidError}</Typography.Text>}
                  {bidStatus && <Typography.Text type="secondary">{bidStatus}</Typography.Text>}
                  {auction.recentBids.length > 0 && <List size="small" header="最近出价" dataSource={auction.recentBids} renderItem={(bid) => <List.Item>#{bid.bidSeq} {bid.bidderAlias}：¥{Number(bid.amount).toFixed(2)}</List.Item>} />}
                </Space>
              ) : product.status === 'ONLINE' && product.canPurchase ? (
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
