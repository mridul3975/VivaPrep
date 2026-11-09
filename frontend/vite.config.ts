import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true, // Listens on all addresses (0.0.0.0) so Windows browser can connect to WSL
    proxy: {
      '/questions': 'http://127.0.0.1:5000',
      '/answers':   'http://127.0.0.1:5000',
      '/transcriptions': 'http://127.0.0.1:5000',
      '/health':    'http://127.0.0.1:5000',
    },
  },
})
