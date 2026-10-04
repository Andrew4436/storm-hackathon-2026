// The 24 VPD neighbourhoods and how each one is drawn.
// 21 names match a City of Vancouver local-area polygon exactly. Exceptions:
// - Central Business District is the polygon named "Downtown".
// - Stanley Park has no polygon: drawn as a circle marker.
// - Musqueam lies inside Dunbar-Southlands but is a separate VPD area: drawn as its own
//   small marker. Never merge it into Dunbar-Southlands.
const MARKERS = {
  'Stanley Park': { coords: [49.3017, -123.1417], radius: 13 },
  Musqueam: { coords: [49.225, -123.2], radius: 8 },
}
const POLYGON_RENAMES = { 'Central Business District': 'Downtown' }

const NAMES = [
  'Arbutus Ridge', 'Central Business District', 'Dunbar-Southlands', 'Fairview',
  'Grandview-Woodland', 'Hastings-Sunrise', 'Kensington-Cedar Cottage', 'Kerrisdale',
  'Killarney', 'Kitsilano', 'Marpole', 'Mount Pleasant', 'Musqueam', 'Oakridge',
  'Renfrew-Collingwood', 'Riley Park', 'Shaughnessy', 'South Cambie', 'Stanley Park',
  'Strathcona', 'Sunset', 'Victoria-Fraserview', 'West End', 'West Point Grey',
]

export const slugify = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')

export const AREAS = NAMES.map((name) => {
  const marker = MARKERS[name]
  return {
    name,
    slug: slugify(name),
    polygonName: marker ? null : POLYGON_RENAMES[name] ?? name,
    render: marker ? 'marker' : 'polygon',
    coords: marker?.coords ?? null,
    radius: marker?.radius ?? null,
  }
})

export const AREA_BY_NAME = new Map(AREAS.map((a) => [a.name, a]))
export const AREA_BY_SLUG = new Map(AREAS.map((a) => [a.slug, a]))
export const AREA_BY_POLYGON = new Map(AREAS.filter((a) => a.polygonName).map((a) => [a.polygonName, a]))
