import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    // Same-origin /api in development, as it will be behind the ingress in production.
    proxy: { '/api': { target: process.env.VITE_API_PROXY ?? 'http://localhost:8001', changeOrigin: false } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    css: false,
    testTimeout: 15000,
  },
})
