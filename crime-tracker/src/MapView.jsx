import { memo, useEffect, useMemo, useRef, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Pane, ZoomControl, useMap, useMapEvents } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { AREAS, AREA_BY_POLYGON } from './areas.js'
import { MAP_STYLE } from './config.js'
import { recordFor } from './api.js'
import { fillFor } from './scale.js'

const OSM_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
const DATA_ATTR =
  'Data: <a href="https://geodash.vpd.ca/opendata/">VPD</a>, ' +
  '<a href="https://opendata.vancouver.ca/explore/dataset/local-area-boundary/">City of Vancouver</a>'
const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas'
const MAX_ZOOM = 18
// Keyless CARTO basemaps return "API key required" placeholder tiles, so the Esri dark grey canvas is the
// default. If it fails to load, fall back to OpenStreetMap, darkened in CSS to sit in the same night palette.
const TILES = {
  esri: {
    url: `${ESRI}/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
    labels: `${ESRI}/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}`,
    attribution: `Tiles &copy; <a href="https://www.esri.com">Esri</a>, HERE, Garmin, ${OSM_ATTR}`,
    maxNativeZoom: 16,
  },
  osm: {
    url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: OSM_ATTR,
    maxNativeZoom: 19,
    className: 'tiles-osm',
  },
}

const MARKER_AREAS = AREAS.filter((a) => a.render === 'marker')
const POLYGON_COUNT = AREAS.length - MARKER_AREAS.length

// Hover cards need a real pointer; on touch, a tap selects and the drawer shows the detail.
const CAN_HOVER = typeof window !== 'undefined' && !!window.matchMedia?.('(hover: hover) and (pointer: fine)').matches

function BaseLayer() {
  const [provider, setProvider] = useState('esri')
  const errors = useRef(0)
  const t = TILES[provider]
  const handlers = useMemo(
    () => ({
      tileerror: () => {
        errors.current += 1
        if (provider === 'esri' && errors.current >= 4) setProvider('osm')
      },
    }),
    [provider],
  )
  return (
    <>
      <TileLayer
        key={provider}
        url={t.url}
        attribution={t.attribution}
        maxNativeZoom={t.maxNativeZoom}
        maxZoom={MAX_ZOOM}
        className={t.className}
        eventHandlers={handlers}
      />
      {t.labels && (
        <Pane name="basemap-labels" style={{ zIndex: 620, pointerEvents: 'none' }}>
          <TileLayer url={t.labels} maxNativeZoom={t.maxNativeZoom} maxZoom={MAX_ZOOM} />
        </Pane>
      )}
    </>
  )
}

/** Credit the incident and boundary data next to the tile credits, always visible on the map. */
function DataAttribution() {
  const map = useMap()
  useEffect(() => {
    const control = map.attributionControl
    if (!control) return
    control.addAttribution(DATA_ATTR)
    return () => control.removeAttribution(DATA_ATTR)
  }, [map])
  return null
}

const EDGE = 16
const GAP = 8
const MIN_FREE = 160
const FALLBACK_PAD = 24
const INITIAL_ZOOM = 11
const RESIZE_SETTLE_MS = 120
const DRAWER_SETTLE_MS = 280 // the drawer and the panels slide for 240 ms
// Used only if the boundary file has no usable shapes, so the map still has somewhere to start.
const CITY_FALLBACK = L.latLngBounds([49.198, -123.225], [49.315, -123.023])

const isPad = (p, W, H) =>
  !!p &&
  [p.top, p.right, p.bottom, p.left].every((v) => Number.isFinite(v) && v >= 0) &&
  p.left + p.right < W &&
  p.top + p.bottom < H

/**
 * Padding that keeps every area clear of the floating panels. The open drawer is always a right inset. Each
 * panel can be avoided either vertically (reserve a strip above or below it) or horizontally (a strip beside
 * it); try every combination and keep the one that allows the largest zoom.
 */
function bestPadding(map, bounds, W, H, obstacles, insetRight) {
  const base = EDGE + insetRight
  const midX = (W - insetRight) / 2
  let best = null
  let roomiest = null
  for (let mask = 0; mask < 1 << obstacles.length; mask++) {
    let top = EDGE
    let bottom = EDGE
    let left = EDGE
    let right = base
    obstacles.forEach((o, i) => {
      if (mask & (1 << i)) {
        if ((o.left + o.right) / 2 < midX) left = Math.max(left, o.right + GAP)
        else right = Math.max(right, W - o.left + GAP)
      } else if ((o.top + o.bottom) / 2 < H / 2) top = Math.max(top, o.bottom + GAP)
      else bottom = Math.max(bottom, H - o.top + GAP)
    })
    const freeW = W - left - right
    const freeH = H - top - bottom
    if (!(freeW > 0 && freeH > 0)) continue
    const area = freeW * freeH
    if (freeW < MIN_FREE || freeH < MIN_FREE) {
      // Too tight to use as a fit target; remember the roomiest one in case nothing else works.
      if (!roomiest || area > roomiest.area) roomiest = { area, top, bottom, left, right }
      continue
    }
    const zoom = map.getBoundsZoom(bounds, false, L.point(left + right, top + bottom))
    if (Number.isFinite(zoom) && (!best || zoom > best.zoom)) best = { zoom, top, bottom, left, right }
  }
  return best ?? roomiest ?? { top: EDGE, bottom: EDGE, left: EDGE, right: base }
}

/**
 * Fit the 24 areas into the part of the map the floating panels and the drawer leave free.
 *
 * Leaflet cannot fit anything into a container with no size: the zoom comes out infinite and the first
 * setView throws "Invalid LatLng (NaN, NaN)". So the map starts from a fixed centre and zoom, and the fit runs
 * only once the map is ready and laid out (whenReady, then the next animation frame), again when the map or a
 * panel changes size, and when the drawer has finished opening or closing. Every padding is checked (finite,
 * non-negative, smaller than the map) before it reaches fitBounds; otherwise a plain 24 px fit is used.
 */
function FitToAreas({ bounds, measure, observe, fitKey }) {
  const map = useMap()
  const last = useRef(null)
  const scheduleRef = useRef(null)
  const measureRef = useRef(measure)
  useEffect(() => {
    measureRef.current = measure
  }, [measure])

  useEffect(() => {
    let timer = 0
    let frame = 0
    let due = 0

    function fit() {
      const el = map.getContainer()
      const W = el.clientWidth
      const H = el.clientHeight
      if (!(W > 0 && H > 0)) return // not laid out yet; the ResizeObserver calls back once it is
      // Leaflet drops a new view requested mid-zoom-animation, so wait for the current one to finish.
      if (map._animatingZoom) {
        map.once('zoomend', onZoomEnd)
        return
      }
      // Leaflet caches the size it saw at mount, which may have been zero.
      const cached = map.getSize()
      if (cached.x !== W || cached.y !== H) map.invalidateSize({ pan: false })

      const { obstacles, insetRight } = measureRef.current(el)
      const ok = (q) =>
        isPad(q, W, H) && Number.isFinite(map.getBoundsZoom(bounds, false, L.point(q.left + q.right, q.top + q.bottom)))
      let p = bestPadding(map, bounds, W, H, obstacles, Number.isFinite(insetRight) && insetRight > 0 ? insetRight : 0)
      if (!ok(p)) p = { top: FALLBACK_PAD, right: FALLBACK_PAD, bottom: FALLBACK_PAD, left: FALLBACK_PAD }
      if (!ok(p)) return // smaller than 48 px: nothing sensible to fit into

      const key = `${p.top},${p.right},${p.bottom},${p.left},${W},${H}`
      if (key === last.current) return
      const animate = last.current != null && !document.hidden
      last.current = key
      map.fitBounds(bounds, { paddingTopLeft: [p.left, p.top], paddingBottomRight: [p.right, p.bottom], animate })
    }

    function onFrame() {
      frame = 0
      due = 0
      fit()
    }
    // On the next frame, once layout is final. A hidden page gets no frames, so there it runs on a timer.
    function nextFrame() {
      if (document.hidden) {
        timer = setTimeout(() => {
          timer = 0
          onFrame()
        }, 0)
      } else {
        frame = requestAnimationFrame(onFrame)
      }
    }
    // Debounced: a request never runs earlier than one already waiting.
    function schedule(delay) {
      const at = performance.now() + delay
      if ((timer || frame) && due >= at) return
      clearTimeout(timer)
      cancelAnimationFrame(frame)
      timer = 0
      frame = 0
      due = at
      if (delay <= 0) {
        nextFrame()
        return
      }
      timer = setTimeout(() => {
        timer = 0
        nextFrame()
      }, delay)
    }
    function onZoomEnd() {
      schedule(0)
    }
    function onResize() {
      schedule(RESIZE_SETTLE_MS)
    }
    function onReady() {
      schedule(0)
    }
    scheduleRef.current = schedule

    map.whenReady(onReady)
    map.on('resize', onResize)
    const ro = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(onResize)
    ro?.observe(map.getContainer())
    for (const el of observe()) ro?.observe(el)
    return () => {
      clearTimeout(timer)
      cancelAnimationFrame(frame)
      map.off('load', onReady)
      map.off('resize', onResize)
      map.off('zoomend', onZoomEnd)
      ro?.disconnect()
      scheduleRef.current = null
    }
  }, [map, bounds, observe])

  // The drawer opened or closed: refit once it and the panels have finished sliding.
  const lastKey = useRef(fitKey)
  useEffect(() => {
    if (lastKey.current === fitKey) return
    lastKey.current = fitKey
    scheduleRef.current?.(DRAWER_SETTLE_MS)
  }, [fitKey])
  return null
}

/**
 * Path options for one area. `fillColor` is the record's place on the continuous scale (or the hatch, or the
 * "no reference" fill) from fillFor, the same mapping for polygons and the two circle markers.
 */
function styleFor(rec, { selected, dimmed, hovered }, marker = false) {
  let fillOpacity = MAP_STYLE.fillOpacity
  if (dimmed) fillOpacity = MAP_STYLE.dimFillOpacity
  if (hovered) fillOpacity = MAP_STYLE.hoverFillOpacity
  let color = MAP_STYLE.stroke
  let opacity = MAP_STYLE.strokeOpacity
  let weight = marker ? 1.5 : MAP_STYLE.weight
  if (hovered) {
    color = MAP_STYLE.hoverStroke
    opacity = 0.9
    weight = MAP_STYLE.hoverWeight
  }
  if (selected) {
    color = MAP_STYLE.selectedStroke
    opacity = 1
    weight = MAP_STYLE.selectedWeight
  }
  return { fillColor: fillFor(rec), fillOpacity, color, opacity, weight }
}

const viewState = (name, selected, highlighted) => ({
  selected: selected === name,
  dimmed: !!selected && selected !== name,
  hovered: highlighted === name,
})

const FADE_MS = 700

/**
 * The one orchestrated moment on load: each shape fades in, 20 ms after the previous one. The inline animation
 * is removed once it has run, because bringToFront() later moves the path in the DOM, which would replay it.
 */
function fadeIn(layer, index) {
  const el = layer.getElement?.()
  if (!el) return
  const delay = index * 20
  let timer = 0
  const clear = () => {
    clearTimeout(timer)
    el.style.animation = ''
    el.removeEventListener('animationend', clear)
    el.removeEventListener('animationcancel', clear)
  }
  el.addEventListener('animationend', clear)
  el.addEventListener('animationcancel', clear)
  // Fallback for when animationend never arrives (reduced motion, or a page that is not painting yet).
  timer = setTimeout(clear, FADE_MS + delay + 300)
  el.style.animation = `nc-area-in ${FADE_MS}ms ease-out ${delay}ms backwards`
}

const polygonName = (layer) => AREA_BY_POLYGON.get(layer.feature?.properties?.name)?.name

/**
 * All 24 areas: ONE GeoJSON layer (stable, never re-keyed) plus the two circle markers. Styles are applied
 * imperatively with setStyle when the view changes, so no layer is ever re-created under the cursor. Hover
 * is reported to React as {name, x, y}; there are no Leaflet tooltips.
 */
function AreasLayer({ data, features, mode, month, selected, highlighted, onSelect, onHover }) {
  const map = useMap()
  const geoRef = useRef(null)
  const markerRefs = useRef(new Map())
  const [ready, setReady] = useState(false)

  // Initial styles, used once when the layers are created; later changes go through setStyle below.
  const [initial] = useState(() => {
    const style = (name, marker) =>
      styleFor(recordFor(data, mode, month, name), viewState(name, selected, highlighted), marker)
    return {
      polygon: (feature) => style(AREA_BY_POLYGON.get(feature.properties?.name)?.name, false),
      markers: Object.fromEntries(MARKER_AREAS.map((a) => [a.name, style(a.name, true)])),
    }
  })

  useEffect(() => {
    const restyle = (layer, name, marker) =>
      layer.setStyle(styleFor(recordFor(data, mode, month, name), viewState(name, selected, highlighted), marker))
    geoRef.current?.eachLayer((l) => restyle(l, polygonName(l), false))
    for (const [name, l] of markerRefs.current) restyle(l, name, true)
  }, [ready, data, mode, month, selected, highlighted])

  // Keep the selected outline above its neighbours. Only on selection change, never on hover.
  useEffect(() => {
    if (!selected) return
    geoRef.current?.eachLayer((l) => {
      if (polygonName(l) === selected) l.bringToFront()
    })
  }, [ready, selected])

  const handlers = useMemo(() => {
    const report = (name, e) => {
      if (!CAN_HOVER || !name) return
      const size = map.getSize()
      onHover({ name, x: e.containerPoint.x, y: e.containerPoint.y, w: size.x, h: size.y })
    }
    const polygons = {
      add: (e) => {
        let i = 0
        e.target.eachLayer((l) => fadeIn(l, i++))
        setReady(true)
      },
      mouseover: (e) => report(polygonName(e.layer), e),
      mousemove: (e) => report(polygonName(e.layer), e),
      mouseout: () => onHover(null),
      click: (e) => onSelect(polygonName(e.layer)),
    }
    const marker = (name, index) => ({
      add: (e) => fadeIn(e.target, index),
      mouseover: (e) => report(name, e),
      mousemove: (e) => report(name, e),
      mouseout: () => onHover(null),
      click: () => onSelect(name),
    })
    return {
      polygons,
      markers: Object.fromEntries(MARKER_AREAS.map((a, i) => [a.name, marker(a.name, POLYGON_COUNT + i)])),
    }
  }, [map, onHover, onSelect])

  // Belt and braces: whatever happens to individual paths, leaving the map clears the hover state.
  useMapEvents({ mouseout: () => onHover(null) })

  return (
    <>
      <GeoJSON ref={geoRef} data={features} style={initial.polygon} eventHandlers={handlers.polygons} />
      <Pane name="area-markers" style={{ zIndex: 450 }}>
        {MARKER_AREAS.map((a) => (
          <CircleMarker
            key={a.slug}
            ref={(layer) => {
              if (layer) markerRefs.current.set(a.name, layer)
              else markerRefs.current.delete(a.name)
            }}
            center={a.coords}
            radius={a.radius}
            pathOptions={initial.markers[a.name]}
            eventHandlers={handlers.markers[a.name]}
          />
        ))}
      </Pane>
    </>
  )
}

function MapView({ data, mode, month, selected, highlighted, onSelect, onHover, measure, observe, fitKey }) {
  const features = useMemo(
    () => ({
      type: 'FeatureCollection',
      features: data.boundaries.features.filter((f) => AREA_BY_POLYGON.has(f.properties?.name)),
    }),
    [data.boundaries],
  )

  const bounds = useMemo(() => {
    const b = L.geoJSON(data.boundaries).getBounds()
    for (const a of AREAS) if (a.coords) b.extend(a.coords)
    return b.isValid() ? b : CITY_FALLBACK
  }, [data.boundaries])

  // The map starts from a fixed view: nothing at mount depends on the container's size (see FitToAreas).
  // maxZoom keeps every zoom finite. maxBounds is roomy so the fit can shift the city away from the panels.
  return (
    <MapContainer
      className="map"
      center={bounds.getCenter()}
      zoom={INITIAL_ZOOM}
      zoomSnap={0.25}
      minZoom={10}
      maxZoom={MAX_ZOOM}
      maxBounds={bounds.pad(1.5)}
      zoomControl={false}
    >
      <ZoomControl position="bottomright" />
      <BaseLayer />
      <DataAttribution />
      <FitToAreas bounds={bounds} measure={measure} observe={observe} fitKey={fitKey} />
      <AreasLayer
        data={data}
        features={features}
        mode={mode}
        month={month}
        selected={selected}
        highlighted={highlighted}
        onSelect={onSelect}
        onHover={onHover}
      />
    </MapContainer>
  )
}

export default memo(MapView)
