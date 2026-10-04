import { useEffect, useMemo, useRef, useState } from 'react'
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Tooltip, Pane, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { AREAS, AREA_BY_POLYGON } from './areas.js'
import { MAP_STYLE, TIERS } from './config.js'
import { recordFor } from './api.js'
import { fmtNum } from './format.js'
import Swatch from './Swatch.jsx'

const OSM_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas'
// Keyless CARTO basemaps now return "API key required" placeholder tiles (HTTP 200), so the
// neutral Esri light-grey canvas is the default. If it fails to load, fall back to OpenStreetMap.
const TILES = {
  esri: {
    url: `${ESRI}/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
    labels: `${ESRI}/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}`,
    attribution: `Tiles &copy; <a href="https://www.esri.com">Esri</a> &mdash; Esri, HERE, Garmin, ${OSM_ATTR}`,
    maxNativeZoom: 16,
  },
  osm: { url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: OSM_ATTR, maxNativeZoom: 19 },
}

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
        maxZoom={18}
        eventHandlers={handlers}
      />
      {t.labels && (
        <Pane name="basemap-labels" style={{ zIndex: 620, pointerEvents: 'none' }}>
          <TileLayer url={t.labels} maxNativeZoom={t.maxNativeZoom} maxZoom={18} />
        </Pane>
      )}
    </>
  )
}

/**
 * Fit the 24 areas into the map without hiding any of them under the legend (bottom-left):
 * reserve either a left strip or a bottom strip for it, whichever allows the larger zoom.
 */
function FitToAreas({ bounds, legendRef }) {
  const map = useMap()
  useEffect(() => {
    const fit = () => {
      // On small screens the legend sits below the map (static), so it needs no room on the map.
      const lg = legendRef?.current
      const el = lg && getComputedStyle(lg).position === 'absolute' ? lg : null
      const w = el ? el.offsetWidth + 28 : 16
      const h = el ? el.offsetHeight + 28 : 16
      const zLeft = map.getBoundsZoom(bounds, false, L.point(w + 16, 32))
      const zBottom = map.getBoundsZoom(bounds, false, L.point(32, h + 16))
      map.fitBounds(
        bounds,
        zLeft >= zBottom
          ? { paddingTopLeft: [w, 16], paddingBottomRight: [16, 16] }
          : { paddingTopLeft: [16, 16], paddingBottomRight: [16, h] },
      )
    }
    fit()
    map.on('resize', fit)
    return () => map.off('resize', fit)
  }, [map, bounds, legendRef])
  return null
}

function styleFor(tier, selected, hovered) {
  const t = TIERS[tier] ?? TIERS.none
  let color = t.stroke ?? MAP_STYLE.stroke
  let weight = MAP_STYLE.weight
  if (hovered) {
    color = '#52606D'
    weight = MAP_STYLE.hoverWeight
  }
  if (selected) {
    color = MAP_STYLE.selectedStroke
    weight = MAP_STYLE.selectedWeight
  }
  return {
    fillColor: t.fill,
    fillOpacity: MAP_STYLE.fillOpacity,
    color,
    weight,
    opacity: 1,
    dashArray: t.dashed && !selected ? '4 3' : null,
  }
}

function TooltipBody({ name, tier, rec, mode }) {
  const label = (TIERS[tier] ?? TIERS.none).label
  let value = 'No data for this month'
  if (rec && mode === 'forecast') {
    value =
      tier === 'insufficient_data'
        ? 'Too few incidents to forecast'
        : `Forecast ${fmtNum(rec.forecast_weighted_index)} (range ${fmtNum(rec.interval_low)}–${fmtNum(rec.interval_high)})`
  } else if (rec) {
    value = `Activity ${fmtNum(rec.weighted_index)} · ${fmtNum(rec.incident_count)} reported incidents`
  }
  return (
    <div className="map-tip">
      <strong>{name}</strong>
      <span className="map-tip__tier">
        <Swatch tier={tier} small />
        {label}
      </span>
      <span className="map-tip__value">{value}</span>
    </div>
  )
}

// Leaflet's tooltip focus listeners can make each SVG path a tab stop (Chromium). Keep the paths out of
// the tab order (the area <select> is the keyboard route); hover tooltips are unaffected.
const untab = (layer) =>
  layer.eachLayer ? layer.eachLayer(untab) : layer.getElement?.()?.setAttribute('tabindex', '-1')

function AreaLayer({ area, feature, view, selected, hovered, onSelect, onHover }) {
  const ref = useRef(null)
  const { tier } = view
  useEffect(() => {
    if (selected || hovered) ref.current?.bringToFront()
  }, [selected, hovered])

  const handlers = useMemo(
    () => ({
      add: (e) => untab(e.target),
      click: () => onSelect(area.name),
      mouseover: () => onHover(area.name),
      mouseout: () => onHover(null),
    }),
    [area.name, onSelect, onHover],
  )
  const pathOptions = styleFor(tier, selected, hovered)
  const tip = (
    <Tooltip sticky={area.render === 'polygon'} direction="top" offset={[0, -6]} opacity={1}>
      <TooltipBody name={area.name} {...view} />
    </Tooltip>
  )

  if (area.render === 'marker') {
    return (
      <CircleMarker
        ref={ref}
        center={area.coords}
        radius={area.radius}
        pathOptions={{ ...pathOptions, weight: Math.max(pathOptions.weight, 1.5) }}
        eventHandlers={handlers}
      >
        {tip}
      </CircleMarker>
    )
  }
  return (
    <GeoJSON ref={ref} data={feature} pathOptions={pathOptions} eventHandlers={handlers}>
      {tip}
    </GeoJSON>
  )
}

export default function MapView({ data, mode, month, selected, onSelect, legendRef }) {
  const [hovered, setHovered] = useState(null)

  const featureByArea = useMemo(() => {
    const m = new Map()
    for (const f of data.boundaries.features) {
      const area = AREA_BY_POLYGON.get(f.properties?.name)
      if (area) m.set(area.name, f)
    }
    return m
  }, [data.boundaries])

  const bounds = useMemo(() => {
    const b = L.geoJSON(data.boundaries).getBounds()
    for (const a of AREAS) if (a.coords) b.extend(a.coords)
    return b
  }, [data.boundaries])

  const views = AREAS.map((area) => {
    const rec = recordFor(data, mode, month, area.name)
    return { area, view: { tier: rec?.tier ?? 'none', rec, mode } }
  })
  const layerProps = (area) => ({
    selected: selected === area.name,
    hovered: hovered === area.name,
    onSelect,
    onHover: setHovered,
  })

  return (
    <MapContainer
      className="map"
      bounds={bounds}
      boundsOptions={{ padding: [16, 16] }}
      zoomSnap={0.25}
      minZoom={10}
      maxBounds={bounds.pad(0.6)}
    >
      <BaseLayer />
      <FitToAreas bounds={bounds} legendRef={legendRef} />
      {views
        .filter(({ area }) => area.render === 'polygon' && featureByArea.has(area.name))
        .map(({ area, view }) => (
          <AreaLayer
            key={area.slug}
            area={area}
            feature={featureByArea.get(area.name)}
            view={view}
            {...layerProps(area)}
          />
        ))}
      <Pane name="area-markers" style={{ zIndex: 450 }}>
        {views
          .filter(({ area }) => area.render === 'marker')
          .map(({ area, view }) => (
            <AreaLayer key={area.slug} area={area} view={view} {...layerProps(area)} />
          ))}
      </Pane>
    </MapContainer>
  )
}
