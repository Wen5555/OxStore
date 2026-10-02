import { AppstoreOutlined, HistoryOutlined, LockOutlined, OrderedListOutlined, ShopOutlined, UploadOutlined } from '@ant-design/icons'
import { Button, Layout, Space, Typography } from 'antd'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

const { Header, Content } = Layout
const { Text } = Typography

const navigation = [
  { label: '功能首页', path: '/admin', icon: <AppstoreOutlined /> },
  { label: '意向队列', path: '/admin/intents', icon: <OrderedListOutlined /> },
  { label: '当前商品', path: '/admin/products/current', icon: <ShopOutlined /> },
  { label: '发布商品', path: '/admin/products/publish', icon: <UploadOutlined /> },
  { label: '商品历史', path: '/admin/products/history', icon: <HistoryOutlined /> },
  { label: '修改密码', path: '/admin/password', icon: <LockOutlined /> },
]

export default function AdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const selectedPath = location.pathname.endsWith('/records')
    ? '/admin/products/history'
    : location.pathname.startsWith('/admin/products/history/')
      ? '/admin/products/history'
      : location.pathname

  return (
    <Layout style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <Header style={{ height: 'auto', padding: '12px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, background: '#fff', borderBottom: '1px solid #f0f0f0' }}>
        <Text strong style={{ fontSize: 18, whiteSpace: 'nowrap' }}>OxStore 卖家后台</Text>
        <Space wrap>
          {navigation.map(({ label, path, icon }) => (
            <Button
              key={path}
              type={selectedPath === path ? 'primary' : 'default'}
              icon={icon}
              onClick={() => navigate(path)}
            >
              {label}
            </Button>
          ))}
        </Space>
      </Header>
      <Content>
        <Outlet />
      </Content>
    </Layout>
  )
}