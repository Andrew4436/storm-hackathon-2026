import { TIERS } from './config.js'

/** Colour chip for a tier. Colour is decoration only; a text label always sits next to it. */
export default function Swatch({ tier, small = false }) {
  const t = TIERS[tier] ?? TIERS.none
  return (
    <span
      className={small ? 'swatch swatch--sm' : 'swatch'}
      aria-hidden="true"
      style={{
        background: t.fill,
        borderColor: t.stroke ?? 'rgba(31, 41, 51, 0.2)',
        borderStyle: t.dashed ? 'dashed' : 'solid',
      }}
    />
  )
}
