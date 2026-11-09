import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { useCategories } from '../hooks'
import { Button, EmptyState, Skeleton, Tag } from '../../../components/ui'
import { QueryError } from '../../../components/catalog/QueryState'

const categorySymbols = ['⌂', '✿', '▧', '◇', '✦', '↗']

export function HomeScreen() {
  const [search, setSearch] = useState('')
  const navigate = useNavigate()
  const categories = useCategories()

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const params = new URLSearchParams()
    if (search.trim()) params.set('search', search.trim())
    const query = params.toString()
    navigate(`/places${query ? `?${query}` : ''}`)
  }

  return (
    <div className="screen-stack">
      <section className="home-hero">
        <p className="eyebrow">ВАШ ГОРОД · ВАШИ ЛЮДИ</p>
        <h1>НАЙДИТЕ<br />СВОЁ МЕСТО</h1>
        <p>Хорошие адреса начинаются здесь.</p>
      </section>

      <form className="search-bar" onSubmit={submitSearch} role="search">
        <span aria-hidden="true">⌕</span>
        <input
          aria-label="Поиск по каталогу"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Название, услуга, адрес"
          value={search}
        />
        <Button aria-label="Искать" className="search-bar__submit" type="submit">
          НАЙТИ
        </Button>
      </form>

      <section aria-labelledby="categories-title" className="screen-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">ВЫБИРАЙТЕ СВОЁ</p>
            <h2 id="categories-title">КАТЕГОРИИ</h2>
          </div>
          <Link className="underlined-link" to="/places">ВЕСЬ КАТАЛОГ ↗</Link>
        </div>

        {categories.isPending ? (
          <div className="category-grid" aria-label="Загружаем категории">
            {Array.from({ length: 6 }, (_, index) => (
              <Skeleton className="category-skeleton" height={112} key={index} />
            ))}
          </div>
        ) : categories.isError ? (
          <QueryError message={categories.error.message} onRetry={() => void categories.refetch()} />
        ) : categories.data.length === 0 ? (
          <EmptyState
            title="КАТЕГОРИЙ ПОКА НЕТ"
            description="Загляните в каталог чуть позже."
            action={<Button onClick={() => navigate('/places')}>ОТКРЫТЬ КАТАЛОГ</Button>}
          />
        ) : (
          <div className="category-grid">
            {categories.data.map((category, index) => (
              <Link
                className="category-tile"
                key={category.id}
                to={`/places?category_id=${encodeURIComponent(category.id)}`}
              >
                <span aria-hidden="true" className="category-tile__symbol">
                  {categorySymbols[index % categorySymbols.length]}
                </span>
                <span className="category-tile__name">{category.name}</span>
                {category.description && (
                  <span className="category-tile__description">{category.description}</span>
                )}
                <span aria-hidden="true" className="category-tile__arrow">↗</span>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="business-banner">
        <div>
          <Tag>ЕСТЬ СВОЁ ДЕЛО?</Tag>
          <h2>ДОБАВЬТЕ<br />СВОЙ БИЗНЕС</h2>
          <p>Расскажите о нём жителям города.</p>
        </div>
        <Button onClick={() => navigate('/add-business')} variant="secondary">
          ДОБАВИТЬ ↗
        </Button>
      </section>
    </div>
  )
}
