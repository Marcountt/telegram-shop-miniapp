import { apiGet, apiRequest } from '../lib/api-client'
import type { OrderDetail, OrderSummary, ProductImage, StoreSection } from './types'

export type AdminProductStatus = 'active' | 'hidden' | 'sold'
export type AdminOrderAction = 'confirm' | 'shipped' | 'delivered' | 'cancel'

export interface AdminVariant {
  id: string
  size: string
  color: string
  stock: number
}

export interface AdminImage extends ProductImage {
  id: string
  alt: string
  is_cover: boolean
}

export interface AdminProduct {
  id: string
  title: string
  brand: string | null
  description: string | null
  section: StoreSection
  category_id: string
  category_name: string
  price_byn: number | string
  price_rub: number | string | null
  old_price_byn: number | string | null
  old_price_rub: number | string | null
  is_new: boolean
  is_active: boolean
  sold_at: string | null
  images: AdminImage[]
  variants: AdminVariant[]
  created_at: string
  updated_at: string
}

export interface AdminProductPage {
  items: AdminProduct[]
  page: number
  page_size: number
  total: number
}

export interface AdminProductPayload {
  title: string
  brand: string | null
  description: string | null
  section: StoreSection
  category_id: string
  price_byn: number
  price_rub?: number
  rub_price_mode: 'auto' | 'manual'
  old_price_byn?: number
  old_price_rub?: number
  sizes: Array<{ size: string; quantity: number; color: string }>
  is_new: boolean
}

export interface AdminCategory {
  id: string
  name: string
  slug: string
  description: string | null
  group_key: 'clothing' | 'shoes'
  is_active: boolean
}

export interface AdminCategoryPayload {
  name: string
  slug: string
  description: string | null
  group_key: 'clothing' | 'shoes'
  is_active: boolean
}

export interface AdminSize {
  id: string
  group_key: 'clothing' | 'shoes'
  value: string
  is_active: boolean
  sort_order: number
}

export interface AdminSizePayload {
  group_key: 'clothing' | 'shoes'
  value: string
  is_active: boolean
  sort_order: number
}

export interface AdminOrder {
  order: OrderSummary
  customer_telegram_id: number
  customer_username: string | null
}

export interface AdminOrderDetail {
  order: OrderDetail
  customer_telegram_id: number
  customer_username: string | null
}

export interface AdminOrderPage {
  items: AdminOrder[]
  page: number
  page_size: number
  total: number
}

export interface AdminDelivery {
  id: string
  code: string
  name: string
  price_byn: number | string | null
  price_note: string | null
  is_active: boolean
  sort_order: number
}

export interface AdminDeliveryPayload {
  code: string
  name: string
  price_byn: number | null
  price_note: string | null
  is_active: boolean
  sort_order: number
}

export interface AdminSettings {
  manager_username: string
  reviews_url: string
  store_name: string
  welcome_text: string
  delivery_info_text: string
  how_to_order_steps: string[]
  byn_to_rub_rate: number | string
  deliveries: AdminDelivery[]
}

export interface AdminDashboard {
  pending_orders: number
  today_orders: number
  today_revenue_byn: number | string
  week_orders: number
  week_revenue_byn: number | string
  one_size_left: Array<{
    id: string
    title: string
    category_name: string
    stock: number
    image_url: string | null
  }>
}

export const adminKeys = {
  dashboard: ['admin', 'dashboard'] as const,
  products: (search: string, categoryId: string, status: string) =>
    ['admin', 'products', search, categoryId, status] as const,
  categories: ['admin', 'categories'] as const,
  sizes: ['admin', 'sizes'] as const,
  orders: (status: string) => ['admin', 'orders', status] as const,
  order: (id: string) => ['admin', 'order', id] as const,
  settings: ['admin', 'settings'] as const,
}

export function getAdminDashboard(signal?: AbortSignal): Promise<AdminDashboard> {
  return apiGet('/api/admin/dashboard', signal)
}

export function getAdminProducts(
  search: string,
  categoryId: string,
  status: string,
  signal?: AbortSignal,
): Promise<AdminProductPage> {
  const params = new URLSearchParams({ page: '1', page_size: '100' })
  if (search.trim()) params.set('search', search.trim())
  if (categoryId) params.set('category_id', categoryId)
  if (status) params.set('status', status)
  return apiGet(`/api/admin/products?${params}`, signal)
}

export function getAdminProduct(id: string, signal?: AbortSignal): Promise<AdminProduct> {
  return apiGet(`/api/admin/products/${encodeURIComponent(id)}`, signal)
}

export function createAdminProduct(payload: AdminProductPayload): Promise<AdminProduct> {
  return apiRequest('/api/admin/products', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateAdminProduct(
  id: string,
  payload: AdminProductPayload,
): Promise<AdminProduct> {
  return apiRequest(`/api/admin/products/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function setProductVisibility(id: string, isActive: boolean): Promise<AdminProduct> {
  return apiRequest(
    `/api/admin/products/${encodeURIComponent(id)}/visibility?is_active=${isActive}`,
    { method: 'PATCH' },
  )
}

export function markProductSold(id: string): Promise<AdminProduct> {
  return apiRequest(`/api/admin/products/${encodeURIComponent(id)}/sold`, { method: 'PATCH' })
}

export function deleteAdminProduct(id: string): Promise<void> {
  return apiRequest(`/api/admin/products/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function uploadProductImages(id: string, files: File[]): Promise<AdminImage[]> {
  const body = new FormData()
  files.forEach((file) => body.append('files', file))
  return apiRequest(`/api/admin/products/${encodeURIComponent(id)}/images`, {
    method: 'POST',
    body,
  })
}

export function reorderProductImages(id: string, imageIds: string[]): Promise<AdminImage[]> {
  return apiRequest(`/api/admin/products/${encodeURIComponent(id)}/images/order`, {
    method: 'PUT',
    body: JSON.stringify({ image_ids: imageIds }),
  })
}

export function deleteProductImage(productId: string, imageId: string): Promise<void> {
  return apiRequest(
    `/api/admin/products/${encodeURIComponent(productId)}/images/${encodeURIComponent(imageId)}`,
    { method: 'DELETE' },
  )
}

export function getAdminCategories(signal?: AbortSignal): Promise<AdminCategory[]> {
  return apiGet('/api/admin/categories', signal)
}

export function createAdminCategory(payload: AdminCategoryPayload): Promise<AdminCategory> {
  return apiRequest('/api/admin/categories', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateAdminCategory(
  id: string,
  payload: AdminCategoryPayload,
): Promise<AdminCategory> {
  return apiRequest(`/api/admin/categories/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteAdminCategory(id: string): Promise<void> {
  return apiRequest(`/api/admin/categories/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function getAdminSizes(signal?: AbortSignal): Promise<AdminSize[]> {
  return apiGet('/api/admin/size-options', signal)
}

export function createAdminSize(payload: AdminSizePayload): Promise<AdminSize> {
  return apiRequest('/api/admin/size-options', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateAdminSize(id: string, payload: AdminSizePayload): Promise<AdminSize> {
  return apiRequest(`/api/admin/size-options/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteAdminSize(id: string): Promise<void> {
  return apiRequest(`/api/admin/size-options/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

export function getAdminOrders(
  status: string,
  signal?: AbortSignal,
): Promise<AdminOrderPage> {
  const query = new URLSearchParams({ page: '1', page_size: '100' })
  if (status) query.set('status', status)
  return apiGet(`/api/admin/orders?${query}`, signal)
}

export function getAdminOrder(id: string, signal?: AbortSignal): Promise<AdminOrderDetail> {
  return apiGet(`/api/admin/orders/${encodeURIComponent(id)}`, signal)
}

export function updateAdminOrderStatus(
  id: string,
  action: AdminOrderAction,
): Promise<AdminOrderDetail> {
  return apiRequest(`/api/admin/orders/${encodeURIComponent(id)}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ action }),
  })
}

export function getAdminSettings(signal?: AbortSignal): Promise<AdminSettings> {
  return apiGet('/api/admin/settings', signal)
}

export function updateAdminSettings(payload: Partial<AdminSettings>): Promise<AdminSettings> {
  return apiRequest('/api/admin/settings', { method: 'PATCH', body: JSON.stringify(payload) })
}

export function createAdminDelivery(payload: AdminDeliveryPayload): Promise<AdminDelivery> {
  return apiRequest('/api/admin/settings/delivery-methods', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateAdminDelivery(
  id: string,
  payload: AdminDeliveryPayload,
): Promise<AdminDelivery> {
  return apiRequest(`/api/admin/settings/delivery-methods/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteAdminDelivery(id: string): Promise<void> {
  return apiRequest(`/api/admin/settings/delivery-methods/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
}
