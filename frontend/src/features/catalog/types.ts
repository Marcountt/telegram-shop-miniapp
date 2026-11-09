export interface Category {
  id: string
  parent_id: string | null
  name: string
  slug: string
  description: string | null
}

export interface PlaceSummary {
  id: string
  category_id: string | null
  name: string
  address: string | null
  district: string | null
  latitude: string | number | null
  longitude: string | number | null
  photos: Array<Record<string, unknown>>
  rating_cache: string | number
  review_count: number
}

export interface WorkingInterval {
  open: string
  close: string
}

export interface Place extends PlaceSummary {
  description: string | null
  phone: string | null
  telegram: string | null
  website: string | null
  working_hours: Record<string, WorkingInterval[]> | null
  status: string
  created_at: string
  updated_at: string
  category: Category | null
}

export interface PlacePage {
  items: PlaceSummary[]
  next_cursor: string | null
}

export interface Review {
  id: string
  place_id: string
  rating: number
  comment: string | null
  created_at: string
  user_name: string | null
}

export interface ReviewPage {
  items: Review[]
  limit: number
  offset: number
}

export interface FavoritePage {
  items: PlaceSummary[]
  limit: number
  offset: number
}

export interface Submission {
  id: string
  place_id: string | null
  status: string
  created_at: string
}

export interface SubmissionInput {
  category_id?: string
  name: string
  description?: string
  address?: string
  district?: string
  latitude?: number
  longitude?: number
  phone?: string
  telegram?: string
  website?: string
}
