import { APP_NAME, QUESTION, TAGLINE } from './config.js'

export default function HeroPanel() {
  return (
    <header className="hero surface surface--frost">
      <p className="hero__mark">{APP_NAME}</p>
      <h1 className="hero__question">{QUESTION}</h1>
      <p className="hero__lede">{TAGLINE}</p>
    </header>
  )
}
