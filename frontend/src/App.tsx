import { Routes, Route, Navigate } from 'react-router-dom'
import ProductPage from './pages/buyer/ProductPage'
import IntentQueryPage from './pages/buyer/IntentQueryPage'
import LoginPage from './pages/admin/LoginPage'
import AdminDashboardPage from './pages/admin/AdminDashboardPage'
import AdminLayout from './pages/admin/AdminLayout'
import CurrentProductPage from './pages/admin/CurrentProductPage'
import PublishProductPage from './pages/admin/PublishProductPage'
import ProductHistoryPage from './pages/admin/ProductHistoryPage'
import IntentQueuePage from './pages/admin/IntentQueuePage'
import ChangePasswordPage from './pages/admin/ChangePasswordPage'

function RequireAuth({ children }: { children: JSX.Element }) {
  const token = localStorage.getItem('shop_token')
  if (!token) {
    return <Navigate to="/admin/login" replace />
  }
  return children
}

export default function App() {
  return (
    <Routes>
      {/* 买家端 */}
      <Route path="/" element={<ProductPage />} />
      <Route path="/intent" element={<IntentQueryPage />} />
      <Route path="/intent/:code" element={<IntentQueryPage />} />

      {/* 卖家端 */}
      <Route path="/admin/login" element={<LoginPage />} />
      <Route path="/admin" element={<RequireAuth><AdminLayout /></RequireAuth>}>
        <Route index element={<AdminDashboardPage />} />
        <Route path="products/current" element={<CurrentProductPage />} />
        <Route path="products/publish" element={<PublishProductPage />} />
        <Route path="products/history" element={<ProductHistoryPage />} />
        <Route path="products/history/:id" element={<ProductHistoryPage />} />
        <Route path="products/:id/records" element={<ProductHistoryPage />} />
        <Route path="intents" element={<IntentQueuePage />} />
        <Route path="password" element={<ChangePasswordPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
