export type ProductStatus = 'ONLINE' | 'FROZEN' | 'OFFLINE'

export interface ProductImage {
  id?: number
  url: string
  position: number
}

export interface Product {
  id: number
  name: string
  price: number
  stock: number
  category2Id: number
  categoryName: string
  status: ProductStatus
  descriptionHtml?: string
  images: ProductImage[]
  mainImageUrl?: string
}
