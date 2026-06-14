import ReactDOM from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
// Self-hosted fonts (bundled) — no runtime fetch to Google, so the strict CSP
// can forbid external origins. Registers 'Geist Variable' / 'Geist Mono Variable'.
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import App from './App'
import { ThemeProvider } from './theme/ThemeContext'
import { initApiBase } from './api/client'
import './index.css'
import './theme/minimal.css'
import './theme/tokens.css'
import './ui-kit/kit.css'

// Resolve the daemon port from the Electron bridge before the first request.
void initApiBase()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,           // data stays fresh 30s — navigating back shows cached data instantly
      retry: 1,                    // retry once on failure, don't hammer a down daemon
      refetchOnWindowFocus: false, // Electron app — window focus isn't meaningful
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}>
    <HashRouter>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </HashRouter>
  </QueryClientProvider>
)
