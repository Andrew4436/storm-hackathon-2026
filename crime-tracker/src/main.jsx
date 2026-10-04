import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import ErrorBoundary from './ErrorBoundary.jsx'
import { APP_NAME, FORECAST_MONTH } from './config.js'
import { monthLabel } from './format.js'

document.title = APP_NAME
const forecastLabel = monthLabel(FORECAST_MONTH)
const article = /^[AEIOU]/.test(forecastLabel) ? 'an' : 'a'
document
  .querySelector('meta[name="description"]')
  ?.setAttribute(
    'content',
    `Reported incidents in Vancouver's 24 neighbourhoods, month by month, compared with each one's own past, with ${article} ${forecastLabel} forecast.`,
  )

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
