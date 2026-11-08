import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import AdminLayout from './pages/admin/AdminLayout'
import AdminProductsPage from './pages/admin/AdminProductsPage'
import AdminAuctionsPage from './pages/admin/AdminAuctionsPage'
import ChangePasswordPage from './pages/admin/ChangePasswordPage'
import CustomerHistoryPage from './pages/admin/CustomerHistoryPage'
import CustomersPage from './pages/admin/CustomersPage'
import LoginPage from './pages/admin/LoginPage'
import ProductEditPage from './pages/admin/ProductEditPage'
import ProductIntentQueuePage from './pages/admin/ProductIntentQueuePage'
import PublishProductPage from './pages/admin/PublishProductPage'
import SellerAuctionNotificationsPage from './pages/admin/SellerAuctionNotificationsPage'
import BuyerAccountPage from './pages/buyer/BuyerAccountPage'
import BuyerAuthPage from './pages/buyer/BuyerAuthPage'
import BuyerHistoryPage from './pages/buyer/BuyerHistoryPage'
import BuyerAuctionNotificationsPage from './pages/buyer/BuyerAuctionNotificationsPage'
import ProductDetailPage from './pages/buyer/ProductDetailPage'
import ProductListPage from './pages/buyer/ProductListPage'

function RequireSeller({ children }: { children: JSX.Element }) {
  const location = useLocation()
  if (!localStorage.getItem('seller_token')) {
    return <Navigate to="/admin/login" replace state={{ from: location.pathname }} />
  }
  return children
}

function RequireCustomer({ children }: { children: JSX.Element }) {
  const location = useLocation()
  if (!localStorage.getItem('customer_token')) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<ProductListPage />} />
      <Route path="/products/:id" element={<ProductDetailPage />} />
      <Route path="/login" element={<BuyerAuthPage />} />
      <Route path="/register" element={<BuyerAuthPage registration />} />
      <Route path="/me/account" element={<RequireCustomer><BuyerAccountPage /></RequireCustomer>} />
      <Route path="/me/order-history" element={<RequireCustomer><BuyerHistoryPage /></RequireCustomer>} />
      <Route path="/me/auction-notifications" element={<RequireCustomer><BuyerAuctionNotificationsPage /></RequireCustomer>} />

      <Route path="/admin/login" element={<LoginPage />} />
      <Route path="/admin" element={<RequireSeller><AdminLayout /></RequireSeller>}>
        <Route index element={<Navigate to="products" replace />} />
        <Route path="products" element={<AdminProductsPage />} />
        <Route path="auctions" element={<AdminAuctionsPage />} />
        <Route path="products/publish" element={<PublishProductPage />} />
        <Route path="products/:id/edit" element={<ProductEditPage />} />
        <Route path="products/:id/intents" element={<ProductIntentQueuePage />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="customers/:customerId/order-history" element={<CustomerHistoryPage />} />
        <Route path="password" element={<ChangePasswordPage />} />
        <Route path="auction-notifications" element={<SellerAuctionNotificationsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
