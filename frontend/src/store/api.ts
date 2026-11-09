import { apiGet, apiRequest } from '../lib/api-client'
import type {
  CheckoutPayload,
  CustomerProfile,
  OrderCreated,
  OrderDetail,
  OrderPage,
  ProductDetailData,
  ProductFavoritePage,
  ProductPage,
  PublicStoreSettings,
  StoreCategory,
  StoreCurrency,
  StoreSizeOption,
} from './types'

export interface CatalogFilters {
  group: 'clothing' | 'shoes'
  section: 'men' | 'women'
  currency: StoreCurrency
  search?: string
  categoryId?: string
  size?: string
  minPrice?: string
  maxPrice?: string
  onSale?: boolean
  sort: 'newest' | 'price_desc' | 'price_asc'
}

export const storeKeys = {
  products: (filters: CatalogFilters) => ['store', 'products', filters] as const,
  product: (id: string, currency: StoreCurrency) => ['store', 'product', id, currency] as const,
  categories: (group: 'clothing' | 'shoes') => ['store', 'categories', group] as const,
  sizes: (group: 'clothing' | 'shoes') => ['store', 'sizes', group] as const,
  settings: (currency: StoreCurrency) => ['store', 'settings', currency] as const,
  profile: ['store', 'profile'] as const,
  orders: ['store', 'orders'] as const,
  order: (id: string) => ['store', 'order', id] as const,
}

export async function getProducts(
  filters: CatalogFilters,
  page: number,
  signal?: AbortSignal,
): Promise<ProductPage> {
  const params = new URLSearchParams({
    group: filters.group,
    section: filters.section,
    currency: filters.currency,
    sort: filters.sort,
    page: String(page),
    page_size: '20',
  })
  if (filters.search?.trim()) params.set('search', filters.search.trim())
  if (filters.categoryId) params.set('category_id', filters.categoryId)
  if (filters.size) params.set('size', filters.size)
  if (filters.minPrice) params.set('min_price', filters.minPrice)
  if (filters.maxPrice) params.set('max_price', filters.maxPrice)
  if (filters.onSale) params.set('on_sale', 'true')
  return apiGet<ProductPage>(`/api/store/products?${params}`, signal)
}

export function getProduct(
  id: string,
  currency: StoreCurrency,
  signal?: AbortSignal,
): Promise<ProductDetailData> {
  return apiGet(
    `/api/store/products/${encodeURIComponent(id)}?currency=${currency}`,
    signal,
  )
}

export function getCategories(
  group: 'clothing' | 'shoes',
  signal?: AbortSignal,
): Promise<StoreCategory[]> {
  return apiGet(`/api/store/categories?group=${group}`, signal)
}

export function getSizes(
  group: 'clothing' | 'shoes',
  signal?: AbortSignal,
): Promise<StoreSizeOption[]> {
  return apiGet(`/api/store/sizes?group=${group}`, signal)
}

export function getFavorites(
  currency: StoreCurrency,
  signal?: AbortSignal,
): Promise<ProductFavoritePage> {
  return apiGet(
    `/api/store/favorites?currency=${currency}&page=1&page_size=100`,
    signal,
  )
}

export function getPublicSettings(
  currency: StoreCurrency,
  signal?: AbortSignal,
): Promise<PublicStoreSettings> {
  return apiGet(`/api/store/settings?currency=${currency}`, signal)
}

export function getCustomerProfile(signal?: AbortSignal): Promise<CustomerProfile> {
  return apiGet('/api/me', signal)
}

export function getOrders(signal?: AbortSignal): Promise<OrderPage> {
  return apiGet('/api/orders?page=1&page_size=20', signal)
}

export function getOrder(
  id: string,
  signal?: AbortSignal,
): Promise<OrderDetail> {
  return apiGet(`/api/orders/${encodeURIComponent(id)}`, signal)
}

export function createOrder(payload: CheckoutPayload): Promise<OrderCreated> {
  return apiRequest('/api/orders', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
