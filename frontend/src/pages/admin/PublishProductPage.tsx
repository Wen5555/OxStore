import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Card, Cascader, Form, Input, InputNumber, Modal, Space, Upload, message } from 'antd'
import type { UploadFile, UploadProps } from 'antd'
import { createProduct } from '../../api/admin'
import { getCategoryTree } from '../../api/catalog'
import { ApiError } from '../../api/request'
import type { CategoryTreeItem } from '../../types/common'

interface PublishValues {
  name: string
  price: number
  stock: number
  category: number[]
}

const imageValidationError = (file: File) => {
  const validType = /\.(jpe?g|png)$/i.test(file.name) && (!file.type || ['image/jpeg', 'image/png'].includes(file.type))
  if (!validType) return '仅支持 JPG、PNG 图片'
  if (file.size > 5 * 1024 * 1024) return '图片不能超过 5MB'
  return null
}

function RichTextEditor({ onChange }: { onChange: (html: string) => void }) {
  const editor = useRef<HTMLDivElement>(null)
  const [imageModal, setImageModal] = useState(false)
  const [imageUrl, setImageUrl] = useState('')

  const command = (name: string, argument?: string) => {
    editor.current?.focus()
    document.execCommand(name, false, argument)
    if (editor.current) onChange(editor.current.innerHTML)
  }

  const insertImage = () => {
    if (!imageUrl.trim()) return
    command('insertImage', imageUrl.trim())
    setImageUrl('')
    setImageModal(false)
  }

  return (
    <div>
      <Space wrap style={{ marginBottom: 8 }}>
        <Button htmlType="button" onClick={() => command('bold')}><strong>加粗</strong></Button>
        <Button htmlType="button" onClick={() => command('italic')}><em>斜体</em></Button>
        <Button htmlType="button" onClick={() => command('insertUnorderedList')}>无序列表</Button>
        <Button htmlType="button" onClick={() => command('insertOrderedList')}>有序列表</Button>
        <Button htmlType="button" onClick={() => setImageModal(true)}>插入图片</Button>
      </Space>
      <div
        ref={editor}
        contentEditable
        suppressContentEditableWarning
        onInput={(event) => onChange(event.currentTarget.innerHTML)}
        style={{ minHeight: 180, padding: 12, border: '1px solid #d9d9d9', borderRadius: 6 }}
      />
      <Modal title="插入图片" open={imageModal} onOk={insertImage} onCancel={() => setImageModal(false)} okText="插入" cancelText="取消">
        <Input value={imageUrl} onChange={(event) => setImageUrl(event.target.value)} placeholder="图片地址" />
      </Modal>
    </div>
  )
}

export default function PublishProductPage() {
  const [form] = Form.useForm<PublishValues>()
  const [categories, setCategories] = useState<CategoryTreeItem[]>([])
  const [descriptionHtml, setDescriptionHtml] = useState('')
  const [files, setFiles] = useState<UploadFile[]>([])
  const [saving, setSaving] = useState(false)
  const [imageError, setImageError] = useState('')
  const [categoryError, setCategoryError] = useState(false)
  const [editorKey, setEditorKey] = useState(0)

  useEffect(() => {
    getCategoryTree()
      .then(setCategories)
      .catch((error) => {
        console.error('获取类目失败:', error)
        setCategoryError(true)
      })
  }, [])

  const beforeUpload: UploadProps['beforeUpload'] = (file, nextFiles) => {
    if (files.length + nextFiles.length > 9) {
      setImageError('商品图最多上传 9 张')
      message.error('商品图最多上传 9 张')
      return Upload.LIST_IGNORE
    }
    const validationError = imageValidationError(file)
    if (validationError) {
      setImageError(`${file.name}：${validationError}`)
      message.error(`${file.name}：${validationError}`)
      return Upload.LIST_IGNORE
    }
    setImageError('')
    return false
  }

  const onFinish = async (values: PublishValues) => {
    if (values.category?.length !== 2) {
      form.setFields([{ name: 'category', errors: ['请选择二级类目'] }])
      return
    }
    const data = new FormData()
    data.append('name', values.name.trim())
    data.append('price', String(values.price))
    data.append('category2Id', String(values.category[1]))
    data.append('stock', String(values.stock))
    if (descriptionHtml.trim()) data.append('descriptionHtml', descriptionHtml)
    files.forEach((file) => {
      if (file.originFileObj) data.append('images[]', file.originFileObj)
    })

    try {
      setSaving(true)
      await createProduct(data)
      message.success('商品发布成功')
      form.resetFields()
      setDescriptionHtml('')
      setEditorKey((key) => key + 1)
      setFiles([])
      setImageError('')
    } catch (error) {
      console.error('发布商品失败:', error)
      if (error instanceof ApiError && error.code === 41301) setImageError('图片不能超过 5MB')
      if (error instanceof ApiError && error.code === 41501) setImageError('图片格式仅支持 JPG、PNG')
    } finally {
      setSaving(false)
    }
  }

  const categoryOptions = categories.map((parent) => ({
    value: parent.id,
    label: parent.name,
    children: (parent.children ?? []).map((child) => ({ value: child.id, label: child.name })),
  }))

  return (
    <main style={{ maxWidth: 800, margin: '0 auto', padding: 24 }}>
      <Card title="发布商品">
        {categoryError && <Alert style={{ marginBottom: 16 }} type="error" showIcon message="类目加载失败，暂时无法发布商品。" />}
        <Form form={form} layout="vertical" onFinish={onFinish} initialValues={{ stock: 0 }}>
          <Form.Item label="商品名称" name="name" rules={[{ required: true, whitespace: true, message: '请输入商品名称' }]}>
            <Input />
          </Form.Item>
          <Form.Item label="价格" name="price" rules={[{ required: true, message: '请输入价格' }, { type: 'number', min: 0.01, message: '价格必须大于 0' }]}>
            <InputNumber min={0.01} precision={2} prefix="¥" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="二级类目" name="category" rules={[{ required: true, message: '请选择二级类目' }]}>
            <Cascader options={categoryOptions} placeholder="请选择一级及二级类目" />
          </Form.Item>
          <Form.Item label="库存数量" name="stock" rules={[{ required: true, message: '请输入库存' }, { type: 'number', min: 0, message: '库存必须为非负整数' }]}>
            <InputNumber min={0} precision={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="商品描述（选填）">
            <RichTextEditor key={editorKey} onChange={setDescriptionHtml} />
          </Form.Item>
          <Form.Item
            label="商品图片（选填，最多 9 张，JPG/PNG，单张不超过 5MB）"
            validateStatus={imageError ? 'error' : undefined}
            help={imageError || undefined}
          >
            <Upload
              accept=".jpg,.jpeg,.png,image/jpeg,image/png"
              listType="picture"
              fileList={files}
              beforeUpload={beforeUpload}
              onChange={({ fileList }) => {
                setFiles(fileList.slice(0, 9))
                setImageError('')
              }}
              multiple
            >
              {files.length < 9 && <Button>选择图片</Button>}
            </Upload>
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>发布商品</Button>
        </Form>
      </Card>
    </main>
  )
}
