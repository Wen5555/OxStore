import { useEffect, useState } from 'react'
import { Alert, Button, Card, Cascader, Form, InputNumber, Popconfirm, Space, Spin, Typography, message } from 'antd'
import { useNavigate, useParams } from 'react-router-dom'
import { getCategoryTree } from '../../api/catalog'
import { getAdminProduct, setProductOffline, setProductOnline, updateProduct } from '../../api/admin'
import type { CategoryTreeItem } from '../../types/common'
import type { Product } from '../../types/product'

interface EditValues {
  stock: number
  category: number[]
}

export default function ProductEditPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [form] = Form.useForm<EditValues>()
  const [product, setProduct] = useState<Product>()
  const [categories, setCategories] = useState<CategoryTreeItem[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    if (!id || !/^\d+$/.test(id)) {
      setLoading(false)
      return
    }
    Promise.all([getAdminProduct(Number(id)), getCategoryTree()])
      .then(([item, tree]) => {
        setProduct(item)
        setCategories(tree)
        const path = tree.flatMap((parent) =>
          (parent.children ?? []).filter((child) => child.id === item.category2Id).map((child) => [parent.id, child.id]),
        )[0]
        form.setFieldsValue({ stock: item.stock ?? 0, category: path })
      })
      .catch((error) => {
        console.error('获取商品信息失败:', error)
        setLoadError(true)
      })
      .finally(() => setLoading(false))
  }, [id, form])

  const save = async (values: EditValues) => {
    if (!product || values.category?.length !== 2) return
    try {
      setSaving(true)
      await updateProduct(product.id, { stock: values.stock, category2Id: values.category[1] })
      message.success('商品信息已更新')
      navigate('/admin/products')
    } catch (error) {
      console.error('更新商品失败:', error)
    } finally {
      setSaving(false)
    }
  }

  const changeListing = async (online: boolean) => {
    if (!product) return
    try {
      setSaving(true)
      if (online) await setProductOnline(product.id)
      else await setProductOffline(product.id)
      message.success(online ? '商品已上架' : '商品已下架')
      navigate('/admin/products')
    } catch (error) {
      console.error('更新商品状态失败:', error)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div style={{ padding: 64, textAlign: 'center' }}><Spin size="large" /></div>
  if (!product) return <main style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}><Card>{loadError ? <Alert type="error" showIcon message="商品信息加载失败，请刷新后重试。" /> : '商品不存在。'}</Card></main>

  const categoryOptions = categories.map((parent) => ({
    value: parent.id,
    label: parent.name,
    children: (parent.children ?? []).map((child) => ({ value: child.id, label: child.name })),
  }))

  return (
    <main style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}>
      <Card title={`维护商品：${product.name}`}>
        <Typography.Paragraph>只能修改库存和二级类目。名称、价格、描述和图片不可原地修改；需要变更时请下架后重新发布。</Typography.Paragraph>
        <Form form={form} layout="vertical" onFinish={save}>
          <Form.Item label="库存数量" name="stock" rules={[{ required: true, message: '请输入库存' }]}>
            <InputNumber min={0} precision={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="二级类目" name="category" rules={[{ required: true, message: '请选择二级类目' }]}>
            <Cascader options={categoryOptions} placeholder="请选择一级及二级类目" />
          </Form.Item>
          <Space wrap>
            <Button type="primary" htmlType="submit" loading={saving}>保存库存和类目</Button>
            {product.status === 'ONLINE' && (
              <Popconfirm title="下架该商品？未完成意向将按规则作废。" onConfirm={() => changeListing(false)} okText="下架" cancelText="取消">
                <Button danger loading={saving}>手动下架</Button>
              </Popconfirm>
            )}
            {product.status === 'OFFLINE' && (
              <Popconfirm
                title="上架该商品？"
                description={(product.stock ?? 0) <= 0 ? '库存必须大于 0 才能上架。' : undefined}
                onConfirm={() => changeListing(true)}
                okText="上架"
                cancelText="取消"
              >
                <Button disabled={(product.stock ?? 0) <= 0} loading={saving}>手动上架</Button>
              </Popconfirm>
            )}
          </Space>
        </Form>
      </Card>
    </main>
  )
}
