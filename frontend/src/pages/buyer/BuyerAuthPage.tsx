import { useState } from 'react'
import { Button, Card, Form, Input, Space, Typography, message } from 'antd'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { login, register } from '../../api/auth'

interface AuthValues {
  username: string
  password: string
  phone?: string
  location?: string
}

export default function BuyerAuthPage({ registration = false }: { registration?: boolean }) {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo = (location.state as { from?: string } | null)?.from ?? '/'

  const onFinish = async (values: AuthValues) => {
    try {
      setLoading(true)
      if (registration) {
        await register({
          username: values.username.trim(),
          password: values.password,
          phone: values.phone!.trim(),
          ...(values.location?.trim() ? { location: values.location.trim() } : {}),
        })
        message.success('注册成功，请登录')
        navigate('/login', { replace: true })
      } else {
        const result = await login({ username: values.username.trim(), password: values.password })
        localStorage.setItem('customer_token', result.token)
        localStorage.setItem('customer_username', result.username)
        localStorage.setItem('customer_user_id', String(result.userId))
        message.success('登录成功')
        navigate(returnTo, { replace: true })
      }
    } catch (error) {
      console.error(registration ? '顾客注册失败:' : '顾客登录失败:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main style={{ maxWidth: 480, margin: '48px auto', padding: 24 }}>
      <Card title={registration ? '顾客注册' : '顾客登录'}>
        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item label="用户名" name="username" rules={[{ required: true, whitespace: true, message: '请输入用户名' }, { max: 50, message: '用户名不能超过 50 个字符' }]}>
            <Input autoComplete="username" />
          </Form.Item>
          <Form.Item
            label="密码"
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              ...(registration ? [{ min: 8, message: '密码不少于 8 位' }] : []),
              ...(registration ? [{ max: 64, message: '密码不能超过 64 位' }] : []),
            ]}
          >
            <Input.Password autoComplete={registration ? 'new-password' : 'current-password'} />
          </Form.Item>
          {registration && (
            <>
              <Form.Item label="手机号" name="phone" rules={[{ required: true, whitespace: true, message: '请输入手机号' }, { max: 20, message: '手机号不能超过 20 个字符' }]}>
                <Input autoComplete="tel" />
              </Form.Item>
              <Form.Item label="默认交易地点（选填）" name="location" rules={[{ max: 200, message: '默认交易地点不能超过 200 个字符' }]}>
                <Input />
              </Form.Item>
            </>
          )}
          <Button type="primary" htmlType="submit" loading={loading} block>
            {registration ? '注册' : '登录'}
          </Button>
        </Form>
        <Space style={{ marginTop: 16 }}>
          <Typography.Text>{registration ? '已有账号？' : '还没有账号？'}</Typography.Text>
          <Link to={registration ? '/login' : '/register'}>{registration ? '登录' : '注册'}</Link>
          <Link to="/">返回商品列表</Link>
        </Space>
      </Card>
    </main>
  )
}
