import { useEffect, useState } from 'react'
import { Alert, Button, Card, Empty, Pagination, Space, Spin, Table, Tag, Tooltip, Typography, message } from 'antd'
import { Link } from 'react-router-dom'
import { getMyFavorites, removeFavorite } from '../../api/challengeB'
import type { FavoriteItem, FavoritePage } from '../../types/challengeB'

const PAGE_SIZE = 10

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN')
}

export default function BuyerFavoritesPage() {
  const [result, setResult] = useState<FavoritePage>()
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const [removingId, setRemovingId] = useState<string>()

  useEffect(() => {
    let active = true
    setLoading(true)
    setLoadError(false)
    getMyFavorites(page)
      .then((data) => { if (active) setResult(data) })
      .catch((error) => {
        console.error('获取收藏列表失败:', error)
        if (active) setLoadError(true)
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [page, retryCount])

  const cancelFavorite = async (item: FavoriteItem) => {
    try {
      setRemovingId(item.favoriteId)
      const response = await removeFavorite(item.productId)
      if (response.message) message.success(response.message)
      setResult((current) => current && ({
        ...current,
        items: current.items.filter((favorite) => favorite.favoriteId !== item.favoriteId),
        total: Math.max(0, current.total - 1),
      }))
      if (result?.items.length === 1 && page > 1) setPage((current) => current - 1)
    } catch (error) {
      console.error('取消收藏失败:', error)
    } finally {
      setRemovingId(undefined)
    }
  }

  return (
    <main style={{ maxWidth: 1000, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Typography.Title level={2} style={{ margin: 0 }}>我的收藏</Typography.Title>
          <Link to="/me/account">返回买家账户</Link>
        </div>
        <Card>
          {loading ? <div style={{ padding: 48, textAlign: 'center' }}><Spin /></div> :
            loadError ? <Alert type="error" showIcon message="收藏列表加载失败。" action={<Button onClick={() => setRetryCount((count) => count + 1)}>重试</Button>} /> :
            !result?.items.length ? <Empty description="暂无收藏" /> : (
              <>
                <Table<FavoriteItem>
                  rowKey="favoriteId"
                  dataSource={result.items}
                  pagination={false}
                  columns={[
                    {
                      title: '商品',
                      dataIndex: 'productName',
                      key: 'productName',
                      render: (name: string, item) => {
                        if (item.canOpenDetail) {
                          return <Link to={`/products/${item.productId}`}>{name}</Link>
                        }
                        const invalidLabel = item.invalidLabel || '已下架'
                        const showInvalidNotice = () => message.warning(invalidLabel)
                        return (
                          <Tooltip title={invalidLabel}>
                            <span
                              role="button"
                              tabIndex={0}
                              aria-label={`${name}（${invalidLabel}）`}
                              style={{ color: 'rgba(0, 0, 0, 0.45)', cursor: 'pointer' }}
                              onClick={showInvalidNotice}
                              onKeyDown={(event) => {
                                if (event.key === 'Enter' || event.key === ' ') {
                                  event.preventDefault()
                                  showInvalidNotice()
                                }
                              }}
                            >
                              {name}
                            </span>
                          </Tooltip>
                        )
                      },
                    },
                    { title: '价格', dataIndex: 'unitPrice', key: 'unitPrice', render: (price: string) => `¥${price}` },
                    {
                      title: '状态',
                      key: 'status',
                      render: (_, item) => item.valid
                        ? <Tag color="green">在售</Tag>
                        : <Tag>{item.invalidLabel || '已下架'}</Tag>,
                    },
                    { title: '收藏时间', dataIndex: 'createdAt', key: 'createdAt', render: formatDate },
                    {
                      title: '操作',
                      key: 'actions',
                      render: (_, item) => (
                        <Button danger type="link" loading={removingId === item.favoriteId} onClick={() => void cancelFavorite(item)}>
                          取消收藏
                        </Button>
                      ),
                    },
                  ]}
                />
                <Pagination style={{ marginTop: 20 }} current={page} pageSize={PAGE_SIZE} total={result.total} onChange={setPage} />
              </>
            )}
        </Card>
      </Space>
    </main>
  )
}
