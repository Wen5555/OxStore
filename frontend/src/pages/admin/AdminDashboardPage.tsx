import { HistoryOutlined, LockOutlined, OrderedListOutlined, ShopOutlined, UploadOutlined } from '@ant-design/icons'
import { Button, Card, Typography } from 'antd'
import { useNavigate } from 'react-router-dom'

const { Title } = Typography

const destinations = [
  { label: '意向队列', path: '/admin/intents', icon: <OrderedListOutlined /> },
  { label: '当前商品', path: '/admin/products/current', icon: <ShopOutlined /> },
  { label: '发布商品', path: '/admin/products/publish', icon: <UploadOutlined /> },
  { label: '商品历史', path: '/admin/products/history', icon: <HistoryOutlined /> },
  { label: '修改密码', path: '/admin/password', icon: <LockOutlined /> },
]

export default function AdminDashboardPage() {
  const navigate = useNavigate()

  return (
    <main style={{ maxWidth: 1080, margin: '0 auto', padding: 24 }}>
      <Title level={2} style={{ marginTop: 0 }}>卖家功能</Title>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))', gap: 16 }}>
        {destinations.map(({ label, path, icon }) => (
          <Card key={path}>
            <Button
              block
              size="large"
              icon={icon}
              onClick={() => navigate(path)}
            >
              {label}
            </Button>
          </Card>
        ))}
      </div>
    </main>
  )
}