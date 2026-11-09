import { Button, EmptyState } from '../ui'

interface QueryErrorProps {
  message: string
  onRetry: () => void
}

export function QueryError({ message, onRetry }: QueryErrorProps) {
  return (
    <EmptyState
      title="НЕ УДАЛОСЬ ЗАГРУЗИТЬ"
      description={message}
      action={
        <Button onClick={onRetry} variant="secondary">
          ПОВТОРИТЬ
        </Button>
      }
    />
  )
}

export function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Произошла неизвестная ошибка.'
}
