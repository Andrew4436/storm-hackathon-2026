import { TIERS } from './config.js'

const tierOf = (tier) => (TIERS[tier] ? tier : 'none')

/** Colour chip for a tier. Colour is decoration only; a text label always sits next to it. */
export function Swatch({ tier }) {
  return <span className={`swatch swatch--${tierOf(tier)}`} aria-hidden="true" />
}

/** Tier word in a pill, with its swatch. The only place a tier colour sits beside text. */
export function TierChip({ tier }) {
  return (
    <span className="chip">
      <Swatch tier={tier} />
      {TIERS[tierOf(tier)].label}
    </span>
  )
}
