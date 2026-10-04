import {
  APP_NAME,
  DATA_THROUGH,
  EVAL_FROM,
  EVAL_GAIN_PCT,
  EVAL_TO,
  EXTRACT_END,
  FIRST_MONTH,
  FORECAST_MONTH,
  HORIZON_MONTHS,
  LIMITATIONS,
  PARTIAL_MONTH,
  PARTIAL_SHARE_PCT,
  TIER_WINDOW_MONTHS,
} from './config.js'
import { dayLabel, monthLabel, numberWord } from './format.js'

const monthName = (key) => monthLabel(key).split(' ')[0]
const plural = (n, word) => `${numberWord(n)} ${n === 1 ? word : `${word}s`}`

export default function HowItWorks({ headingRef }) {
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
            {monthLabel(FIRST_MONTH)} to {monthLabel(DATA_THROUGH)}.
          </li>
          <li>
            Combines eight incident types into one severity-weighted activity figure, with weights that follow the
            Statistics Canada Crime Severity Index approach. The plain count of reported incidents sits beside it.
          </li>
          <li>
            Colours each area relative to this area&rsquo;s own history. Areas are never ranked against each other.
          </li>
          <li>
            Forecasts {monthLabel(FORECAST_MONTH)} for every area, {plural(HORIZON_MONTHS, 'month')} ahead of the latest
            complete month.
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
          For each month, an area&rsquo;s severity-weighted activity is compared with its own average over the
          previous {TIER_WINDOW_MONTHS} complete months. Close to that average is typical; clearly lower is below
          typical; clearly higher is above typical. A busy area can be below typical and a quiet one above typical,
          because each is only compared with itself. Areas need 12 months of history before they get a colour.
        </p>
        <p>
          The forecast gives a single number and an uncertainty range. The range is where the model expects 80% of
          outcomes to fall, so roughly one month in five will land outside it.
        </p>
      </section>

      <section>
        <h3>How well the forecast does</h3>
        <p>
          We tested the forecast on months it had never seen: {monthLabel(EVAL_FROM)} to {monthLabel(EVAL_TO)}. The
          model we ship, a Poisson regression (GLM), had about {EVAL_GAIN_PCT}% lower error than simply using each
          area&rsquo;s 12-month average.
        </p>
      </section>

      {PARTIAL_MONTH && (
        <section>
          <h3>Why {monthLabel(PARTIAL_MONTH)} is not on the timeline</h3>
          <p>
            The VPD extract ends on {dayLabel(EXTRACT_END)}, so {monthName(PARTIAL_MONTH)} holds only about{' '}
            {PARTIAL_SHARE_PCT}% of a normal month and would look like a sudden drop everywhere. The timeline stops at{' '}
            {monthLabel(DATA_THROUGH)}, and the forecast uses data through {monthName(DATA_THROUGH)}.
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
