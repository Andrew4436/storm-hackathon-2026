import {
  APP_NAME,
  EVAL_FROM,
  EVAL_TO,
  EXTRACT_END,
  FIRST_MONTH,
  LIMITATIONS,
  PARTIAL_MONTH,
  PARTIAL_SHARE_PCT,
} from './config.js'
import {
  dayLabel,
  fmtPct1,
  intervalPct,
  modelName,
  monthLabel,
  numberWord,
  oneIn,
  thresholdText,
  typicalLevelText,
} from './format.js'

const monthName = (key) => monthLabel(key).split(' ')[0]
const plural = (n, word) => `${numberWord(n)} ${n === 1 ? word : `${word}s`}`
const MONTH_RE = /^\d{4}-(0[1-9]|1[0-2])$/

/** The held-out months: the first and last of evaluation.folds if it lists months, else EVAL_FROM to EVAL_TO. */
function testPeriod(folds) {
  const months = Array.isArray(folds) && folds.length && folds.every((f) => MONTH_RE.test(f)) ? [...folds].sort() : null
  return months ? [months[0], months[months.length - 1]] : [EVAL_FROM, EVAL_TO]
}

const Num = ({ v }) => <strong className="how__num">{fmtPct1(v)}</strong>

/** One plain sentence per evaluation figure from meta.json; a figure the file lacks is left out. */
function Performance({ meta }) {
  const e = meta.evaluation
  const [from, to] = testPeriod(e.folds)
  const gain = e.improvement_vs_mean_12_pct
  const lines = []
  if (e.wape_pct != null) {
    lines.push(
      <li key="wape">
        On average the forecast misses by <Num v={e.wape_pct} /> of actual activity (WAPE).
      </li>,
    )
  }
  if (gain != null) {
    lines.push(
      <li key="gain">
        {Math.abs(gain) < 0.05 ? (
          <>About the same error as each area&rsquo;s 12-month average.</>
        ) : (
          <>
            That is <Num v={Math.abs(gain)} /> {gain > 0 ? 'less' : 'more'} error than each area&rsquo;s 12-month
            average.
          </>
        )}
      </li>,
    )
  }
  if (e.interval_coverage_pct != null) {
    lines.push(
      <li key="coverage">
        The {intervalPct(meta)}% range held the actual value <Num v={e.interval_coverage_pct} /> of the time.
      </li>,
    )
  }
  if (e.tier_accuracy_pct != null) {
    lines.push(
      <li key="tier">
        It picked the right colour <Num v={e.tier_accuracy_pct} /> of the time
        {e.tier_majority_baseline_pct != null ? (
          <>
            , against <Num v={e.tier_majority_baseline_pct} /> for always picking the most common colour.
          </>
        ) : (
          '.'
        )}
      </li>,
    )
  }
  return (
    <section>
      <h3>How well does it forecast?</h3>
      <p>
        We tested the model we ship, {modelName(meta)}, on months it had never seen: {monthLabel(from)} to{' '}
        {monthLabel(to)}.
      </p>
      {lines.length > 0 && <ul className="how__stats">{lines}</ul>}
    </section>
  )
}

export default function HowItWorks({ meta, headingRef }) {
  const showPartial = PARTIAL_MONTH && PARTIAL_MONTH > meta.data_through
  return (
    <article className="how">
      <h2 className="how__title" tabIndex={-1} ref={headingRef}>
        How this works
      </h2>

      <section>
        <h3>What it does</h3>
        <ul>
          <li>
            Shows reported incidents for each of the 24 VPD neighbourhoods, one month at a time, from{' '}
            {monthLabel(FIRST_MONTH)} to {monthLabel(meta.data_through)}.
          </li>
          <li>
            Combines eight incident types into one severity-weighted activity figure, with weights that follow the
            Statistics Canada Crime Severity Index approach. The plain count of reported incidents sits beside it.
          </li>
          <li>
            Colours each area relative to this area&rsquo;s own history. Areas are never ranked against each other.
          </li>
          <li>
            Forecasts {monthLabel(meta.forecast_month)} for every area, {plural(meta.horizon_months, 'month')} ahead of
            the latest complete month.
          </li>
        </ul>
      </section>

      <section>
        <h3>What it does not do</h3>
        <ul>
          <li>
            It does not score streets, addresses, properties or people. The smallest unit is a whole neighbourhood in
            a whole month.
          </li>
          <li>It does not rate places as places to live or visit, and it is not advice for policing.</li>
          <li>It leaves out homicides and traffic collisions (collisions were recorded differently from 2014).</li>
          <li>It is not live. The data stops on {dayLabel(EXTRACT_END)}.</li>
        </ul>
      </section>

      <section>
        <h3>Limitations</h3>
        <p>{LIMITATIONS}</p>
      </section>

      <section>
        <h3>How the colours and the range are worked out</h3>
        <p>
          For each month, an area&rsquo;s severity-weighted activity is compared with its typical level:{' '}
          {typicalLevelText(meta)}. {thresholdText(meta)} A busy area can be below typical and a quiet one above
          typical, because each is only compared with itself. Areas need 12 months of history before they get a
          colour.
        </p>
        <p>
          The forecast gives a single number and an uncertainty range. The range is where the model expects{' '}
          {intervalPct(meta)}% of outcomes to fall, so roughly one month in {oneIn(meta)} will land outside it.
        </p>
      </section>

      <Performance meta={meta} />

      {showPartial && (
        <section>
          <h3>Why {monthLabel(PARTIAL_MONTH)} is not on the timeline</h3>
          <p>
            The VPD extract ends on {dayLabel(EXTRACT_END)}, so {monthName(PARTIAL_MONTH)} holds only about{' '}
            {PARTIAL_SHARE_PCT}% of a normal month and would look like a sudden drop everywhere. The timeline stops at{' '}
            {monthLabel(meta.data_through)}, and the forecast uses data through {monthName(meta.data_through)}.
          </p>
        </section>
      )}

      <section>
        <h3>Stanley Park and Musqueam</h3>
        <p>
          VPD reports both as their own neighbourhoods, but the City of Vancouver boundary map has no separate shape
          for them, so they appear as circles. Musqueam is kept separate from Dunbar-Southlands; with about two
          reported incidents a month it is shown as insufficient data.
        </p>
      </section>

      <section>
        <h3>Sources</h3>
        <ul>
          <li>
            Incidents: <a href="https://geodash.vpd.ca/opendata/">Vancouver Police Department GeoDASH open data</a>.
          </li>
          <li>
            Boundaries:{' '}
            <a href="https://opendata.vancouver.ca/explore/dataset/local-area-boundary/">
              City of Vancouver Open Data, local-area-boundary
            </a>
            .
          </li>
          <li>
            Basemap: dark grey canvas tiles by <a href="https://www.esri.com">Esri</a>, with{' '}
            <a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>. Map library:{' '}
            <a href="https://leafletjs.com">Leaflet</a>.
          </li>
        </ul>
        <p className="how__note">{APP_NAME} is not affiliated with the Vancouver Police Department.</p>
      </section>
    </article>
  )
}
