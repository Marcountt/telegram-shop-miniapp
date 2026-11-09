import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { getErrorMessage } from '../../../components/catalog/QueryState'
import { Button, Card, EmptyState, Skeleton } from '../../../components/ui'
import { useCategories, useSubmitBusiness } from '../hooks'

export function AddBusinessScreen() {
  const categories = useCategories()
  const submission = useSubmitBusiness()
  const navigate = useNavigate()
  const [coordinateError, setCoordinateError] = useState('')

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setCoordinateError('')
    const formData = new FormData(event.currentTarget)
    const latitude = readCoordinate(formData.get('latitude'))
    const longitude = readCoordinate(formData.get('longitude'))
    if ((latitude === undefined) !== (longitude === undefined)) {
      setCoordinateError('Укажите обе координаты или оставьте оба поля пустыми.')
      return
    }

    const categoryId = String(formData.get('category_id') ?? '')
    const value = (key: string) => String(formData.get(key) ?? '').trim()
    submission.mutate({
      ...(categoryId ? { category_id: categoryId } : {}),
      name: value('name'),
      description: value('description') || undefined,
      address: value('address') || undefined,
      district: value('district') || undefined,
      ...(latitude !== undefined && longitude !== undefined ? { latitude, longitude } : {}),
      phone: value('phone') || undefined,
      telegram: value('telegram') || undefined,
      website: value('website') || undefined,
    })
  }

  if (submission.isSuccess) {
    return (
      <div className="screen-stack">
        <EmptyState
          title="ЗАЯВКА ОТПРАВЛЕНА"
          description="Спасибо! Место появится в каталоге после проверки модератором."
          icon={<span aria-hidden="true">✓</span>}
          action={
            <div className="form-actions">
              <Button onClick={() => navigate('/places')}>В КАТАЛОГ</Button>
              <Button onClick={() => submission.reset()} variant="text">ДОБАВИТЬ ЕЩЁ</Button>
            </div>
          }
        />
      </div>
    )
  }

  return (
    <div className="screen-stack">
      <div className="screen-title-row">
        <div>
          <p className="eyebrow">ПОМОГИТЕ СОСЕДЯМ НАЙТИ ВАС</p>
          <h1 className="screen-title">ВАШ БИЗНЕС</h1>
        </div>
        <Link className="underlined-link" to="/">НАЗАД ↗</Link>
      </div>

      <Card className="submission-intro">
        <p>Заполните карточку. Мы проверим информацию перед публикацией.</p>
        <p className="eyebrow">ЗВЁЗДОЧКОЙ ОТМЕЧЕНЫ ОБЯЗАТЕЛЬНЫЕ ПОЛЯ</p>
      </Card>

      {categories.isError && (
        <div className="inline-error" role="alert">
          <p>Категории временно недоступны: {getErrorMessage(categories.error)}</p>
          <Button onClick={() => void categories.refetch()} variant="secondary">ПОВТОРИТЬ</Button>
        </div>
      )}

      <form className="business-form" onSubmit={submit}>
        <fieldset className="business-form__fieldset" disabled={submission.isPending}>
          <label className="form-field">
            <span>НАЗВАНИЕ *</span>
            <input autoComplete="organization" maxLength={200} minLength={1} name="name" required />
          </label>

          <label className="form-field">
            <span>КАТЕГОРИЯ</span>
            {categories.isPending ? (
              <Skeleton height={48} />
            ) : (
              <select defaultValue="" name="category_id">
                <option value="">ВЫБРАТЬ КАТЕГОРИЮ</option>
                {categories.data?.map((category) => (
                  <option key={category.id} value={category.id}>{category.name}</option>
                ))}
              </select>
            )}
          </label>

          <label className="form-field">
            <span>ОПИСАНИЕ</span>
            <textarea maxLength={5000} name="description" rows={4} />
          </label>

          <div className="form-grid">
            <label className="form-field">
              <span>РАЙОН</span>
              <input autoComplete="address-level2" maxLength={120} name="district" />
            </label>
            <label className="form-field">
              <span>АДРЕС</span>
              <input autoComplete="street-address" maxLength={300} name="address" />
            </label>
          </div>

          <div className="form-grid">
            <label className="form-field">
              <span>ШИРОТА</span>
              <input max="90" min="-90" name="latitude" placeholder="53.9006" step="any" type="number" />
            </label>
            <label className="form-field">
              <span>ДОЛГОТА</span>
              <input max="180" min="-180" name="longitude" placeholder="27.5590" step="any" type="number" />
            </label>
          </div>
          {coordinateError && <p className="form-error" role="alert">{coordinateError}</p>}

          <div className="form-grid">
            <label className="form-field">
              <span>ТЕЛЕФОН</span>
              <input autoComplete="tel" maxLength={32} name="phone" type="tel" />
            </label>
            <label className="form-field">
              <span>TELEGRAM</span>
              <input autoComplete="off" maxLength={64} name="telegram" placeholder="@username" />
            </label>
          </div>

          <label className="form-field">
            <span>САЙТ</span>
            <input autoComplete="url" maxLength={2048} name="website" placeholder="https://" type="url" />
          </label>

          <p className="photo-upload-note">
            ЗАГРУЗКА ФОТОГРАФИЙ ПОКА НЕДОСТУПНА. ЕЁ ДОБАВИМ ПОСЛЕ НАСТРОЙКИ ХРАНИЛИЩА.
          </p>
        </fieldset>

        {submission.isError && (
          <p className="form-error" role="alert">{getErrorMessage(submission.error)}</p>
        )}
        <Button disabled={submission.isPending || categories.isPending} type="submit">
          {submission.isPending ? 'ОТПРАВЛЯЕМ…' : 'ОТПРАВИТЬ НА ПРОВЕРКУ'}
        </Button>
      </form>
    </div>
  )
}

function readCoordinate(value: FormDataEntryValue | null): number | undefined {
  if (typeof value !== 'string' || value.trim() === '') return undefined
  const number = Number(value)
  return Number.isFinite(number) ? number : undefined
}
