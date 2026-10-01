// 通用响应结构：与后端 ApiResponse 对齐
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

// 分页数据
export interface Page<T> {
  list: T[]
  total: number
  page: number
  size: number
}
