import { Routes, Route, Navigate } from 'react-router-dom'
import ProductPage from './pages/buyer/ProductPage'
import IntentQueryPage from './pages/buyer/IntentQueryPage'
import LoginPage from './pages/admin/LoginPage'
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
      <Route path="/intent/:code" element={<IntentQueryPage />} />

      {/* 卖家端 */}
      <Route path="/admin/login" element={<LoginPage />} />
      <Route path="/admin/products/current" element={<RequireAuth><CurrentProductPage /></RequireAuth>} />
      <Route path="/admin/products/publish" element={<RequireAuth><PublishProductPage /></RequireAuth>} />
      <Route path="/admin/products/history" element={<RequireAuth><ProductHistoryPage /></RequireAuth>} />
      <Route path="/admin/intents" element={<RequireAuth><IntentQueuePage /></RequireAuth>} />
      <Route path="/admin/password" element={<RequireAuth><ChangePasswordPage /></RequireAuth>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
