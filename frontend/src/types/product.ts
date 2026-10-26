export type ProductStatus = 'ONLINE' | 'FROZEN' | 'OFFLINE'

export interface ProductImage {
  url: string
  position: number
}

export interface ProductSummary {
  id: number
  name: string
  price: number
  category2Id: number
  categoryName: string
  mainImageUrl: string | null
}

export interface Product {
  id: number
  name: string
  price: number
  stock: number
  category2Id: number
  categoryName: string
  status: ProductStatus
  canPurchase: boolean
  descriptionHtml?: string
  images: ProductImage[]
  mainImageUrl: string | null
}

export interface ProductSummaryResponse {
  productId: number
  name: string
  price: number
  mainImagePath: string | null
  category2Id: number
  category2Name: string
}

export interface ProductDetailResponse {
  productId: number
  name: string
  price: number
  category2Id: number
  category2Name: string
  stock: number
  descriptionHtml: string
  images: string[]
  mainImagePath: string | null
  status: ProductStatus
  canPurchase: boolean
  publishedAt: string
  statusUpdatedAt: string
}

export function mapProductSummary(response: ProductSummaryResponse): ProductSummary {
  return {
    id: response.productId,
    name: response.name,
    price: response.price,
    category2Id: response.category2Id,
    categoryName: response.category2Name,
    mainImageUrl: response.mainImagePath,
  }
}

export function mapProductDetail(response: ProductDetailResponse): Product {
  return {
    id: response.productId,
    name: response.name,
    price: response.price,
    stock: response.stock,
    category2Id: response.category2Id,
    categoryName: response.category2Name,
    status: response.status,
    canPurchase: response.canPurchase,
    descriptionHtml: response.descriptionHtml,
    images: response.images.map((url, position) => ({ url, position })),
    mainImageUrl: response.mainImagePath,
  }
}
