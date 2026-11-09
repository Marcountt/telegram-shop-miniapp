import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { QueryClientProvider } from '@tanstack/react-query'
import { App } from './app/App'
import { queryClient } from './lib/query-client'
import { initializeTelegram } from './telegram/initialize'
import { StoreProvider } from './app/store-context'
import './styles.css'

initializeTelegram()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <StoreProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </StoreProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
