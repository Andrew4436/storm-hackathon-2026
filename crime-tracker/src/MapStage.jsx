import { useCallback, useMemo, useRef, useState } from 'react'
import { AREAS } from './areas.js'
import { HATCH_ID } from './config.js'
import { recordFor } from './api.js'
import MapView from './MapView.jsx'
import HoverCard from './HoverCard.jsx'
import HeroPanel from './HeroPanel.jsx'
import ControlBar from './ControlBar.jsx'
import Legend from './Legend.jsx'
import PulseStrip from './PulseStrip.jsx'

const DESKTOP = '(min-width: 960px)'
const isDesktop = () => window.matchMedia?.(DESKTOP).matches ?? true
/** The drawer's width from the --drawer-w token, so the fit and the hover card follow the CSS. */
function drawerWidth() {
  const w = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--drawer-w'))
  return Number.isFinite(w) && w > 0 ? w : 400
}

/** Hatch fill for "insufficient data" shapes. Referenced by the Leaflet SVG as url(#nc-hatch). */
function HatchDefs() {
  return (
    <svg className="defs" width="0" height="0" aria-hidden="true" focusable="false">
      <defs>
        <pattern id={HATCH_ID} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="6" height="6" style={{ fill: 'var(--ink-800)' }} />
          <line x1="0" y1="0" x2="0" y2="6" strokeWidth="1.5" style={{ stroke: 'var(--fog-400)' }} />
        </pattern>
      </defs>
    </svg>
  )
}

/**
 * The full-bleed map and everything that floats over it. Owns the hover state:
 * hover = {name, x, y, w, h} from the map (drives the one hover card), stripHover = name from the pulse strip.
 */
export default function MapStage({ data, mode, month, selected, onSelect, drawerOpen, areaSelectRef, controls }) {
  const [hover, setHover] = useState(null)
  const [stripHover, setStripHover] = useState(null)
  const topRef = useRef(null)
  const bottomRef = useRef(null)

  const tiers = useMemo(
    () => new Map(AREAS.map((a) => [a.name, recordFor(data, mode, month, a.name)?.tier ?? 'none'])),
    [data, mode, month],
  )
  const showNone = [...tiers.values()].includes('none')
  const highlighted = hover?.name ?? stripHover

  // What the map has to fit around, in map-container pixels: the floating panels that overlap it, and the open
  // drawer as a right inset. On small screens the panels sit outside the map and the drawer is a bottom sheet.
  const measure = useCallback(
    (mapEl) => {
      const m = mapEl.getBoundingClientRect()
      const obstacles = []
      for (const group of [topRef.current, bottomRef.current]) {
        if (!group) continue
        for (const el of group.children) {
          const r = el.getBoundingClientRect()
          const o = { left: r.left - m.left, right: r.right - m.left, top: r.top - m.top, bottom: r.bottom - m.top }
          const overlaps = o.right > 0 && o.left < m.width && o.bottom > 0 && o.top < m.height
          if (r.width && r.height && overlaps) obstacles.push(o)
        }
      }
      return { obstacles, insetRight: drawerOpen && isDesktop() ? drawerWidth() : 0 }
    },
    [drawerOpen],
  )
  const observe = useCallback(
    () => [topRef.current, bottomRef.current].filter(Boolean).flatMap((g) => [g, ...g.children]),
    [],
  )
  const clearHover = useCallback(() => setHover(null), [])

  // The panels come before the map in the DOM so keyboard users reach the controls first; CSS places them.
  return (
    <main className="stage">
      <div className="stage__top" ref={topRef}>
        <HeroPanel />
        <ControlBar {...controls} />
      </div>

      <div className="stage__bottom" ref={bottomRef}>
        <Legend showNone={showNone} />
        <PulseStrip
          tiers={tiers}
          selected={selected}
          highlighted={highlighted}
          onHover={setStripHover}
          onSelect={onSelect}
          drawerOpen={drawerOpen}
          selectRef={areaSelectRef}
        />
      </div>

      <div className="stage__map" onMouseLeave={clearHover}>
        <MapView
          data={data}
          mode={mode}
          month={month}
          selected={selected}
          highlighted={highlighted}
          onSelect={onSelect}
          onHover={setHover}
          measure={measure}
          observe={observe}
          fitKey={drawerOpen}
        />
        <HoverCard
          hover={hover}
          data={data}
          mode={mode}
          month={month}
          rightInset={drawerOpen && isDesktop() ? drawerWidth() : 0}
        />
      </div>
      <HatchDefs />
    </main>
  )
}
