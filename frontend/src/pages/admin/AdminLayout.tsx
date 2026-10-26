import { LockOutlined, ShopOutlined, UploadOutlined, UserOutlined } from '@ant-design/icons'
import { Button, Layout, Space, Typography } from 'antd'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

const { Header, Content } = Layout
const { Text } = Typography

const navigation = [
  { label: '商品管理', path: '/admin/products', icon: <ShopOutlined /> },
  { label: '发布商品', path: '/admin/products/publish', icon: <UploadOutlined /> },
  { label: '全部顾客', path: '/admin/customers', icon: <UserOutlined /> },
  { label: '修改密码', path: '/admin/password', icon: <LockOutlined /> },
]

export default function AdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const selectedPath = location.pathname.startsWith('/admin/customers')
    ? '/admin/customers'
    : location.pathname.startsWith('/admin/products')
      ? (location.pathname.endsWith('/publish') ? '/admin/products/publish' : '/admin/products')
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