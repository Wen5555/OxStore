import { useEffect, useState } from 'react'
import { Button, Card, Form, Input, message } from 'antd'
import { useLocation, useNavigate } from 'react-router-dom'
import { sellerLogin } from '../../api/auth'
import { consumeAuthRedirectMessage, getReturnPath } from '../../utils/navigation'

interface LoginFormValues {
  username: string
  password: string
}

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo = getReturnPath(location.state, location.search, '/admin')

  useEffect(() => {
    const authMessage = consumeAuthRedirectMessage()
    if (authMessage) message.error(authMessage)
  }, [])

  const handleLogin = async (values: LoginFormValues) => {
    try {
      setLoading(true)
      const result = await sellerLogin(values)
      localStorage.setItem('seller_token', result.token)
      navigate(returnTo, { replace: true })
    } catch (error) {
      console.error('卖家登录失败:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 420, margin: '80px auto', padding: 24 }}>
      <Card title="卖家登录">
        <Form layout="vertical" onFinish={handleLogin}>
          <Form.Item label="账号" name="username" rules={[{ required: true, message: '请输入账号' }]}>
            <Input autoComplete="username" />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={loading} block>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  )
}
