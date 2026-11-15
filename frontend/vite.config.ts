import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    // Same-origin /api in development, as it will be behind the ingress in production.
    // Until the API gateway exists (Phase 13/14), route each service's paths to its local port. Most specific first.
    proxy: {
      '/api/v1/rfqs': { target: process.env.VITE_QUOTATION_PROXY ?? 'http://localhost:8005', changeOrigin: false },
      '/api/v1/quotations': { target: process.env.VITE_QUOTATION_PROXY ?? 'http://localhost:8005', changeOrigin: false },
      '/api/v1/vendors': { target: process.env.VITE_VENDOR_PROXY ?? 'http://localhost:8004', changeOrigin: false },
      '/api/v1/approvals': { target: process.env.VITE_APPROVAL_PROXY ?? 'http://localhost:8003', changeOrigin: false },
      '/api/v1/purchase-requests': { target: process.env.VITE_PR_PROXY ?? 'http://localhost:8002', changeOrigin: false },
      '/api': { target: process.env.VITE_API_PROXY ?? 'http://localhost:8001', changeOrigin: false },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    css: false,
    testTimeout: 15000,
  },
})
