import { FILL_NONE } from './config.js'
import { HATCH_FILL } from './scale.js'

/**
 * A small colour chip for a map fill (fillFor in scale.js): a scale colour, the hatch, or the "no reference" fill.
 * Colour is decoration only; a text label always sits next to it.
 */
export function Swatch({ fill }) {
  if (fill === HATCH_FILL) return <span className="swatch swatch--hatch" aria-hidden="true" />
  if (fill === FILL_NONE) return <span className="swatch swatch--none" aria-hidden="true" />
  return <span className="swatch" style={{ background: fill }} aria-hidden="true" />
}
