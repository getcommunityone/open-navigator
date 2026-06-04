// Initialize OpenTelemetry browser tracing ONCE, before anything else renders.
import './instrumentation'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './contexts/AuthContext'
import { LocationProvider } from './contexts/LocationContext'
import ScrollToTop from './components/ScrollToTop'
import App from './App'
import './index.css'
import { installExtensionConsoleNoiseFilter } from './utils/filterExtensionConsoleNoise'

installExtensionConsoleNoiseFilter()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter
        future={{
          v7_startTransition: true,
          v7_relativeSplatPath: true,
        }}
      >
        <ScrollToTop />
        <AuthProvider>
          <LocationProvider>
            <App />
          </LocationProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
