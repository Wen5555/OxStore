import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Checkbox, Empty, Input, Modal, Radio, Space, Spin, Tag, Typography, message } from 'antd'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/request'
import {
  clearMyCart,
  createIdempotencyKey,
  createCheckoutConfirmation,
  getMyCart,
  moveCartItemsToFavorites,
  removeCartItem,
  setCartItemQuantity,
  submitMyOrder,
} from '../../api/challengeB'
import type { Cart, CartItem, CheckoutConfirmation, Order } from '../../types/challengeB'

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
  const navigate = useNavigate()
  const [cart, setCart] = useState<Cart>()
  const [selectionMode, setSelectionMode] = useState<'checkout' | 'favorite'>('checkout')
  const [checkoutSelectedIds, setCheckoutSelectedIds] = useState<Set<string>>(new Set())
  const [favoriteSelectedIds, setFavoriteSelectedIds] = useState<Set<string>>(new Set())
  const [quantities, setQuantities] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [retryCount, setRetryCount] = useState(0)
  const [savingId, setSavingId] = useState<string>()
  const [checkoutConfirmation, setCheckoutConfirmation] = useState<CheckoutConfirmation>()
  const [checkoutModalOpen, setCheckoutModalOpen] = useState(false)
  const [checkoutSubmitting, setCheckoutSubmitting] = useState(false)
  const [checkoutSubmitKey, setCheckoutSubmitKey] = useState('')
  const [successOrder, setSuccessOrder] = useState<Order>()
  const [favoriteMoveOpen, setFavoriteMoveOpen] = useState(false)
  const [favoriteMoveSubmitting, setFavoriteMoveSubmitting] = useState(false)
  const [favoriteMoveKey, setFavoriteMoveKey] = useState('')
  const [favoriteMoveIds, setFavoriteMoveIds] = useState<string[]>([])

  const loadCart = async (preserveSelection = false) => {
    setLoading(true)
    setLoadError(false)
    try {
      const latest = await getMyCart()
      setCart(latest)
      setQuantities((current) => Object.fromEntries(latest.items.map((item) => [
        item.cartItemId,
        preserveSelection ? current[item.cartItemId] ?? item.quantity : item.quantity,
      ])))
      if (preserveSelection) {
        setCheckoutSelectedIds((current) => new Set([...current].filter((id) =>
          latest.items.some((item) => item.cartItemId === id && item.canCheckoutSelect))))
        setFavoriteSelectedIds((current) => new Set([...current].filter((id) =>
          latest.items.some((item) => item.cartItemId === id && item.canFavoriteSelect))))
      } else {
        setCheckoutSelectedIds(new Set(latest.items
          .filter((item) => item.canCheckoutSelect && item.defaultCheckoutSelected)
          .map((item) => item.cartItemId)))
        setFavoriteSelectedIds(new Set(latest.items
          .filter((item) => item.canFavoriteSelect)
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
  const selectedIds = selectionMode === 'checkout' ? checkoutSelectedIds : favoriteSelectedIds
  const selectableIds = items
    .filter((item) => selectionMode === 'checkout' ? item.canCheckoutSelect : item.canFavoriteSelect)
    .map((item) => item.cartItemId)
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
        setCheckoutSelectedIds((current) => {
          const next = new Set(current)
          next.delete(item.cartItemId)
          return next
        })
        setFavoriteSelectedIds((current) => {
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
      setCheckoutSelectedIds((current) => {
        const next = new Set(current)
        next.delete(item.cartItemId)
        return next
      })
      setFavoriteSelectedIds((current) => {
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
          setCheckoutSelectedIds(new Set())
          setFavoriteSelectedIds(new Set())
          setQuantities({})
        } catch (error) {
          console.error('清空购物车失败:', error)
        }
      },
    })
  }

  const toggleAll = (checked: boolean) => {
    const updateSelection = (current: Set<string>) => {
      const next = new Set(current)
      for (const id of selectableIds) {
        if (checked) next.add(id)
        else next.delete(id)
      }
      return next
    }
    if (selectionMode === 'checkout') setCheckoutSelectedIds(updateSelection)
    else setFavoriteSelectedIds(updateSelection)
  }

  const toggleItem = (item: CartItem, checked: boolean) => {
    const updateSelection = (current: Set<string>) => {
      const next = new Set(current)
      if (checked) next.add(item.cartItemId)
      else next.delete(item.cartItemId)
      return next
    }
    if (selectionMode === 'checkout') setCheckoutSelectedIds(updateSelection)
    else setFavoriteSelectedIds(updateSelection)
  }

  const openCheckoutConfirmation = async () => {
    setSelectionMode('checkout')
    if (checkoutSelectedIds.size === 0) {
      message.error('请选择商品')
      return
    }
    try {
      const confirmation = await createCheckoutConfirmation([...checkoutSelectedIds])
      setCheckoutConfirmation(confirmation)
      setCheckoutSubmitKey(createIdempotencyKey())
      setCheckoutModalOpen(true)
    } catch (error) {
      console.error('生成下单确认失败:', error)
      if (error instanceof ApiError && error.itemErrors.length > 0) {
        error.itemErrors.forEach((itemError) => message.error(itemError.message))
      }
    }
  }

  const submitOrder = async () => {
    if (!checkoutConfirmation) return
    setCheckoutSubmitting(true)
    try {
      const result = await submitMyOrder(checkoutConfirmation.confirmationToken, checkoutSubmitKey)
      setCheckoutModalOpen(false)
      setCheckoutConfirmation(undefined)
      setSuccessOrder(result.data)
      setCheckoutSelectedIds(new Set())
      message.success(result.message || '下单成功')
      await loadCart(true)
    } catch (error) {
      console.error('提交订单失败:', error)
      if (error instanceof ApiError && error.code === 40913) {
        try {
          const confirmation = await createCheckoutConfirmation([...checkoutSelectedIds])
          setCheckoutConfirmation(confirmation)
          setCheckoutSubmitKey(createIdempotencyKey())
        } catch (confirmationError) {
          console.error('重新确认下单失败:', confirmationError)
          setCheckoutModalOpen(false)
          setCheckoutConfirmation(undefined)
          if (confirmationError instanceof ApiError && confirmationError.itemErrors.length > 0) {
            confirmationError.itemErrors.forEach((itemError) => message.error(itemError.message))
          }
        }
      } else if (error instanceof ApiError && error.code === 40909) {
        setCheckoutModalOpen(false)
        setCheckoutConfirmation(undefined)
        navigate('/me/order-history')
      } else if (error instanceof ApiError && error.code === 40910) {
        error.itemErrors.forEach((itemError) => message.error(itemError.message))
        setCheckoutModalOpen(false)
        setCheckoutConfirmation(undefined)
      } else if (error instanceof ApiError && error.itemErrors.length > 0) {
        error.itemErrors.forEach((itemError) => message.error(itemError.message))
      }
    } finally {
      setCheckoutSubmitting(false)
    }
  }

  const openFavoriteMoveConfirmation = () => {
    setSelectionMode('favorite')
    const ids = items
      .filter((item) => favoriteSelectedIds.has(item.cartItemId) && item.canFavoriteSelect)
      .map((item) => item.cartItemId)
    if (ids.length === 0) {
      message.error('请选择商品')
      return
    }
    setFavoriteMoveIds(ids)
    setFavoriteMoveKey(createIdempotencyKey())
    setFavoriteMoveOpen(true)
  }

  const submitFavoriteMove = async () => {
    setFavoriteMoveSubmitting(true)
    try {
      const result = await moveCartItemsToFavorites(favoriteMoveIds, favoriteMoveKey)
      message.success(result.message || `已收藏 ${result.data.movedLineCount} 件商品`)
      setFavoriteMoveOpen(false)
      await loadCart(true)
    } catch (error) {
      console.error('转收藏失败:', error)
      if (error instanceof ApiError && error.itemErrors.length > 0) {
        error.itemErrors.forEach((itemError) => message.error(itemError.message))
      }
    } finally {
      setFavoriteMoveSubmitting(false)
    }
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
                  <Radio.Group
                    value={selectionMode}
                    onChange={(event) => setSelectionMode(event.target.value)}
                    optionType="button"
                    buttonStyle="solid"
                    options={[
                      { label: '下单选择', value: 'checkout' },
                      { label: '转收藏选择', value: 'favorite' },
                    ]}
                  />
                  <Checkbox checked={allSelected} indeterminate={selectedIds.size > 0 && !allSelected} onChange={(event) => toggleAll(event.target.checked)}>
                    {selectionMode === 'checkout' ? '全选可下单商品' : '全选可收藏商品'}
                  </Checkbox>
                  <Button danger onClick={clearCart}>清空购物车</Button>
                  <Button onClick={openFavoriteMoveConfirmation}>转为收藏</Button>
                  <Button type="primary" aria-label="下单" onClick={() => void openCheckoutConfirmation()}>下单</Button>
                </Space>
                {items.map((item) => (
                  <Card key={item.cartItemId} size="small">
                    <Space align="start" style={{ width: '100%', justifyContent: 'space-between' }} wrap>
                      <Space align="start">
                        <Checkbox
                          aria-label={`选择${item.productName}`}
                          checked={selectedIds.has(item.cartItemId)}
                          disabled={selectionMode === 'checkout' ? !item.canCheckoutSelect : !item.canFavoriteSelect}
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
                  已选 {selectedIds.size} 件商品
                  {selectionMode === 'checkout' && <>，金额合计：<Typography.Text strong>{formatAmount(selectedTotal)}</Typography.Text></>}
                </Typography.Text>
              </Space>
            )}
        </Card>
      </Space>
      <Modal
        title="确认下单"
        open={checkoutModalOpen}
        onCancel={() => setCheckoutModalOpen(false)}
        onOk={() => void submitOrder()}
        okText="确认下单"
        cancelText="返回购物车"
        confirmLoading={checkoutSubmitting}
        width={700}
      >
        {checkoutConfirmation && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {checkoutConfirmation.items.map((item) => (
              <Space key={item.cartItemId} style={{ width: '100%', justifyContent: 'space-between' }}>
                <Typography.Text>{item.productName}</Typography.Text>
                <Typography.Text>¥{item.unitPrice} × {item.quantity}</Typography.Text>
                <Typography.Text strong>¥{item.lineAmount}</Typography.Text>
              </Space>
            ))}
            <Typography.Text strong>总金额：¥{checkoutConfirmation.totalAmount}</Typography.Text>
          </Space>
        )}
      </Modal>

      <Modal
        title="确认转为收藏"
        open={favoriteMoveOpen}
        onCancel={() => setFavoriteMoveOpen(false)}
        onOk={() => void submitFavoriteMove()}
        okText="确认转收藏"
        cancelText="取消"
        confirmLoading={favoriteMoveSubmitting}
      >
        <Typography.Text>
          所选 {favoriteMoveIds.length} 件商品将从购物车移除并加入收藏
        </Typography.Text>
      </Modal>

      <Modal
        title="下单成功"
        open={Boolean(successOrder)}
        footer={
          <Space>
            {successOrder && <Link to="/me/order-history">查看订单详情</Link>}
            <Button type="primary" onClick={() => setSuccessOrder(undefined)}>关闭</Button>
          </Space>
        }
        onCancel={() => setSuccessOrder(undefined)}
      >
        {successOrder && (
          <Space direction="vertical">
            <Typography.Text strong>下单成功</Typography.Text>
            <Typography.Text>订单号：{successOrder.orderNo}</Typography.Text>
          </Space>
        )}
      </Modal>
    </main>
  )
}
