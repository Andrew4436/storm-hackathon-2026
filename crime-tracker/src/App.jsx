import { useCallback, useEffect, useRef, useState } from 'react'
import { FIRST_MONTH, PLAY_INTERVAL_MS } from './config.js'
import { monthLabel } from './format.js'
import { AREA_BY_NAME, AREA_BY_SLUG } from './areas.js'
import { loadData } from './api.js'
import MapStage from './MapStage.jsx'
import Drawer from './Drawer.jsx'
import AreaDetail from './AreaDetail.jsx'
import HowItWorks from './HowItWorks.jsx'
import './App.css'

const NO_MONTHS = []

/**
 * ?mode=forecast|historical&month=YYYY-MM&area=slug, so a view can be bookmarked. Only the query string is read
 * and written, so the app works under a base path (GitHub Pages). The month is checked against the loaded
 * months once the data is in, because the last complete month comes from meta.json.
 */
function readUrl() {
  const p = new URLSearchParams(window.location.search)
  const m = p.get('month')
  return {
    mode: p.get('mode') === 'forecast' ? 'forecast' : 'historical',
    month: m && /^\d{4}-(0[1-9]|1[0-2])$/.test(m) && m >= FIRST_MONTH ? m : null,
    area: AREA_BY_SLUG.get(p.get('area') ?? '')?.name ?? null,
  }
}

/** The page description names the forecast month, which is only known once meta.json is in. */
function describePage(forecastMonth) {
  const label = monthLabel(forecastMonth)
  const article = /^[AEIOU]/.test(label) ? 'an' : 'a'
  document
    .querySelector('meta[name="description"]')
    ?.setAttribute(
      'content',
      `Reported incidents in Vancouver's 24 neighbourhoods, month by month, compared with each one's own past, with ${article} ${label} forecast.`,
    )
}

function useData() {
  const [state, setState] = useState({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const ctrl = new AbortController()
    loadData(ctrl.signal).then(
      (data) => setState({ status: data.months.length && data.forecastByArea.size ? 'ready' : 'empty', data }),
      (error) => {
        if (!ctrl.signal.aborted) setState({ status: 'error', error })
      },
    )
    return () => ctrl.abort()
  }, [attempt])
  const retry = useCallback(() => {
    setState({ status: 'loading' })
    setAttempt((n) => n + 1)
  }, [])
  return [state, retry]
}

function StatusPage({ title, children }) {
  return (
    <div className="status-page">
      <div className="status surface" role="status">
        <h2 className="status__title">{title}</h2>
        {children}
      </div>
    </div>
  )
}

export default function App() {
  const [initial] = useState(readUrl)
  const [mode, setMode] = useState(initial.mode)
  const [month, setMonth] = useState(initial.month)
  const [selected, setSelected] = useState(initial.area)
  const [sheet, setSheet] = useState(null) // 'about' while "How this works" is open
  const [playing, setPlaying] = useState(false)
  const [state, retry] = useData()
  const months = state.data?.months ?? NO_MONTHS
  // Once the data is in, a month from the URL that is not on the timeline (or no month) becomes the last one.
  if (months.length && !months.includes(month)) setMonth(months[months.length - 1])

  const aboutButtonRef = useRef(null)
  const areaSelectRef = useRef(null)
  const sheetHeadingRef = useRef(null)
  const monthRef = useRef(month)

  useEffect(() => {
    const p = new URLSearchParams()
    p.set('mode', mode)
    if (month) p.set('month', month)
    if (selected) p.set('area', AREA_BY_NAME.get(selected).slug)
    // Only the query changes; the path (and any base path) and the hash stay as they are.
    const url = new URL(window.location.href)
    url.search = p.toString()
    window.history.replaceState(null, '', url)
  }, [mode, month, selected])

  const forecastMonth = state.data?.meta.forecast_month
  useEffect(() => {
    if (forecastMonth) describePage(forecastMonth)
  }, [forecastMonth])

  // Playback: one month every PLAY_INTERVAL_MS through the historical range, stopping at the last month.
  useEffect(() => {
    monthRef.current = month
  }, [month])
  useEffect(() => {
    if (!playing || !months.length) return
    const id = setInterval(() => {
      const i = months.indexOf(monthRef.current)
      if (i < 0 || i >= months.length - 1) {
        setPlaying(false)
        return
      }
      monthRef.current = months[i + 1]
      setMonth(months[i + 1])
      if (i + 1 >= months.length - 1) setPlaying(false)
    }, PLAY_INTERVAL_MS)
    return () => clearInterval(id)
  }, [playing, months])

  const onSelect = useCallback((name) => {
    setSelected(name)
    if (name) setSheet(null)
  }, [])
  const onMode = useCallback((m) => {
    setMode(m)
    if (m === 'forecast') setPlaying(false)
  }, [])
  const onMonth = useCallback((m) => {
    setPlaying(false)
    setMonth(m)
  }, [])
  const onPlay = useCallback(() => {
    if (playing) {
      setPlaying(false)
      return
    }
    if (months.indexOf(month) >= months.length - 1) {
      monthRef.current = months[0]
      setMonth(months[0])
    }
    setPlaying(true)
  }, [playing, months, month])
  const onAbout = useCallback(() => setSheet((s) => (s === 'about' ? null : 'about')), [])

  const closeDrawer = useCallback(() => {
    if (sheet) {
      setSheet(null)
      aboutButtonRef.current?.focus()
    } else {
      // The drawer turns inert as it closes; if focus was inside it, hand it to the neighbourhood list.
      const active = document.activeElement
      if (!active || active === document.body || active.closest('.drawer')) areaSelectRef.current?.focus()
      setSelected(null)
    }
  }, [sheet])

  // Move focus into "How this works" when it opens; Escape closes whichever drawer is showing.
  useEffect(() => {
    if (sheet === 'about') sheetHeadingRef.current?.focus({ preventScroll: true })
  }, [sheet])
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape' && (sheet || selected)) closeDrawer()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [sheet, selected, closeDrawer])

  // Keep the last content in the drawer while it slides closed.
  const viewKey = sheet === 'about' ? 'about' : selected ? `area:${selected}` : null
  const [shownKey, setShownKey] = useState(viewKey)
  if (viewKey && viewKey !== shownKey) setShownKey(viewKey)
  const drawerOpen = viewKey !== null

  if (state.status === 'loading') {
    return (
      <StatusPage title="Loading reported-incident data">
        <p>
          Fetching monthly history from {monthLabel(FIRST_MONTH)}, the latest forecast and the neighbourhood
          boundaries.
        </p>
      </StatusPage>
    )
  }
  if (state.status === 'error') {
    return (
      <StatusPage title={state.error?.summary ?? 'The data could not be loaded.'}>
        <p>Check your connection and try again.</p>
        <p className="status__detail">{String(state.error?.message ?? state.error)}</p>
        <button type="button" className="btn btn--primary" onClick={retry}>
          Try again
        </button>
      </StatusPage>
    )
  }
  if (state.status === 'empty') {
    return (
      <StatusPage title="The data files are empty">
        <p>They loaded but contain no months or forecasts. Check the files in public/data or the API, then reload.</p>
        <button type="button" className="btn btn--primary" onClick={retry}>
          Reload
        </button>
      </StatusPage>
    )
  }

  const data = state.data
  const shownArea = shownKey?.startsWith('area:') ? shownKey.slice(5) : null

  return (
    <div className={drawerOpen ? 'app has-drawer' : 'app'}>
      <MapStage
        data={data}
        mode={mode}
        month={month}
        selected={selected}
        onSelect={onSelect}
        drawerOpen={drawerOpen}
        controls={{
          mode,
          onMode,
          month,
          onMonth,
          months,
          playing,
          onPlay,
          onAbout,
          forecastMonth: data.meta.forecast_month,
          aboutOpen: sheet === 'about',
          aboutRef: aboutButtonRef,
          selectRef: areaSelectRef,
        }}
      />
      <Drawer
        open={drawerOpen}
        label={shownKey === 'about' ? 'How this works' : 'Neighbourhood details'}
        onClose={closeDrawer}
      >
        {shownKey === 'about' && <HowItWorks meta={data.meta} headingRef={sheetHeadingRef} />}
        {shownArea && <AreaDetail data={data} mode={mode} month={month} name={shownArea} />}
      </Drawer>
    </div>
  )
}
