import { useEffect, useRef, useState, type ButtonHTMLAttributes, type DragEvent, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { isTMA } from '@telegram-apps/sdk'
import { Link } from 'react-router'
import { EmptyState, Skeleton } from '../components/ui'
import { ApiError, apiGet } from '../lib/api-client'
import { useCurrency } from '../app/store-context'
import type { CustomerProfile, StoreSection } from './types'
import {
  adminKeys,
  createAdminCategory,
  createAdminDelivery,
  createAdminProduct,
  createAdminSize,
  deleteAdminCategory,
  deleteAdminDelivery,
  deleteAdminProduct,
  deleteAdminSize,
  deleteProductImage,
  getAdminCategories,
  getAdminDashboard,
  getAdminOrder,
  getAdminOrders,
  getAdminProduct,
  getAdminProducts,
  getAdminSettings,
  getAdminSizes,
  markProductSold,
  reorderProductImages,
  setProductVisibility,
  updateAdminCategory,
  updateAdminDelivery,
  updateAdminOrderStatus,
  updateAdminProduct,
  updateAdminSettings,
  updateAdminSize,
  uploadProductImages,
  type AdminCategory,
  type AdminCategoryPayload,
  type AdminDashboard,
  type AdminDeliveryPayload,
  type AdminImage,
  type AdminOrderAction,
  type AdminProduct,
  type AdminProductPayload,
  type AdminProductStatus,
  type AdminSettings,
  type AdminSize,
  type AdminSizePayload,
} from './admin-api'

type AdminTab = 'dashboard' | 'products' | 'orders' | 'categories' | 'settings'
type ProductPhoto = { key: string; src: string; image?: AdminImage; file?: File }

const tabLabels: Array<{ id: AdminTab; label: string }> = [
  { id: 'dashboard', label: 'Обзор' },
  { id: 'products', label: 'Товары' },
  { id: 'orders', label: 'Заказы' },
  { id: 'categories', label: 'Каталог' },
  { id: 'settings', label: 'Настройки' },
]

function messageOf(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return 'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.'
}

function LoadingState() {
  return (
    <div className="admin-loading" aria-busy="true">
      <Skeleton height={20} width="45%" />
      <Skeleton height={82} />
      <Skeleton height={82} />
    </div>
  )
}

function AdminNotice({ children, error = false }: { children: string; error?: boolean }) {
  return <p className={`admin-notice${error ? ' admin-notice--error' : ''}`} role={error ? 'alert' : 'status'}>{children}</p>
}

function AdminButton({
  children,
  variant = 'primary',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' }) {
  return <button className={`ui-button ui-button--${variant} admin-button`} type="button" {...props}>{children}</button>
}

function Field({
  label,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="form-field admin-field">
      <span>{label}</span>
      <input {...props} />
    </label>
  )
}

function TextAreaField({
  label,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  return (
    <label className="form-field admin-field">
      <span>{label}</span>
      <textarea {...props} />
    </label>
  )
}

function formatByn(value: number | string): string {
  return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(value))} BYN`
}

function AdminDashboardView({ data }: { data?: AdminDashboard }) {
  if (!data) return <LoadingState />
  const metrics = [
    { label: 'Новые заказы', value: data.pending_orders },
    { label: 'Заказов сегодня', value: data.today_orders },
    { label: 'Выручка сегодня', value: formatByn(data.today_revenue_byn) },
    { label: 'Заказов за неделю', value: data.week_orders },
    { label: 'Выручка за неделю', value: formatByn(data.week_revenue_byn) },
  ]
  return (
    <div className="admin-view">
      <div className="admin-metrics">
        {metrics.map((metric) => (
          <article className="admin-metric" key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
          </article>
        ))}
      </div>
      <section className="admin-section">
        <div className="admin-section__heading">
          <h2>Остался один размер</h2>
          <span>{data.one_size_left.length}</span>
        </div>
        {!data.one_size_left.length ? (
          <p className="admin-muted">Товаров с остатком в одном размере нет.</p>
        ) : data.one_size_left.map((product) => (
          <article className="admin-low-stock" key={product.id}>
            {product.image_url ? <img alt="" src={product.image_url} /> : <div className="admin-image-placeholder" />}
            <div><strong>{product.title}</strong><span>{product.category_name}</span></div>
            <b>{product.stock} шт.</b>
          </article>
        ))}
      </section>
    </div>
  )
}

function ProductForm({
  product,
  categories,
  sizes,
  rate,
  onCancel,
  onSaved,
}: {
  product: AdminProduct | null
  categories: AdminCategory[]
  sizes: AdminSize[]
  rate: number
  onCancel: () => void
  onSaved: () => void
}) {
  const queryClient = useQueryClient()
  const [step, setStep] = useState(0)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [persistedProduct, setPersistedProduct] = useState<AdminProduct | null>(null)
  const [title, setTitle] = useState(product?.title ?? '')
  const [brand, setBrand] = useState(product?.brand ?? '')
  const [description, setDescription] = useState(product?.description ?? '')
  const [section, setSection] = useState<StoreSection>(product?.section ?? 'unisex')
  const [categoryId, setCategoryId] = useState(product?.category_id ?? '')
  const [priceByn, setPriceByn] = useState(String(product?.price_byn ?? ''))
  const [oldPriceByn, setOldPriceByn] = useState(String(product?.old_price_byn ?? ''))
  const [rubMode, setRubMode] = useState<'auto' | 'manual'>('auto')
  const [priceRub, setPriceRub] = useState(String(product?.price_rub ?? ''))
  const [oldPriceRub, setOldPriceRub] = useState(String(product?.old_price_rub ?? ''))
  const [isNew, setIsNew] = useState(product?.is_new ?? false)
  const [selectedSizes, setSelectedSizes] = useState<Record<string, number>>(() =>
    Object.fromEntries(
      (product?.variants ?? [])
        .filter((variant) => variant.size)
        .map((variant) => [variant.size, variant.stock]),
    ),
  )
  const [photos, setPhotos] = useState<ProductPhoto[]>(() =>
    (product?.images ?? []).map((image) => ({
      key: image.id,
      image,
      src: image.thumbnail_url ?? image.url,
    })),
  )
  const objectUrls = useRef<string[]>([])
  let savedProduct: AdminProduct | null = null
  const selectedCategory = categories.find((category) => category.id === categoryId)
  const currentProduct = persistedProduct ?? product
  const groupSizes = sizes.filter((item) => item.group_key === (selectedCategory?.group_key ?? 'clothing') && item.is_active)
  const autoRubPrice = Number(priceByn) * rate

  useEffect(() => () => objectUrls.current.forEach((url) => URL.revokeObjectURL(url)), [])

  const movePhoto = (fromKey: string, toKey: string) => {
    setPhotos((current) => {
      const sourceIndex = current.findIndex((photo) => photo.key === fromKey)
      const targetIndex = current.findIndex((photo) => photo.key === toKey)
      if (sourceIndex < 0 || targetIndex < 0 || sourceIndex === targetIndex) return current
      const next = [...current]
      const [moved] = next.splice(sourceIndex, 1)
      next.splice(targetIndex, 0, moved)
      return next
    })
  }

  const addFiles = (files: FileList | null) => {
    if (!files) return
    const newPhotos = Array.from(files)
      .filter((file) => file.type.startsWith('image/'))
      .map((file) => {
        const src = URL.createObjectURL(file)
        objectUrls.current.push(src)
        return { key: crypto.randomUUID(), file, src }
      })
    setPhotos((current) => [...current, ...newPhotos].slice(0, 20))
  }

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    if (!categoryId) {
      setError('Выберите категорию товара.')
      setStep(1)
      return
    }
    if (!title.trim() || !Number.isFinite(Number(priceByn)) || Number(priceByn) <= 0) {
      setError('Укажите название и цену в BYN больше нуля.')
      setStep(0)
      return
    }
    if (rubMode === 'manual' && (!Number.isFinite(Number(priceRub)) || Number(priceRub) <= 0)) {
      setError('Укажите цену в RUB больше нуля.')
      setStep(1)
      return
    }
    const payload: AdminProductPayload = {
      title: title.trim(),
      brand: brand.trim() || null,
      description: description.trim() || null,
      section,
      category_id: categoryId,
      price_byn: Number(priceByn),
      rub_price_mode: rubMode,
      is_new: isNew,
      sizes: Object.entries(selectedSizes).map(([size, quantity]) => ({
        size,
        quantity,
        color: '',
      })),
    }
    if (oldPriceByn) payload.old_price_byn = Number(oldPriceByn)
    if (rubMode === 'manual') {
      payload.price_rub = Number(priceRub)
      if (oldPriceRub) payload.old_price_rub = Number(oldPriceRub)
    }
    setSaving(true)
    try {
      const saved = currentProduct
        ? await updateAdminProduct(currentProduct.id, payload)
        : await createAdminProduct(payload)
      savedProduct = saved
      if (!currentProduct) setPersistedProduct(saved)
      const remainingImages = photos.flatMap((photo) => photo.image ? [photo.image] : [])
      const remainingIds = new Set(remainingImages.map((image) => image.id))
      const removedImages = (currentProduct?.images ?? []).filter((image) => !remainingIds.has(image.id))
      for (const image of removedImages) {
        await deleteProductImage(saved.id, image.id)
      }

      const files = photos.flatMap((photo) => photo.file ? [photo.file] : [])
      let uploaded: AdminImage[] = []
      if (files.length) uploaded = await uploadProductImages(saved.id, files)
      const newImages = uploaded.slice(remainingImages.length)
      const uploadedByFile = new Map<string, AdminImage>()
      let newIndex = 0
      for (const photo of photos) {
        if (photo.file) {
          const image = newImages[newIndex]
          newIndex += 1
          if (image) uploadedByFile.set(photo.key, image)
        }
      }
      const orderedIds = photos.flatMap((photo) => {
        if (photo.image) return [photo.image.id]
        const image = uploadedByFile.get(photo.key)
        return image ? [image.id] : []
      })
      if (orderedIds.length) await reorderProductImages(saved.id, orderedIds)
      await queryClient.invalidateQueries({ queryKey: ['admin'] })
      await queryClient.invalidateQueries({ queryKey: ['store'] })
      onSaved()
    } catch (saveError) {
      let errorMessage = messageOf(saveError)
      if (savedProduct) {
        try {
          const latest = await getAdminProduct(savedProduct.id)
          setPersistedProduct(latest)
          setPhotos(latest.images.map((image) => ({
            key: image.id,
            image,
            src: image.thumbnail_url ?? image.url,
          })))
          errorMessage = `Товар сохранён, но не все фотографии обновились: ${errorMessage}. Проверьте список фото и попробуйте ещё раз.`
        } catch (refreshError) {
          errorMessage = `Данные товара сохранены, но не удалось проверить фотографии: ${messageOf(refreshError)}. Обновите список товаров перед повторной попыткой.`
        }
      }
      setError(errorMessage)
      await queryClient.invalidateQueries({ queryKey: ['admin'] })
    } finally {
      setSaving(false)
    }
  }

  const stepLabels = ['Основное', 'Размеры и цены', 'Фотографии']
  return (
    <section className="admin-editor">
      <div className="admin-section__heading">
        <button className="admin-back-button" onClick={onCancel} type="button">‹ Назад к товарам</button>
        <span>{step + 1} / {stepLabels.length}</span>
      </div>
      <h2>{currentProduct ? 'Изменить товар' : 'Новый товар'}</h2>
      <div aria-label="Шаги формы" className="admin-steps">
        {stepLabels.map((label, index) => (
          <button className={index === step ? 'is-active' : index < step ? 'is-complete' : ''} key={label} onClick={() => setStep(index)} type="button">
            <b>{index + 1}</b>{label}
          </button>
        ))}
      </div>
      <form className="admin-form" onSubmit={(event) => void save(event)}>
        {step === 0 && (
          <>
            <Field autoFocus label="Название товара" maxLength={200} onChange={(event) => setTitle(event.target.value)} required value={title} />
            <Field label="Бренд (необязательно)" maxLength={120} onChange={(event) => setBrand(event.target.value)} value={brand} />
            <TextAreaField label="Описание" onChange={(event) => setDescription(event.target.value)} rows={4} value={description} />
            <label className="form-field admin-field">
              <span>Для кого</span>
              <select onChange={(event) => setSection(event.target.value as StoreSection)} value={section}>
                <option value="women">Женское</option><option value="men">Мужское</option><option value="unisex">Унисекс</option>
              </select>
            </label>
            <label className="form-field admin-field">
              <span>Категория</span>
              <select onChange={(event) => setCategoryId(event.target.value)} required value={categoryId}>
                <option value="">Выберите категорию</option>
                {categories.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
          </>
        )}
        {step === 1 && (
          <>
            <section className="admin-section">
              <h3>Размеры и количество</h3>
              <div className="admin-size-options">
                {groupSizes.map((item) => {
                  const selected = Object.hasOwn(selectedSizes, item.value)
                  return (
                    <button
                      aria-pressed={selected}
                      className={`size-chip${selected ? ' is-selected' : ''}`}
                      key={item.id}
                      onClick={() => setSelectedSizes((current) => {
                        if (selected) {
                          const next = { ...current }
                          delete next[item.value]
                          return next
                        }
                        return { ...current, [item.value]: 1 }
                      })}
                      type="button"
                    >{item.value}</button>
                  )
                })}
              </div>
              {Object.entries(selectedSizes).map(([size, quantity]) => (
                <Field
                  key={size}
                  label={`Размер ${size} · количество`}
                  min={0}
                  onChange={(event) => setSelectedSizes((current) => ({ ...current, [size]: Number(event.target.value) }))}
                  type="number"
                  value={quantity}
                />
              ))}
            </section>
            <div className="admin-form-grid">
              <Field label="Цена BYN" min="0.01" onChange={(event) => setPriceByn(event.target.value)} required step="0.01" type="number" value={priceByn} />
              <Field label="Старая цена BYN (если скидка)" min="0.01" onChange={(event) => setOldPriceByn(event.target.value)} step="0.01" type="number" value={oldPriceByn} />
            </div>
            <label className="admin-switch">
              <input checked={rubMode === 'manual'} onChange={(event) => setRubMode(event.target.checked ? 'manual' : 'auto')} type="checkbox" />
              <span>Ввести цену в RUB вручную</span>
            </label>
            {rubMode === 'manual' ? (
              <div className="admin-form-grid">
                <Field label="Цена RUB" min="0.01" onChange={(event) => setPriceRub(event.target.value)} required step="0.01" type="number" value={priceRub} />
                {oldPriceByn && <Field label="Старая цена RUB" min="0.01" onChange={(event) => setOldPriceRub(event.target.value)} step="0.01" type="number" value={oldPriceRub} />}
              </div>
            ) : (
              <p className="admin-muted">Цена в RUB по курсу {rate}: <strong>{Number.isFinite(autoRubPrice) ? `${autoRubPrice.toFixed(2)} RUB` : 'укажите цену BYN'}</strong></p>
            )}
            <label className="admin-switch">
              <input checked={isNew} onChange={(event) => setIsNew(event.target.checked)} type="checkbox" />
              <span>Отметить товар как «Новый»</span>
            </label>
          </>
        )}
        {step === 2 && (
          <section className="admin-section">
            <h3>Фотографии</h3>
            <p className="admin-muted">Первая фотография будет обложкой. Нажмите и перетащите, чтобы изменить порядок.</p>
            <label className="ui-button ui-button--secondary admin-upload">
              Добавить фото с телефона
              <input accept="image/*" capture="environment" multiple onChange={(event) => addFiles(event.target.files)} type="file" />
            </label>
            <div className="admin-photo-grid">
              {photos.map((photo, index) => (
                <PhotoTile
                  index={index}
                  isLast={index === photos.length - 1}
                  key={photo.key}
                  onMove={(offset) => setPhotos((current) => {
                    const source = current.findIndex((item) => item.key === photo.key)
                    const target = source + offset
                    if (source < 0 || target < 0 || target >= current.length) return current
                    const next = [...current]
                    const [moved] = next.splice(source, 1)
                    next.splice(target, 0, moved)
                    return next
                  })}
                  onRemove={() => setPhotos((current) => current.filter((item) => item.key !== photo.key))}
                  onReorder={movePhoto}
                  photo={photo}
                />
              ))}
            </div>
            {photos.length === 0 && <p className="admin-muted">Можно опубликовать товар без фото и добавить их позже.</p>}
          </section>
        )}
        {error && <AdminNotice error>{error}</AdminNotice>}
        <div className="admin-form-actions">
          {step > 0 && <AdminButton onClick={() => setStep((current) => current - 1)} variant="secondary">Назад</AdminButton>}
          {step < 2 ? (
            <AdminButton key="next" onClick={() => setStep((current) => current + 1)}>Далее</AdminButton>
          ) : (
            <AdminButton disabled={saving} key="publish" type="submit">{saving ? 'Сохраняем…' : 'Опубликовать'}</AdminButton>
          )}
        </div>
      </form>
    </section>
  )
}

function PhotoTile({
  photo,
  index,
  isLast,
  onReorder,
  onMove,
  onRemove,
}: {
  photo: ProductPhoto
  index: number
  isLast: boolean
  onReorder: (from: string, to: string) => void
  onMove: (offset: number) => void
  onRemove: () => void
}) {
  const onDragStart = (event: DragEvent<HTMLDivElement>) => {
    event.dataTransfer.setData('text/plain', photo.key)
    event.dataTransfer.effectAllowed = 'move'
  }
  return (
    <div
      aria-label={`Фото ${index + 1}`}
      className="admin-photo-tile"
      draggable
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault()
        onReorder(event.dataTransfer.getData('text/plain'), photo.key)
      }}
      onDragStart={onDragStart}
      role="group"
    >
      <img alt={photo.image?.alt ?? `Фото ${index + 1}`} src={photo.src} />
      {index === 0 && <span className="admin-photo-cover">Обложка</span>}
      <span className="admin-photo-index">{index + 1}</span>
      <button
        aria-label={`Удалить фото ${index + 1}`}
        className="admin-photo-remove"
        onClick={onRemove}
        type="button"
      >×</button>
      <div className="admin-photo-reorder">
        <button aria-label={`Переместить фото ${index + 1} выше`} disabled={index === 0} onClick={() => onMove(-1)} type="button">‹</button>
        <button aria-label={`Переместить фото ${index + 1} ниже`} disabled={isLast} onClick={() => onMove(1)} type="button">›</button>
      </div>
    </div>
  )
}

function AdminProductsView({
  categories,
  sizes,
  rate,
}: {
  categories: AdminCategory[]
  sizes: AdminSize[]
  rate: number
}) {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [status, setStatus] = useState<AdminProductStatus | ''>('')
  const [editing, setEditing] = useState<AdminProduct | null>(null)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const productsQuery = useQuery({
    queryKey: adminKeys.products(search, categoryId, status),
    queryFn: ({ signal }) => getAdminProducts(search, categoryId, status, signal),
  })

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ['admin', 'products'] })
    await queryClient.invalidateQueries({ queryKey: adminKeys.dashboard })
  }
  const act = async (action: () => Promise<unknown>) => {
    setError('')
    try {
      await action()
      await refresh()
    } catch (actionError) {
      setError(messageOf(actionError))
    }
  }

  if (creating || editing) {
    return (
      <ProductForm
        categories={categories}
        onCancel={() => { setCreating(false); setEditing(null) }}
        onSaved={() => { setCreating(false); setEditing(null); void refresh() }}
        product={editing}
        rate={rate}
        sizes={sizes}
      />
    )
  }

  return (
    <div className="admin-view">
      <div className="admin-view__toolbar">
        <h2>Товары</h2>
        <AdminButton onClick={() => setCreating(true)}>+ Добавить товар</AdminButton>
      </div>
      <div className="admin-filters">
        <Field aria-label="Поиск товара" label="Поиск" onChange={(event) => setSearch(event.target.value)} placeholder="Название или бренд" value={search} />
        <label className="form-field admin-field">
          <span>Категория</span>
          <select onChange={(event) => setCategoryId(event.target.value)} value={categoryId}>
            <option value="">Все категории</option>
            {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
        </label>
        <label className="form-field admin-field">
          <span>Состояние</span>
          <select onChange={(event) => setStatus(event.target.value as AdminProductStatus | '')} value={status}>
            <option value="">Все товары</option><option value="active">Опубликованные</option><option value="hidden">Скрытые</option><option value="sold">Проданные</option>
          </select>
        </label>
      </div>
      {error && <AdminNotice error>{error}</AdminNotice>}
      {productsQuery.isLoading && <LoadingState />}
      {productsQuery.isError && <AdminNotice error>{messageOf(productsQuery.error)}</AdminNotice>}
      {!productsQuery.isLoading && !productsQuery.isError && !productsQuery.data?.items.length && (
        <EmptyState title="ТОВАРЫ НЕ НАЙДЕНЫ" description="Измените фильтры или добавьте первый товар." />
      )}
      <div className="admin-product-list">
        {productsQuery.data?.items.map((product) => (
          <article className="admin-product" key={product.id}>
            {product.images[0]?.thumbnail_url || product.images[0]?.url
              ? <img alt="" src={product.images[0].thumbnail_url ?? product.images[0].url} />
              : <div className="admin-image-placeholder" />}
            <div className="admin-product__body">
              <div className="admin-product__heading">
                <strong>{product.title}</strong>
                <span className={`admin-status${product.sold_at ? ' is-sold' : product.is_active ? ' is-active' : ''}`}>
                  {product.sold_at ? 'Продан' : product.is_active ? 'Опубликован' : 'Скрыт'}
                </span>
              </div>
              <span>{product.brand || product.category_name}</span>
              <div className="admin-product__meta">
                <b>{formatByn(product.price_byn)}</b>
                <span>{product.variants.reduce((total, variant) => total + variant.stock, 0)} шт. · {product.variants.length} размеров</span>
              </div>
              <div className="admin-product__actions">
                <AdminButton onClick={() => setEditing(product)} variant="secondary">Изменить</AdminButton>
                <AdminButton onClick={() => void act(() => setProductVisibility(product.id, !product.is_active))} variant="secondary">
                  {product.is_active ? 'Скрыть' : 'Показать'}
                </AdminButton>
                {!product.sold_at && (
                  <AdminButton
                    onClick={() => {
                      if (window.confirm(`Отметить «${product.title}» как проданный? Остатки всех размеров обнулятся.`)) {
                        void act(() => markProductSold(product.id))
                      }
                    }}
                    variant="secondary"
                  >Продан</AdminButton>
                )}
                <AdminButton
                  onClick={() => {
                    if (window.confirm(`Удалить товар «${product.title}» без возможности восстановления?`)) {
                      void act(() => deleteAdminProduct(product.id))
                    }
                  }}
                  variant="danger"
                >Удалить</AdminButton>
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}

const orderStatuses = [
  { value: '', label: 'Все' },
  { value: 'pending', label: 'Новые' },
  { value: 'processing', label: 'Подтверждённые' },
  { value: 'shipped', label: 'Отправленные' },
  { value: 'completed', label: 'Доставленные' },
  { value: 'cancelled', label: 'Отменённые' },
]

const orderStatusName: Record<string, string> = {
  pending: 'Новый',
  processing: 'Подтверждён',
  shipped: 'Отправлен',
  completed: 'Доставлен',
  cancelled: 'Отменён',
}

function AdminOrdersView() {
  const queryClient = useQueryClient()
  const [status, setStatus] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [error, setError] = useState('')
  const ordersQuery = useQuery({
    queryKey: adminKeys.orders(status),
    queryFn: ({ signal }) => getAdminOrders(status, signal),
  })
  const detailQuery = useQuery({
    queryKey: adminKeys.order(selectedId),
    queryFn: ({ signal }) => getAdminOrder(selectedId, signal),
    enabled: Boolean(selectedId),
  })
  const setOrderStatus = async (action: AdminOrderAction) => {
    setError('')
    try {
      await updateAdminOrderStatus(selectedId, action)
      await queryClient.invalidateQueries({ queryKey: ['admin', 'orders'] })
      await queryClient.invalidateQueries({ queryKey: adminKeys.order(selectedId) })
      await queryClient.invalidateQueries({ queryKey: adminKeys.dashboard })
    } catch (statusError) {
      setError(messageOf(statusError))
    }
  }

  if (selectedId) {
    const detail = detailQuery.data
    return (
      <section className="admin-view">
        <button className="admin-back-button" onClick={() => setSelectedId('')} type="button">‹ К списку заказов</button>
        {detailQuery.isLoading && <LoadingState />}
        {detailQuery.isError && <AdminNotice error>{messageOf(detailQuery.error)}</AdminNotice>}
        {detail && (
          <article className="admin-order-detail">
            <div className="admin-section__heading">
              <h2>Заказ №{detail.order.id.slice(0, 8).toUpperCase()}</h2>
              <span className={`admin-status is-${detail.order.status}`}>{orderStatusName[detail.order.status] ?? detail.order.status}</span>
            </div>
            <section className="admin-section">
              <h3>Покупатель</h3>
              <p>{detail.order.recipient_name}</p>
              <a href={`tel:${detail.order.phone}`}>{detail.order.phone}</a>
              <a href={detail.customer_username ? `https://t.me/${detail.customer_username}` : `tg://user?id=${detail.customer_telegram_id}`} rel="noreferrer" target="_blank">
                {detail.customer_username ? `Открыть Telegram @${detail.customer_username}` : 'Открыть профиль покупателя в Telegram'}
              </a>
            </section>
            <section className="admin-section">
              <h3>Состав заказа</h3>
              {detail.order.items.map((item, index) => (
                <div className="admin-order-item" key={`${item.product_name}-${index}`}>
                  <span>{item.product_name} · {item.size || 'Без размера'} × {item.quantity}</span>
                  <b>{new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(item.line_total))} {detail.order.currency}</b>
                </div>
              ))}
              <div className="admin-order-total"><span>Итого ({detail.order.currency})</span><strong>{new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(Number(detail.order.total))} {detail.order.currency}</strong></div>
            </section>
            <section className="admin-section">
              <h3>Доставка</h3>
              <p>{detail.order.delivery_method_name} · {detail.order.city}</p>
              <p>{detail.order.delivery_address}</p>
              {detail.order.comment && <p>Комментарий: {detail.order.comment}</p>}
            </section>
            {error && <AdminNotice error>{error}</AdminNotice>}
            <div className="admin-order-actions">
              {detail.order.status === 'pending' && <AdminButton onClick={() => void setOrderStatus('confirm')}>Подтвердить</AdminButton>}
              {detail.order.status === 'processing' && <AdminButton onClick={() => void setOrderStatus('shipped')}>Отметить отправленным</AdminButton>}
              {detail.order.status === 'shipped' && <AdminButton onClick={() => void setOrderStatus('delivered')}>Отметить доставленным</AdminButton>}
              {['pending', 'processing'].includes(detail.order.status) && <AdminButton onClick={() => void setOrderStatus('cancel')} variant="danger">Отменить заказ</AdminButton>}
            </div>
          </article>
        )}
      </section>
    )
  }

  return (
    <div className="admin-view">
      <h2>Заказы</h2>
      <div className="admin-filter-chips">
        {orderStatuses.map((item) => (
          <button className={status === item.value ? 'is-selected' : ''} key={item.value} onClick={() => setStatus(item.value)} type="button">{item.label}</button>
        ))}
      </div>
      {ordersQuery.isLoading && <LoadingState />}
      {ordersQuery.isError && <AdminNotice error>{messageOf(ordersQuery.error)}</AdminNotice>}
      {!ordersQuery.isLoading && !ordersQuery.isError && !ordersQuery.data?.items.length && <EmptyState title="ЗАКАЗОВ НЕТ" />}
      <div className="admin-order-list">
        {ordersQuery.data?.items.map(({ order, customer_username, customer_telegram_id }) => (
          <button className="admin-order" key={order.id} onClick={() => setSelectedId(order.id)} type="button">
            <span className="admin-order__top"><strong>№{order.id.slice(0, 8).toUpperCase()}</strong><b>{orderStatusName[order.status] ?? order.status}</b></span>
            <span>{order.recipient_name} · {customer_username ? `@${customer_username}` : order.phone}</span>
            <span className="admin-order__bottom">{new Date(order.created_at).toLocaleString('ru-RU')} · {new Intl.NumberFormat('ru-RU').format(Number(order.total))} {order.currency}</span>
            <span className="sr-only">Telegram ID {customer_telegram_id}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

  function AdminCatalogView({
    categories,
    sizes,
  }: {
    categories: AdminCategory[]
    sizes: AdminSize[]
  }) {
    const queryClient = useQueryClient()
    const [categoryEdit, setCategoryEdit] = useState<AdminCategory | null>(null)
    const [categoryName, setCategoryName] = useState('')
    const [categorySlug, setCategorySlug] = useState('')
    const [categoryGroup, setCategoryGroup] = useState<'clothing' | 'shoes'>('clothing')
    const [sizeEdit, setSizeEdit] = useState<AdminSize | null>(null)
    const [sizeValue, setSizeValue] = useState('')
    const [sizeGroup, setSizeGroup] = useState<'clothing' | 'shoes'>('clothing')
    const [error, setError] = useState('')
    const [notice, setNotice] = useState('')

    const saveCategory = async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      setError('')
      setNotice('')
      const payload: AdminCategoryPayload = {
        name: categoryName.trim(),
        slug: categorySlug.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
        description: categoryEdit?.description ?? null,
        group_key: categoryGroup,
        is_active: categoryEdit?.is_active ?? true,
      }
      try {
        if (categoryEdit) await updateAdminCategory(categoryEdit.id, payload)
        else await createAdminCategory(payload)
        setCategoryEdit(null)
        setCategoryName('')
        setCategorySlug('')
        setNotice('Категория сохранена.')
        await queryClient.invalidateQueries({ queryKey: adminKeys.categories })
        await queryClient.invalidateQueries({ queryKey: ['store', 'categories'] })
      } catch (saveError) {
        setError(messageOf(saveError))
      }
    }

    const saveSize = async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      setError('')
      setNotice('')
      const payload: AdminSizePayload = {
        group_key: sizeGroup,
        value: sizeValue.trim(),
        is_active: sizeEdit?.is_active ?? true,
        sort_order: sizeEdit?.sort_order ?? sizes.filter((item) => item.group_key === sizeGroup).length + 1,
      }
      try {
        if (sizeEdit) await updateAdminSize(sizeEdit.id, payload)
        else await createAdminSize(payload)
        setSizeEdit(null)
        setSizeValue('')
        setNotice('Размер сохранён.')
        await queryClient.invalidateQueries({ queryKey: adminKeys.sizes })
        await queryClient.invalidateQueries({ queryKey: ['store', 'sizes'] })
      } catch (saveError) {
        setError(messageOf(saveError))
      }
    }

    return (
      <div className="admin-view">
        <h2>Категории и размеры</h2>
        {(error || notice) && <AdminNotice error={Boolean(error)}>{error || notice}</AdminNotice>}
        <section className="admin-section">
          <h3>{categoryEdit ? 'Изменить категорию' : 'Добавить категорию'}</h3>
          <form className="admin-form" onSubmit={(event) => void saveCategory(event)}>
            <Field label="Название категории" onChange={(event) => setCategoryName(event.target.value)} required value={categoryName} />
            <Field label="Короткое имя для ссылки (латиницей)" onChange={(event) => setCategorySlug(event.target.value)} required value={categorySlug} />
            <label className="form-field admin-field">
              <span>Группа</span>
              <select onChange={(event) => setCategoryGroup(event.target.value as 'clothing' | 'shoes')} value={categoryGroup}>
                <option value="clothing">Одежда и аксессуары</option><option value="shoes">Обувь</option>
              </select>
            </label>
            <div className="admin-form-actions">
              <AdminButton type="submit">{categoryEdit ? 'Сохранить категорию' : 'Добавить категорию'}</AdminButton>
              {categoryEdit && <AdminButton onClick={() => { setCategoryEdit(null); setCategoryName(''); setCategorySlug('') }} variant="secondary">Отмена</AdminButton>}
            </div>
          </form>
          <div className="admin-manage-list">
            {categories.map((category) => (
              <article className="admin-manage-row" key={category.id}>
                <div><strong>{category.name}</strong><span>{category.group_key === 'shoes' ? 'Обувь' : 'Одежда'} · {category.is_active ? 'активна' : 'скрыта'}</span></div>
                <AdminButton
                  onClick={() => {
                    setCategoryEdit(category)
                    setCategoryName(category.name)
                    setCategorySlug(category.slug)
                    setCategoryGroup(category.group_key)
                  }}
                  variant="secondary"
                >Изменить</AdminButton>
                <AdminButton
                  onClick={async () => {
                    try {
                      if (category.is_active) {
                        await updateAdminCategory(category.id, {
                          name: category.name,
                          slug: category.slug,
                          description: category.description,
                          group_key: category.group_key,
                          is_active: false,
                        })
                      } else {
                        await deleteAdminCategory(category.id)
                      }
                      await queryClient.invalidateQueries({ queryKey: adminKeys.categories })
                      setNotice(category.is_active ? 'Категория скрыта.' : 'Категория удалена.')
                      setError('')
                    } catch (actionError) {
                      setError(messageOf(actionError))
                    }
                  }}
                  variant="danger"
                >{category.is_active ? 'Скрыть' : 'Удалить'}</AdminButton>
              </article>
            ))}
          </div>
        </section>

        <section className="admin-section">
          <h3>{sizeEdit ? 'Изменить размер' : 'Добавить размер'}</h3>
          <form className="admin-form" onSubmit={(event) => void saveSize(event)}>
            <label className="form-field admin-field">
              <span>Для какой группы</span>
              <select onChange={(event) => setSizeGroup(event.target.value as 'clothing' | 'shoes')} value={sizeGroup}>
                <option value="clothing">Одежда</option><option value="shoes">Обувь</option>
              </select>
            </label>
            <Field label="Размер (например M или 42)" onChange={(event) => setSizeValue(event.target.value)} required value={sizeValue} />
            <div className="admin-form-actions">
              <AdminButton type="submit">{sizeEdit ? 'Сохранить размер' : 'Добавить размер'}</AdminButton>
              {sizeEdit && <AdminButton onClick={() => { setSizeEdit(null); setSizeValue('') }} variant="secondary">Отмена</AdminButton>}
            </div>
          </form>
          <div className="admin-manage-list">
            {sizes.map((size) => (
              <article className="admin-manage-row" key={size.id}>
                <div><strong>{size.value}</strong><span>{size.group_key === 'shoes' ? 'Обувь' : 'Одежда'} · {size.is_active ? 'активен' : 'скрыт'}</span></div>
                <AdminButton onClick={() => { setSizeEdit(size); setSizeValue(size.value); setSizeGroup(size.group_key) }} variant="secondary">Изменить</AdminButton>
                <AdminButton
                  onClick={async () => {
                    try {
                      if (size.is_active) {
                        await updateAdminSize(size.id, { ...size, is_active: false })
                      } else {
                        await deleteAdminSize(size.id)
                      }
                      await queryClient.invalidateQueries({ queryKey: adminKeys.sizes })
                      setNotice(size.is_active ? 'Размер скрыт.' : 'Размер удалён.')
                      setError('')
                    } catch (actionError) {
                      setError(messageOf(actionError))
                    }
                  }}
                  variant="danger"
                >{size.is_active ? 'Скрыть' : 'Удалить'}</AdminButton>
              </article>
            ))}
          </div>
        </section>
      </div>
    )
  }

  function AdminSettingsView({ settings }: { settings?: AdminSettings }) {
    const queryClient = useQueryClient()
    const [error, setError] = useState('')
    const [notice, setNotice] = useState('')
    const [saving, setSaving] = useState(false)
    const [deliveries, setDeliveries] = useState<Array<AdminDeliveryPayload & { originalId?: string }>>([])
    const [settingsReady, setSettingsReady] = useState(false)

    useEffect(() => {
      if (settings && !settingsReady) {
        setDeliveries(settings.deliveries.map((method) => ({
          originalId: method.id,
          code: method.code,
          name: method.name,
          price_byn: method.price_byn == null ? null : Number(method.price_byn),
          price_note: method.price_note,
          is_active: method.is_active,
          sort_order: method.sort_order,
        })))
        setSettingsReady(true)
      }
    }, [settings, settingsReady])

    if (!settings) return <LoadingState />

    const saveSettings = async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      setSaving(true)
      setError('')
      setNotice('')
      const form = new FormData(event.currentTarget)
      try {
        await updateAdminSettings({
          manager_username: String(form.get('manager_username') ?? '').trim(),
          reviews_url: String(form.get('reviews_url') ?? '').trim(),
          store_name: String(form.get('store_name') ?? '').trim(),
          welcome_text: String(form.get('welcome_text') ?? '').trim(),
          delivery_info_text: String(form.get('delivery_info_text') ?? '').trim(),
          byn_to_rub_rate: Number(form.get('byn_to_rub_rate')),
        })
        setNotice('Настройки магазина сохранены.')
        await queryClient.invalidateQueries({ queryKey: adminKeys.settings })
        await queryClient.invalidateQueries({ queryKey: ['store', 'settings'] })
      } catch (saveError) {
        setError(messageOf(saveError))
      } finally {
        setSaving(false)
      }
    }

    const saveDelivery = async (index: number) => {
      const method = deliveries[index]
      if (!method) return
      setError('')
      setNotice('')
      if (!method.name.trim()) {
        setError('Укажите название способа доставки.')
        return
      }
      if (!/^[a-z0-9_-]{1,40}$/.test(method.code.trim())) {
        setError('Код доставки: только латинские буквы в нижнем регистре, цифры, дефис или подчёркивание.')
        return
      }
      if (method.price_byn !== null && (!Number.isFinite(method.price_byn) || method.price_byn < 0)) {
        setError('Цена доставки должна быть неотрицательным числом.')
        return
      }
      const payload: AdminDeliveryPayload = {
        code: method.code.trim(),
        name: method.name.trim(),
        price_byn: method.price_byn,
        price_note: method.price_note?.trim() || null,
        is_active: method.is_active,
        sort_order: method.sort_order,
      }
      if (payload.price_byn === null && !payload.price_note) {
        setError('Укажите цену или примечание «по договорённости».')
        return
      }
      try {
        if (method.originalId) await updateAdminDelivery(method.originalId, payload)
        else await createAdminDelivery(payload)
        setNotice('Способ доставки сохранён.')
        await queryClient.invalidateQueries({ queryKey: adminKeys.settings })
        await queryClient.invalidateQueries({ queryKey: ['store', 'settings'] })
      } catch (saveError) {
        setError(messageOf(saveError))
      }
    }

    return (
      <div className="admin-view">
        <h2>Настройки магазина</h2>
        {(error || notice) && <AdminNotice error={Boolean(error)}>{error || notice}</AdminNotice>}
        <form className="admin-form admin-section" onSubmit={(event) => void saveSettings(event)}>
          <h3>Магазин и сообщения</h3>
          <Field defaultValue={settings.store_name} label="Название магазина" name="store_name" required />
          <Field defaultValue={settings.manager_username} label="Username менеджера в Telegram" name="manager_username" required />
          <Field defaultValue={settings.reviews_url} label="Ссылка на отзывы" name="reviews_url" required type="url" />
          <Field defaultValue={String(settings.byn_to_rub_rate)} label="Курс: 1 BYN = RUB" min="0.01" name="byn_to_rub_rate" required step="0.01" type="number" />
          <TextAreaField defaultValue={settings.welcome_text} label="Приветствие покупателям" name="welcome_text" required rows={4} />
          <TextAreaField defaultValue={settings.delivery_info_text} label="Информация о доставке" name="delivery_info_text" required rows={4} />
          <AdminButton disabled={saving} type="submit">{saving ? 'Сохраняем…' : 'Сохранить настройки'}</AdminButton>
        </form>
        <section className="admin-section">
          <div className="admin-section__heading"><h3>Способы доставки</h3><AdminButton onClick={() => setDeliveries((current) => [...current, { code: `delivery-${Date.now()}`, name: '', price_byn: null, price_note: 'по договорённости', is_active: true, sort_order: current.length + 1 }])} variant="secondary">+ Добавить</AdminButton></div>
          {deliveries.map((method, index) => {
            return (
              <article className="admin-delivery-card" key={`${method.code}-${index}`}>
                <div className="admin-form-grid">
                  <Field label="Название" onChange={(event) => setDeliveries((list) => list.map((item, i) => i === index ? { ...item, name: event.target.value } : item))} value={method.name} />
                  <Field label="Код (латиницей)" onChange={(event) => setDeliveries((list) => list.map((item, i) => i === index ? { ...item, code: event.target.value } : item))} value={method.code} />
                </div>
                <div className="admin-form-grid">
                  <Field label="Цена BYN (пусто, если по договорённости)" min="0" onChange={(event) => setDeliveries((list) => list.map((item, i) => i === index ? { ...item, price_byn: event.target.value ? Number(event.target.value) : null, price_note: event.target.value ? null : item.price_note || 'по договорённости' } : item))} step="0.01" type="number" value={method.price_byn ?? ''} />
                  <Field label="Примечание к цене" onChange={(event) => setDeliveries((list) => list.map((item, i) => i === index ? { ...item, price_note: event.target.value || null } : item))} value={method.price_note ?? ''} />
                </div>
                <label className="admin-switch"><input checked={method.is_active} onChange={(event) => setDeliveries((list) => list.map((item, i) => i === index ? { ...item, is_active: event.target.checked } : item))} type="checkbox" /><span>Показывать покупателям</span></label>
                <div className="admin-form-actions">
                  <AdminButton onClick={() => void saveDelivery(index)}>Сохранить</AdminButton>
                  <AdminButton
                    onClick={async () => {
                      try {
                        if (method.originalId) await deleteAdminDelivery(method.originalId)
                        setDeliveries((list) => list.filter((_, i) => i !== index))
                        await queryClient.invalidateQueries({ queryKey: adminKeys.settings })
                        setNotice('Способ доставки удалён.')
                        setError('')
                      } catch (deleteError) {
                        setError(messageOf(deleteError))
                      }
                    }}
                    variant="danger"
                  >Удалить</AdminButton>
                </div>
              </article>
            )
          })}
        </section>
      </div>
    )
  }

  export function AdminPanel() {
    const [tab, setTab] = useState<AdminTab>('dashboard')
    const { currency } = useCurrency()
    const profileQuery = useQuery({
      queryKey: ['store', 'profile'],
      queryFn: ({ signal }) => apiGet<CustomerProfile>('/api/me', signal),
      enabled: isTMA(),
    })
    const isAdmin = profileQuery.data?.is_admin === true
    const categoriesQuery = useQuery({
      queryKey: adminKeys.categories,
      queryFn: ({ signal }) => getAdminCategories(signal),
      enabled: isAdmin && ['products', 'categories'].includes(tab),
    })
    const sizesQuery = useQuery({
      queryKey: adminKeys.sizes,
      queryFn: ({ signal }) => getAdminSizes(signal),
      enabled: isAdmin && ['products', 'categories'].includes(tab),
    })
    const settingsQuery = useQuery({
      queryKey: adminKeys.settings,
      queryFn: ({ signal }) => getAdminSettings(signal),
      enabled: isAdmin && ['dashboard', 'products', 'settings'].includes(tab),
    })
    const dashboardQuery = useQuery({
      queryKey: adminKeys.dashboard,
      queryFn: ({ signal }) => getAdminDashboard(signal),
      enabled: isAdmin && tab === 'dashboard',
    })

    if (!isTMA()) {
      return (
        <section className="admin-denied">
          <EmptyState title="ОТКРОЙТЕ В TELEGRAM" description="Панель управления доступна только администраторам Mini App." />
          <Link className="ui-button ui-button--secondary" to="/shop/profile">Назад в магазин</Link>
        </section>
      )
    }
    if (profileQuery.isLoading) return <LoadingState />
    if (profileQuery.isError) {
      return (
        <section className="admin-denied">
          <AdminNotice error>{messageOf(profileQuery.error)}</AdminNotice>
          <Link className="ui-button ui-button--secondary" to="/shop/profile">Назад в магазин</Link>
        </section>
      )
    }
    if (!isAdmin) {
      return (
        <section className="admin-denied">
          <EmptyState title="НЕТ ДОСТУПА" description="Панель управления доступна только владельцу магазина." />
          <Link className="ui-button ui-button--secondary" to="/shop/profile">Назад в магазин</Link>
        </section>
      )
    }

    const categories = categoriesQuery.data ?? []
    const sizes = sizesQuery.data ?? []
    return (
      <section className="admin-panel">
        <header className="admin-header">
          <div>
            <p className="eyebrow">DEMO STORE · {currency}</p>
            <h1>Панель управления</h1>
          </div>
          <Link aria-label="Вернуться в магазин" className="admin-close" to="/shop/profile">×</Link>
        </header>
        <nav aria-label="Разделы панели" className="admin-tabs">
          {tabLabels.map((item) => (
            <button
              aria-current={tab === item.id ? 'page' : undefined}
              className={tab === item.id ? 'is-active' : ''}
              key={item.id}
              onClick={() => setTab(item.id)}
              type="button"
            >
              {item.label}
              {item.id === 'dashboard' && dashboardQuery.data?.pending_orders ? <span>{dashboardQuery.data.pending_orders}</span> : null}
            </button>
          ))}
        </nav>
        <main className="admin-main">
          {tab === 'dashboard' && (
            dashboardQuery.isError
              ? <AdminNotice error>{messageOf(dashboardQuery.error)}</AdminNotice>
              : <AdminDashboardView data={dashboardQuery.data} />
          )}
          {tab === 'products' && (
            categoriesQuery.isError || sizesQuery.isError
              ? <AdminNotice error>{messageOf(categoriesQuery.error ?? sizesQuery.error)}</AdminNotice>
              : categoriesQuery.isLoading || sizesQuery.isLoading
                ? <LoadingState />
                : <AdminProductsView categories={categories} sizes={sizes} rate={Number(settingsQuery.data?.byn_to_rub_rate ?? 30)} />
          )}
          {tab === 'orders' && <AdminOrdersView />}
          {tab === 'categories' && (
            categoriesQuery.isError || sizesQuery.isError
              ? <AdminNotice error>{messageOf(categoriesQuery.error ?? sizesQuery.error)}</AdminNotice>
              : <AdminCatalogView categories={categories} sizes={sizes} />
          )}
          {tab === 'settings' && (
            settingsQuery.isError
              ? <AdminNotice error>{messageOf(settingsQuery.error)}</AdminNotice>
              : <AdminSettingsView settings={settingsQuery.data} />
          )}
        </main>
      </section>
    )
  }
