export type StoreCurrency = 'BYN' | 'RUB'
export type StoreSection = 'men' | 'women' | 'unisex'

export interface ProductImage {
  url: string
  thumbnail_url?: string
}

export interface ProductCardData {
  id: string
  category_id: string
  category_name: string
  group: 'clothing' | 'shoes'
  title: string
  brand: string | null
  section: StoreSection
  images: ProductImage[]
  sizes: string[]
  is_new: boolean
  currency: StoreCurrency
  price: number | string
  original_price: number | string | null
  on_sale: boolean
  stock: number
  sold: boolean
  created_at: string
}

export interface ProductVariant {
  id: string
  size: string
  color: string
  stock: number
  currency: StoreCurrency
  price: number | string
}

export interface ProductDetailData extends ProductCardData {
  description: string | null
  sizes: string[]
  colors: string[]
  variants: ProductVariant[]
}

export interface StoreCategory {
  id: string
  name: string
  slug: string
  description: string | null
  group_key: 'clothing' | 'shoes'
}

export interface StoreSizeOption {
  id: string
  group_key: 'clothing' | 'shoes'
  value: string
  sort_order: number
}

export interface ProductFavoritePage {
  items: ProductCardData[]
  page: number
  page_size: number
  total: number
  currency: StoreCurrency
}

export interface ProductPage {
  items: ProductCardData[]
  page: number
  page_size: number
  total: number
  total_pages: number
  currency: StoreCurrency
}

export interface StoreCartLine {
  variant_id: string
  product_id: string
  title: string
  image: ProductImage | null
  size: string
  color: string
  quantity: number
  stock: number
  currency: StoreCurrency
  unit_price: number | string
  line_total: number | string
}

export interface StoreCart {
  items: StoreCartLine[]
  currency: StoreCurrency
  items_total: number | string
  item_count: number
}

export interface DeliveryMethod {
  id: string
  code: string
  name: string
  currency: StoreCurrency
  price: number | string | null
  price_note: string | null
}

export interface PublicStoreSettings {
  manager_username: string
  reviews_url: string
  store_name: string
  currency: StoreCurrency
  delivery_methods: DeliveryMethod[]
}

export interface CustomerProfile {
  telegram_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  photo_url: string | null
  preferred_section: StoreSection
  preferred_currency: StoreCurrency
  is_admin: boolean
}

export interface OrderLine {
  product_id: string | null
  product_name: string
  size: string
  color: string
  quantity: number
  currency: StoreCurrency
  unit_price: number | string
  line_total: number | string
}

export interface OrderSummary {
  id: string
  status: string
  recipient_name: string
  phone: string
  delivery_method_name: string
  city: string
  delivery_address: string
  currency: StoreCurrency
  items_total: number | string
  total: number | string
  created_at: string
}

export interface OrderDetail extends OrderSummary {
  delivery_price: number | string | null
  delivery_price_note: string | null
  comment: string | null
  items: OrderLine[]
}

export interface OrderPage {
  items: OrderSummary[]
  page: number
  page_size: number
  total: number
}

export interface OrderCreated {
  order: OrderDetail
  manager_link: string
}

export interface CheckoutPayload {
  recipient_name: string
  phone: string
  delivery_method_id: string
  city: string
  address?: string
  branch?: string
  comment?: string
}
