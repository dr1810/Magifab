import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { AccessibilityProvider } from './accessibility-context'
import './index.css'

createRoot(document.getElementById('app')!).render(
  <StrictMode><AccessibilityProvider><App /></AccessibilityProvider></StrictMode>,
)
