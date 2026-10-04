import { useCallback, useEffect, useRef, useState } from 'react'
import { APP_NAME, DATA_NOTE, DATA_THROUGH, FIRST_MONTH, TAGLINE, TIERS } from './config.js'
import { AREA_BY_NAME, AREA_BY_SLUG } from './areas.js'
import { loadData, recordFor } from './api.js'
import Controls from './Controls.jsx'
import MapView from './MapView.jsx'
import Legend from './Legend.jsx'
import DetailPanel from './DetailPanel.jsx'
import About from './About.jsx'
import './App.css'

/** ?mode=forecast|historical&month=YYYY-MM&area=slug, so a view can be bookmarked. */
function readUrl() {
  const p = new URLSearchParams(window.location.search)
  const m = p.get('month')
  const validMonth = m && /^\d{4}-(0[1-9]|1[0-2])$/.test(m) && m >= FIRST_MONTH && m <= DATA_THROUGH
  return {
    mode: p.get('mode') === 'forecast' ? 'forecast' : 'historical',
    month: validMonth ? m : DATA_THROUGH,
    area: AREA_BY_SLUG.get(p.get('area') ?? '')?.name ?? null,
  }
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

function StatusCard({ title, children }) {
  return (
    <div className="status" role="status">
      <h2>{title}</h2>
      {children}
    </div>
  )
}

export default function App() {
  const [initial] = useState(readUrl)
  const [mode, setMode] = useState(initial.mode)
  const [month, setMonth] = useState(initial.month)
  const [selected, setSelected] = useState(initial.area)
  const [state, retry] = useData()
  const legendRef = useRef(null)

  useEffect(() => {
    const p = new URLSearchParams()
    p.set('mode', mode)
    p.set('month', month)
    if (selected) p.set('area', AREA_BY_NAME.get(selected).slug)
    window.history.replaceState(null, '', `${window.location.pathname}?${p}`)
  }, [mode, month, selected])

  const onSelect = useCallback((name) => setSelected(name), [])
  const data = state.data
  const showNone =
    state.status === 'ready' &&
    [...AREA_BY_NAME.keys()].some((n) => (recordFor(data, mode, month, n)?.tier ?? 'none') === 'none')

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <svg className="brand__mark" viewBox="0 0 32 32" aria-hidden="true">
            <rect x="3" y="3" width="12" height="12" rx="2" fill={TIERS.below_typical.fill} />
            <rect x="17" y="3" width="12" height="12" rx="2" fill={TIERS.typical.fill} />
            <rect x="3" y="17" width="12" height="12" rx="2" fill={TIERS.typical.fill} />
            <rect x="17" y="17" width="12" height="12" rx="2" fill={TIERS.above_typical.fill} />
          </svg>
          <h1>{APP_NAME}</h1>
        </div>
        <p className="tagline">{TAGLINE}</p>
        <p className="data-note">{DATA_NOTE}</p>
      </header>

      <main>
        {state.status === 'loading' && (
          <StatusCard title="Loading reported-incident data">
            <p>Fetching 24 years of monthly history, the October 2026 forecast and the neighbourhood boundaries.</p>
            <div className="status__bar" aria-hidden="true" />
          </StatusCard>
        )}
        {state.status === 'error' && (
          <StatusCard title="The data could not be loaded">
            <p>{String(state.error?.message ?? state.error)}</p>
            <button type="button" className="btn btn--primary" onClick={retry}>
              Try again
            </button>
          </StatusCard>
        )}
        {state.status === 'empty' && (
          <StatusCard title="No data available">
            <p>The data files loaded but contain no months or forecasts. Check the files in public/data or the API.</p>
            <button type="button" className="btn btn--primary" onClick={retry}>
              Reload
            </button>
          </StatusCard>
        )}
        {state.status === 'ready' && (
          <>
            <Controls mode={mode} onMode={setMode} month={month} onMonth={setMonth} months={data.months} />
            <div className="workspace">
              <section className="map-wrap" aria-label="Map of Vancouver neighbourhoods">
                <MapView data={data} mode={mode} month={month} selected={selected} onSelect={onSelect} legendRef={legendRef} />
                <Legend mode={mode} showNone={showNone} ref={legendRef} />
              </section>
              <DetailPanel data={data} mode={mode} month={month} selected={selected} onSelect={onSelect} />
            </div>
          </>
        )}
        <About />
      </main>
    </div>
  )
}
