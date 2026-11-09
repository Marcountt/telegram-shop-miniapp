import { apiGet, apiRequest } from '../../lib/api-client'
import type {
  Category,
  FavoritePage,
  Place,
  PlacePage,
  ReviewPage,
  Submission,
  SubmissionInput,
} from './types'

export interface PlaceFilters {
  search?: string
  categoryId?: string
  district?: string
  minRating?: number
  openNow?: boolean
  sort?: 'newest' | 'rating' | 'name'
}

export async function getCategories(signal?: AbortSignal): Promise<Category[]> {
  return apiGet<Category[]>('/api/categories', signal)
}

export async function getPlaces(
  filters: PlaceFilters,
  cursor?: string,
  signal?: AbortSignal,
): Promise<PlacePage> {
  const params = new URLSearchParams()
  if (filters.search?.trim()) params.set('search', filters.search.trim())
  if (filters.categoryId) params.set('category_id', filters.categoryId)
  if (filters.district?.trim()) params.set('district', filters.district.trim())
  if (filters.minRating !== undefined && filters.minRating > 0) {
    params.set('min_rating', String(filters.minRating))
  }
  if (filters.openNow) params.set('open_now', 'true')
  if (filters.sort) params.set('sort', filters.sort)
  if (cursor) params.set('cursor', cursor)
  params.set('limit', '20')
  return apiGet<PlacePage>(`/api/places?${params.toString()}`, signal)
}

export async function getPlace(id: string, signal?: AbortSignal): Promise<Place> {
  return apiGet<Place>(`/api/places/${encodeURIComponent(id)}`, signal)
}

export async function getFavorites(
  offset: number,
  signal?: AbortSignal,
): Promise<FavoritePage> {
  return apiGet<FavoritePage>(`/api/favorites?limit=20&offset=${offset}`, signal)
}

export async function getFavoriteStatus(
  placeId: string,
  signal?: AbortSignal,
): Promise<boolean> {
  const limit = 100
  let offset = 0

  while (true) {
    const page = await apiGet<FavoritePage>(
      `/api/favorites?limit=${limit}&offset=${offset}`,
      signal,
    )
    if (page.items.some((place) => place.id === placeId)) return true
    if (page.items.length < limit) return false
    offset += limit
  }
}

export async function addFavorite(placeId: string): Promise<void> {
  await apiRequest(`/api/favorites/${encodeURIComponent(placeId)}`, {
    method: 'PUT',
  })
}

export async function removeFavorite(placeId: string): Promise<void> {
  await apiRequest(`/api/favorites/${encodeURIComponent(placeId)}`, {
    method: 'DELETE',
  })
}

export async function getReviews(
  placeId: string,
  offset: number,
  signal?: AbortSignal,
): Promise<ReviewPage> {
  return apiGet<ReviewPage>(
    `/api/places/${encodeURIComponent(placeId)}/reviews?limit=20&offset=${offset}`,
    signal,
  )
}

export async function addReview(
  placeId: string,
  rating: number,
  comment: string,
): Promise<void> {
  await apiRequest(`/api/places/${encodeURIComponent(placeId)}/reviews`, {
    method: 'POST',
    body: JSON.stringify({ rating, comment: comment || null }),
  })
}

export async function submitBusiness(
  submission: SubmissionInput,
): Promise<Submission> {
  return apiRequest<Submission>('/api/submissions', {
    method: 'POST',
    body: JSON.stringify(submission),
  })
}
