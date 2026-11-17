import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Checkbox, Empty, Input, Modal, Space, Spin, Tag, Typography, message } from 'antd'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/request'
import { clearMyCart, getMyCart, removeCartItem, setCartItemQuantity } from '../../api/challengeB'
import type { Cart, CartItem } from '../../types/challengeB'

function moneyCents(value: string) {
  const [whole, fraction = ''] = value.split('.')
  return BigInt(`${whole}${fraction.padEnd(2, '0').slice(0, 2)}`)
}

function formatCents(value: bigint) {
  return `${value / 100n}.${String(value % 100n).padStart(2, '0')}`
}

function formatAmount(value: bigint) {
  const formatted = formatCents(value)
  return `¥${formatted}`
}

export default function BuyerCartPage() {
  const [cart, setCart] = useState<Cart>()
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [quantities, setQuantities] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const [savingId, setSavingId] = useState<string>()

  const loadCart = async (preserveSelection = false) => {
    setLoading(true)
    setLoadError(false)
    try {
      const latest = await getMyCart()
      setCart(latest)
      setQuantities(Object.fromEntries(latest.items.map((item) => [item.cartItemId, item.quantity])))
      if (preserveSelection) {
        setSelectedIds((current) => new Set([...current].filter((id) =>
          latest.items.some((item) => item.cartItemId === id && item.canCheckoutSelect))))
      } else {
        setSelectedIds(new Set(latest.items
          .filter((item) => item.canCheckoutSelect && item.defaultCheckoutSelected)
          .map((item) => item.cartItemId)))
      }
    } catch (error) {
      console.error('获取购物车失败:', error)
      setLoadError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadCart()
  }, [retryCount])

  const items = cart?.items ?? []
  const selectableIds = items.filter((item) => item.canCheckoutSelect).map((item) => item.cartItemId)
  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.has(id))
  const selectedTotal = useMemo(() => items.reduce((total, item) => {
    if (!selectedIds.has(item.cartItemId)) return total
    return total + moneyCents(item.unitPrice) * BigInt(item.quantity)
  }, 0n), [items, selectedIds])

  const changeQuantity = async (item: CartItem) => {
    const raw = quantities[item.cartItemId] ?? item.quantity
    if (!/^\d+$/.test(raw)) {
      setQuantities((current) => ({ ...current, [item.cartItemId]: item.quantity }))
      message.error('数量无效，请输入正整数')
      return
    }

    const quantity = BigInt(raw).toString()
    if (quantity === item.quantity) return

    try {
      setSavingId(item.cartItemId)
      const response = await setCartItemQuantity(item.cartItemId, quantity)
      if (response.message) message.success(response.message)
      if (response.data) {
        setCart((current) => current && ({
          ...current,
          items: current.items.map((cartItem) => cartItem.cartItemId === item.cartItemId ? response.data! : cartItem),
        }))
        setQuantities((current) => ({ ...current, [item.cartItemId]: response.data!.quantity }))
      } else {
        setCart((current) => current && ({ ...current, items: current.items.filter((cartItem) => cartItem.cartItemId !== item.cartItemId) }))
        setSelectedIds((current) => {
          const next = new Set(current)
          next.delete(item.cartItemId)
          return next
        })
      }
    } catch (error) {
      console.error('修改购物车数量失败:', error)
      if (error instanceof ApiError && error.code === 40912) await loadCart(true)
    } finally {
      setSavingId(undefined)
    }
  }

  const deleteItem = async (item: CartItem) => {
    try {
      setSavingId(item.cartItemId)
      const response = await removeCartItem(item.cartItemId)
      if (response.message) message.success(response.message)
      setCart((current) => current && ({ ...current, items: current.items.filter((cartItem) => cartItem.cartItemId !== item.cartItemId) }))
      setSelectedIds((current) => {
        const next = new Set(current)
        next.delete(item.cartItemId)
        return next
      })
    } catch (error) {
      console.error('删除购物车商品失败:', error)
    } finally {
      setSavingId(undefined)
    }
  }

  const clearCart = () => {
    Modal.confirm({
      title: '确定清空购物车？',
      content: '清空后购物车中的商品行将被移除。',
      okText: '清空购物车',
      cancelText: '取消',
      onOk: async () => {
        try {
          const response = await clearMyCart()
          if (response.message) message.success(response.message)
          setCart({ items: [] })
          setSelectedIds(new Set())
          setQuantities({})
        } catch (error) {
          console.error('清空购物车失败:', error)
        }
      },
    })
  }

  const toggleAll = (checked: boolean) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      for (const id of selectableIds) {
        if (checked) next.add(id)
        else next.delete(id)
      }
      return next
    })
  }

  const toggleItem = (item: CartItem, checked: boolean) => {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (checked) next.add(item.cartItemId)
      else next.delete(item.cartItemId)
      return next
    })
  }

  return (
    <main style={{ maxWidth: 1000, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Typography.Title level={2} style={{ margin: 0 }}>购物车</Typography.Title>
          <Link to="/me/account">返回买家账户</Link>
        </div>
        <Card>
          {loading ? <div style={{ padding: 48, textAlign: 'center' }}><Spin /></div> :
            loadError ? <Alert type="error" showIcon message="购物车加载失败。" action={<Button onClick={() => setRetryCount((count) => count + 1)}>重试</Button>} /> :
            !items.length ? <Empty description="购物车是空的" /> : (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Space wrap>
                  <Checkbox checked={allSelected} indeterminate={selectedIds.size > 0 && !allSelected} onChange={(event) => toggleAll(event.target.checked)}>
                    全选可下单商品
                  </Checkbox>
                  <Button danger onClick={clearCart}>清空购物车</Button>
                </Space>
                {items.map((item) => (
                  <Card key={item.cartItemId} size="small">
                    <Space align="start" style={{ width: '100%', justifyContent: 'space-between' }} wrap>
                      <Space align="start">
                        <Checkbox
                          checked={selectedIds.has(item.cartItemId)}
                          disabled={!item.canCheckoutSelect}
                          onChange={(event) => toggleItem(item, event.target.checked)}
                        />
                        <Space direction="vertical" size={4}>
                          {item.online ? <Link to={`/products/${item.productId}`}>{item.productName}</Link> : <Typography.Text>{item.productName}</Typography.Text>}
                          <Typography.Text>单价：¥{item.unitPrice}</Typography.Text>
                          {!item.online && <Tag>{item.invalidLabel || '已下架'}</Tag>}
                          {item.online && BigInt(item.stock) < BigInt(item.quantity) && (
                            <Typography.Text type="secondary">当前库存 {item.stock}，下单时将重新校验。</Typography.Text>
                          )}
                        </Space>
                      </Space>
                      <Space wrap>
                        <Input
                          aria-label={`${item.productName}数量`}
                          value={quantities[item.cartItemId] ?? item.quantity}
                          onChange={(event) => setQuantities((current) => ({ ...current, [item.cartItemId]: event.target.value }))}
                          style={{ width: 120 }}
                        />
                        <Button loading={savingId === item.cartItemId} onClick={() => void changeQuantity(item)}>更新数量</Button>
                        <Button danger loading={savingId === item.cartItemId} onClick={() => void deleteItem(item)}>删除</Button>
                      </Space>
                    </Space>
                  </Card>
                ))}
                <Typography.Text>
                  已选 {selectedIds.size} 件商品，金额合计：<Typography.Text strong>{formatAmount(selectedTotal)}</Typography.Text>
                </Typography.Text>
              </Space>
            )}
        </Card>
      </Space>
    </main>
  )
}
