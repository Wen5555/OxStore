export type ProductStatus = 'ONLINE' | 'FROZEN' | 'OFFLINE'
export type SellingMode = 'FIXED_PRICE' | 'AUCTION'
export type AuctionStatus = 'LIVE' | 'ENDED_SOLD' | 'ENDED_UNSOLD'

export interface AuctionSummary {
  auctionStatus: AuctionStatus
  currentPrice: number
  nextMinBid: number
  endsAt: string
  bidCount: number
}

export interface ProductImage {
  url: string
  position: number
}

export interface ProductSummary {
  id: string
  name: string
  price: number
  category2Id: number
  categoryName: string
  mainImageUrl: string | null
  sellingMode: SellingMode
  auction?: AuctionSummary
}

export interface Product {
  id: string
  name: string
  price: number
  stock: string
  category2Id: number
  categoryName: string
  status: ProductStatus
  canPurchase: boolean
  descriptionHtml?: string
  images: ProductImage[]
  mainImageUrl: string | null
  sellingMode: SellingMode
  auction?: AuctionSummary
}

export interface ProductSummaryResponse {
  productId: string | number
  name: string
  price: number
  mainImagePath: string | null
  category2Id: number
  category2Name: string
  sellingMode?: SellingMode
  auction?: AuctionSummary
}

export interface ProductDetailResponse {
  productId: string | number
  name: string
  price: number
  category2Id: number
  category2Name: string
  stock: string
  descriptionHtml: string
  images: string[]
  mainImagePath: string | null
  status: ProductStatus
  canPurchase: boolean
  publishedAt: string
  statusUpdatedAt: string
  sellingMode?: SellingMode
  auction?: AuctionSummary
}

export function mapProductSummary(response: ProductSummaryResponse): ProductSummary {
  return {
    id: String(response.productId),
    name: response.name,
    price: response.price,
    category2Id: response.category2Id,
    categoryName: response.category2Name,
    mainImageUrl: response.mainImagePath,
    sellingMode: response.sellingMode ?? 'FIXED_PRICE',
    auction: response.auction,
  }
}

export function mapProductDetail(response: ProductDetailResponse): Product {
  return {
    id: String(response.productId),
    name: response.name,
    price: response.price,
    stock: String(response.stock),
    category2Id: response.category2Id,
    categoryName: response.category2Name,
    status: response.status,
    canPurchase: response.canPurchase,
    descriptionHtml: response.descriptionHtml,
    images: response.images.map((url, position) => ({ url, position })),
    mainImageUrl: response.mainImagePath,
    sellingMode: response.sellingMode ?? 'FIXED_PRICE',
    auction: response.auction,
  }
}
