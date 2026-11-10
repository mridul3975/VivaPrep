import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true, // Listens on all addresses (0.0.0.0) so Windows browser can connect to WSL
    watch: { usePolling: true, interval: 300 },
    proxy: {
      '/auth': 'http://127.0.0.1:5000',
      '/retrieve': 'http://127.0.0.1:5000',
      '/sources': 'http://127.0.0.1:5000',
      '/questions': 'http://127.0.0.1:5000',
      '/answers': 'http://127.0.0.1:5000',
      '/transcriptions': 'http://127.0.0.1:5000',
      '/health': 'http://127.0.0.1:5000',
      '/history': 'http://127.0.0.1:5000',
      '/profile': 'http://127.0.0.1:5000',
      '/debug': 'http://127.0.0.1:5000',
    },
  },
})
