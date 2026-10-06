import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,
    host: true, // allow Docker to bind on 0.0.0.0
  },

  test: {
    // Vitest configuration – co-located here to avoid a separate vitest.config.js
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.js'],
    css: true,
  },
})
