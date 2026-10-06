import { useState, type ChangeEvent } from 'react'
import { Button, Card, Form, Input, message, Space } from 'antd'
import { publishProduct } from '../../api/product'

interface PublishFormValues {
  name: string
  description?: string
  price: string
}

export default function PublishProductPage() {
  const [form] = Form.useForm<PublishFormValues>()
  const [image, setImage] = useState<File | null>(null)
  const [imageError, setImageError] = useState('')
  const [fileInputKey, setFileInputKey] = useState(0)
  const [publishing, setPublishing] = useState(false)

  const handleImageChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null
    setImage(file)

    if (!file) {
      setImageError('请选择 JPG 或 PNG 图片')
      return
    }

    const validExtension = /\.(jpe?g|png)$/i.test(file.name)
    const validMime = !file.type || ['image/jpeg', 'image/png'].includes(file.type)
    if (!validExtension || !validMime) {
      setImage(null)
      setImageError('图片格式仅支持 JPG、PNG')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setImage(null)
      setImageError('图片不能超过 5MB')
      return
    }

    setImageError('')
  }

  const handlePublish = async (values: PublishFormValues) => {
    if (!image) {
      setImageError('请选择 JPG 或 PNG 图片')
      return
    }

    const data = new FormData()
    data.append('name', values.name.trim())
    data.append('description', values.description?.trim() ?? '')
    data.append('price', values.price.trim())
    data.append('image', image)

    try {
      setPublishing(true)
      await publishProduct(data)
      message.success('商品发布成功')
      form.resetFields()
      setImage(null)
      setImageError('')
      setFileInputKey((current) => current + 1)
    } catch (error) {
      console.error('发布商品失败:', error)
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div style={{ maxWidth: 760, margin: '0 auto', padding: 24 }}>
      <Card title="发布商品">
        <Form form={form} layout="vertical" onFinish={handlePublish}>
          <Form.Item
            label="商品名称"
            name="name"
            rules={[
              { required: true, message: '请输入商品名称' },
              {
                validator: (_, value: string | undefined) =>
                  !value || value.trim().length > 0
                    ? Promise.resolve()
                    : Promise.reject(new Error('商品名称不能全是空白')),
              },
            ]}
          >
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item
            label="商品描述"
            name="description"
            rules={[
              { required: true, message: '请输入商品描述' },
              {
                validator: (_, value: string | undefined) =>
                  !value || value.trim().length > 0
                    ? Promise.resolve()
                    : Promise.reject(new Error('商品描述不能全是空白')),
              },
            ]}
          >
            <Input.TextArea rows={4} maxLength={2000} />
          </Form.Item>
          <Form.Item
            label="价格"
            name="price"
            rules={[
              { required: true, message: '请输入商品价格' },
              {
                validator: (_, value: string | undefined) =>
                  value && /^\d+(?:\.\d{1,2})?$/.test(value.trim()) && Number(value) > 0
                    ? Promise.resolve()
                    : Promise.reject(new Error('价格须大于 0，且最多两位小数')),
              },
            ]}
          >
            <Input inputMode="decimal" prefix="¥" />
          </Form.Item>
          <Form.Item label="商品图片" required validateStatus={imageError ? 'error' : undefined} help={imageError || '仅支持 JPG、PNG，最大 5MB'}>
            <Space direction="vertical">
              <input
                key={fileInputKey}
                type="file"
                accept=".jpg,.jpeg,.png,image/jpeg,image/png"
                onChange={handleImageChange}
              />
              {image && <span>{image.name}</span>}
            </Space>
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={publishing}>
            发布商品
          </Button>
        </Form>
      </Card>
    </div>
  )
}