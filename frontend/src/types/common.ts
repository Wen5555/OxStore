// 通用响应结构：与后端 ApiResponse 对齐
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  traceId?: string
}

// 分页数据
export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface Category {
  id: number
  name: string
  children: Category[]
}

export interface CategoryTreeItem {
  id: number
  name: string
  children: Category[]
}

export interface Customer {
  customerId: number
  username: string
  phone: string
  location: string | null
  registeredAt: string
}

export interface OrderHistoryItem {
  orderId: number
  productName: string
  submittedAt: string
  status: 'SUCCESS' | 'FAILED'
  transactedAt: string
}
