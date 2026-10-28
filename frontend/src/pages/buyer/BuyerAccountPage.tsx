import { IdcardOutlined, LogoutOutlined, ShoppingOutlined, UnorderedListOutlined, UserOutlined } from '@ant-design/icons'
import { Button, Card, Descriptions, Space, Tag, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'

export default function BuyerAccountPage() {
  const navigate = useNavigate()
  const username = localStorage.getItem('customer_username') || '已登录顾客'
  const customerId = localStorage.getItem('customer_user_id')

  const logout = () => {
    localStorage.removeItem('customer_token')
    localStorage.removeItem('customer_username')
    localStorage.removeItem('customer_user_id')
    navigate('/', { replace: true })
  }

  return (
    <main style={{ maxWidth: 900, margin: '0 auto', padding: 24 }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Typography.Title level={2} style={{ margin: 0 }}>买家账户</Typography.Title>
          <Typography.Text type="secondary">查看账户信息，管理你的 OxStore 购物体验。</Typography.Text>
        </div>

        <Card>
          <Space align="start" size="middle" style={{ marginBottom: 24 }}>
            <UserOutlined style={{ fontSize: 28, color: '#1677ff', padding: 12, background: '#e6f4ff', borderRadius: '50%' }} />
            <div>
              <Typography.Title level={4} style={{ margin: '0 0 8px' }}>{username}</Typography.Title>
              <Tag color="blue">买家账户</Tag>
            </div>
          </Space>

          <Descriptions column={{ xs: 1, sm: 2 }} bordered>
            <Descriptions.Item label={<><UserOutlined /> 用户名</>}>{username}</Descriptions.Item>
            <Descriptions.Item label={<><IdcardOutlined /> 顾客编号</>}>{customerId || '—'}</Descriptions.Item>
          </Descriptions>
        </Card>

        <Card title="账户服务">
          <Space wrap>
            <Button type="primary" icon={<UnorderedListOutlined />} onClick={() => navigate('/me/order-history')}>
              查看购买历史
            </Button>
            <Button icon={<ShoppingOutlined />} onClick={() => navigate('/')}>
              继续购物
            </Button>
            <Button danger icon={<LogoutOutlined />} onClick={logout}>
              退出登录
            </Button>
          </Space>
        </Card>
      </Space>
    </main>
  )
}
