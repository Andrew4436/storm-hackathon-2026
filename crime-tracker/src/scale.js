import { FILL_NONE, HATCH_ID, HIST_SATURATE_PCT, SCALE } from './config.js'

/*
 * The map's one continuous, diverging colour scale. v runs from -1 (SCALE.below, teal) through 0 (SCALE.mid,
 * neutral grey) to +1 (SCALE.above, amber), interpolated in OKLab so equal steps in v look like equal steps in
 * colour. Deterministic: v is rounded to 0.01 and each of the 201 colours is computed once.
 *
 *   Forecast:      v = p_above - p_below            (+0.8 is a 90% chance above when "within" is near 0)
 *   Past months:   v = pct_vs_typical / 30, clamped (30% from the usual level gets the full colour)
 *   Insufficient data: hatched (HATCH_ID). No usual level to compare with: FILL_NONE.
 */

const hexToRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
const toLinear = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
const toGamma = (c) => (c <= 0.0031308 ? 12.92 * c : 1.055 * c ** (1 / 2.4) - 0.055)

function hexToOklab(hex) {
  const [r, g, b] = hexToRgb(hex).map(toLinear)
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ]
}

function oklabToHex([L, A, B]) {
  const l = (L + 0.3963377774 * A + 0.2158037573 * B) ** 3
  const m = (L - 0.1055613458 * A - 0.0638541728 * B) ** 3
  const s = (L - 0.0894841775 * A - 1.291485548 * B) ** 3
  const rgb = [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ]
  return `#${rgb
    .map((c) => Math.round(Math.min(1, Math.max(0, toGamma(Math.min(1, Math.max(0, c))))) * 255))
    .map((n) => n.toString(16).padStart(2, '0'))
    .join('')}`
}

const STOPS = { below: hexToOklab(SCALE.below), mid: hexToOklab(SCALE.mid), above: hexToOklab(SCALE.above) }
const cache = new Map()

export const clamp1 = (v) => Math.max(-1, Math.min(1, v))

/** The scale colour for v in [-1, 1] (values outside are clamped; anything not finite is the midpoint). */
export function colourFor(v) {
  const q = Number.isFinite(v) ? Math.round(clamp1(v) * 100) / 100 : 0
  let hex = cache.get(q)
  if (!hex) {
    const end = q < 0 ? STOPS.below : STOPS.above
    const t = Math.abs(q)
    hex = oklabToHex(STOPS.mid.map((c, i) => c + (end[i] - c) * t))
    cache.set(q, hex)
  }
  return hex
}

/** CSS linear-gradient of the whole scale, left (-1) to right (+1), built from colourFor. */
export function scaleGradient(steps = 20) {
  const stops = []
  for (let i = 0; i <= steps; i++) stops.push(`${colourFor(-1 + (2 * i) / steps)} ${((100 * i) / steps).toFixed(1)}%`)
  return `linear-gradient(to right, ${stops.join(', ')})`
}

/** Position of v on a left-to-right scale, as a CSS percentage. */
export const scalePos = (v) => `${((clamp1(v) + 1) * 50).toFixed(2)}%`

export const HATCH_FILL = `url(#${HATCH_ID})`

/**
 * The fill for one record (forecast or history row, as indexed by api.js), or null for no record:
 * a scale colour, the hatch for insufficient data, or FILL_NONE when there is no usual level to compare with.
 */
export function fillFor(rec) {
  if (!rec || rec.kind === 'none') return FILL_NONE
  if (rec.kind === 'insufficient_data') return HATCH_FILL
  return colourFor(rec.v)
}

/* ---------- Turning the files' fields into a position on the scale (used once, at load) ---------- */

const finite = (x) => (typeof x === 'number' && Number.isFinite(x) ? x : null)
const OUTCOMES = ['below_typical', 'typical', 'above_typical']

/** {below, within, above} from p_below / p_within / p_above (rescaled to sum to 1), or null if any is missing. */
function readProbs(r) {
  const ps = [r.p_below, r.p_within, r.p_above].map(finite)
  if (ps.some((p) => p == null || p < 0)) return null
  const sum = ps[0] + ps[1] + ps[2]
  if (!(sum > 0)) return null
  return { below: ps[0] / sum, within: ps[1] / sum, above: ps[2] / sum }
}

/** v for a deviation from the usual level, in percent. */
export const pctToV = (pct) => clamp1(pct / HIST_SATURATE_PCT)

/** A history row: kind ('value' | 'insufficient_data' | 'none') and v. */
export function historyShade(r) {
  if (r.relative_activity_tier === 'insufficient_data') return { kind: 'insufficient_data', v: null }
  const pct = finite(r.pct_vs_typical)
  return pct == null ? { kind: 'none', v: null } : { kind: 'value', v: pctToV(pct) }
}

/**
 * A forecast row: kind, v, the three chances and the most likely outcome. A file without chances (an older
 * pipeline) falls back to the forecast's own deviation, coloured like a past month.
 */
export function forecastShade(f) {
  if (f.most_likely === 'insufficient_data' || f.relative_activity_tier === 'insufficient_data') {
    return { kind: 'insufficient_data', v: null, probs: null, likely: null }
  }
  const probs = readProbs(f)
  if (probs) {
    const byOutcome = { below_typical: probs.below, typical: probs.within, above_typical: probs.above }
    const likely = OUTCOMES.includes(f.most_likely)
      ? f.most_likely
      : OUTCOMES.reduce((a, b) => (byOutcome[b] > byOutcome[a] ? b : a))
    return { kind: 'value', v: clamp1(probs.above - probs.below), probs, likely }
  }
  const pct = finite(f.pct_vs_typical)
  if (pct == null) return { kind: 'none', v: null, probs: null, likely: null }
  return { kind: 'value', v: pctToV(pct), probs: null, likely: null }
}
