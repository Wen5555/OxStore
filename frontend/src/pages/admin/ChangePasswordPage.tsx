import { useState } from 'react'
import { Button, Card, Form, Input, message } from 'antd'
import { changePassword } from '../../api/auth'

interface PasswordFormValues {
  oldPassword: string
  newPassword: string
  confirmPassword: string
}

export default function ChangePasswordPage() {
  const [form] = Form.useForm<PasswordFormValues>()
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (values: PasswordFormValues) => {
    try {
      setSaving(true)
      await changePassword({ oldPassword: values.oldPassword, newPassword: values.newPassword })
      message.success('密码修改成功')
      form.resetFields()
    } catch (error) {
      console.error('修改密码失败:', error)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ maxWidth: 560, margin: '0 auto', padding: 24 }}>
      <Card title="修改密码">
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item label="当前密码" name="oldPassword" rules={[{ required: true, message: '请输入当前密码' }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Form.Item
            label="新密码"
            name="newPassword"
            rules={[
              { required: true, message: '请输入新密码' },
              {
                pattern: /^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/,
                message: '新密码至少 8 位，且须包含字母、数字和特殊符号',
              },
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            label="确认新密码"
            name="confirmPassword"
            dependencies={['newPassword']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value: string | undefined) {
                  return !value || getFieldValue('newPassword') === value
                    ? Promise.resolve()
                    : Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={saving}>
            保存新密码
          </Button>
        </Form>
      </Card>
    </div>
  )
}
