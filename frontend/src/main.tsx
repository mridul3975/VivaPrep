import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/geist'
import './index.css'
import AuthGate from './auth/AuthGate'
import DotPattern from './components/DotPattern'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DotPattern />
    <AuthGate />
  </StrictMode>,
)
