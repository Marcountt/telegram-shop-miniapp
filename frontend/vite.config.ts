import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    allowedHosts: ['.trycloudflare.com', '.ngrok-free.app', '.ngrok-free.dev'],
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/docs': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/openapi.json': 'http://127.0.0.1:8000',
      '/uploads': 'http://127.0.0.1:8000',
    },
  },
})
