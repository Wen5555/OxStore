import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, Input, Pagination, Select, Space, Spin, Typography } from 'antd'
import { Link, useNavigate } from 'react-router-dom'
import { getCategoryTree, getProducts } from '../../api/catalog'
import type { CategoryTreeItem, Page } from '../../types/common'
import type { ProductSummary } from '../../types/product'

const PAGE_SIZE = 10

function productImage(product: ProductSummary) {
  return product.mainImageUrl || '/placeholder-product.svg'
}

export default function ProductListPage() {
  const [categories, setCategories] = useState<CategoryTreeItem[]>([])
  const [result, setResult] = useState<Page<ProductSummary>>()
  const [category2Id, setCategory2Id] = useState<number>()
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [categoryError, setCategoryError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const navigate = useNavigate()
  const loggedIn = Boolean(localStorage.getItem('customer_token'))

  useEffect(() => {
    getCategoryTree()
      .then(setCategories)
      .catch((error) => {
        console.error('获取类目失败:', error)
        setCategoryError(true)
      })
  }, [])

  useEffect(() => {
    let active = true
    setLoading(true)
    setLoadError(false)
    getProducts({ category2Id, q: keyword.trim() || undefined, page, size: PAGE_SIZE })
      .then((data) => { if (active) setResult(data) })
      .catch((error) => {
        console.error('获取商品失败:', error)
        if (active) setLoadError(true)
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [category2Id, keyword, page, retryCount])

  const categoryOptions = categories.flatMap((parent) =>
    (parent.children ?? []).map((child) => ({ value: child.id, label: `${parent.name} / ${child.name}` })),
  )

  return (
    <main style={{ maxWidth: 1200, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <Typography.Title level={2} style={{ margin: 0 }}>OxStore 商品</Typography.Title>
          <Space>
            {loggedIn ? (
              <>
                <Button onClick={() => navigate('/me/account')}>我的账户</Button>
                <Button onClick={() => navigate('/me/order-history')}>我的购买历史</Button>
                <Button onClick={() => {
                  localStorage.removeItem('customer_token')
                  localStorage.removeItem('customer_username')
                  localStorage.removeItem('customer_user_id')
                  window.location.reload()
                }}>退出登录</Button>
              </>
            ) : <><Button onClick={() => navigate('/login')}>登录</Button><Button type="primary" onClick={() => navigate('/register')}>注册</Button></>}
          </Space>
        </header>

        {categoryError && <Alert type="error" showIcon message="商品类目加载失败，类目筛选暂不可用。" />}
        <Space wrap>
          <Input.Search
            aria-label="商品关键词"
            placeholder="搜索商品名称或描述"
            allowClear
            value={keyword}
            onChange={(event) => { setKeyword(event.target.value); setPage(1) }}
            style={{ width: 320 }}
          />
          <Select
            aria-label="二级类目"
            allowClear
            placeholder="全部二级类目"
            options={categoryOptions}
            value={category2Id}
            onChange={(value) => { setCategory2Id(value); setPage(1) }}
            style={{ width: 240 }}
          />
        </Space>

        {loading ? <div style={{ padding: 64, textAlign: 'center' }}><Spin size="large" /></div> :
          loadError ? <Alert type="error" showIcon message="商品列表加载失败。" action={<Button onClick={() => setRetryCount((count) => count + 1)}>重试</Button>} /> :
          !result?.items.length ? <Card><Empty description="暂无在售商品" /></Card> : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 16 }}>
                {result.items.map((product) => (
                  <Card
                    key={product.id}
                    hoverable
                    cover={<img src={productImage(product)} alt={product.name} style={{ height: 200, objectFit: 'contain', background: '#fafafa' }} />}
                    onClick={() => navigate(`/products/${product.id}`)}
                  >
                    <Card.Meta title={<Link to={`/products/${product.id}`}>{product.name}</Link>} description={product.categoryName} />
                    <Typography.Title level={4} style={{ color: '#cf1322', marginBottom: 0 }}>
                      ¥{Number(product.price).toFixed(2)}
                    </Typography.Title>
                  </Card>
                ))}
              </div>
              <Pagination current={page} pageSize={PAGE_SIZE} total={result.total} onChange={setPage} />
            </>
          )}
      </Space>
    </main>
  )
}
