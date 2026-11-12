import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/geist'
import './index.css'
import AuthGate from './auth/AuthGate'
import UiloraEffect from './components/UiloraEffect'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <UiloraEffect variant="raster" />
    <AuthGate />
  </StrictMode>,
)
