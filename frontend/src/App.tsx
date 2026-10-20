import { useEffect } from 'react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppRoutes } from '@/routes/AppRoutes'
import { useAuthStore } from '@/stores/authStore'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

export default function App() {
  // Restore the session from the httpOnly refresh cookie on every page load.
  useEffect(() => { void useAuthStore.getState().bootstrap() }, [])
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  )
}
