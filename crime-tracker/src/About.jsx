import { LIMITATIONS } from './config.js'

export default function About() {
  return (
    <details className="about">
      <summary>About this map</summary>
      <div className="about__body">
        <p className="about__lead">{LIMITATIONS}</p>

        <div className="about__cols">
          <section>
            <h3>What it does</h3>
            <ul>
              <li>Shows reported incidents for each of the 24 VPD neighbourhoods, one month at a time, from January 2003 to August 2026.</li>
              <li>
                Combines eight incident types into one severity-weighted activity figure, using weights that follow the
                Statistics Canada Crime Severity Index approach. The plain count of reported incidents is shown alongside.
              </li>
              <li>
                Colours each area relative to this area&rsquo;s own history: below typical, typical or above typical
                compared with its own last 36 complete months. Areas are not ranked against each other.
              </li>
              <li>Forecasts October 2026 for every area, two months ahead of the latest complete month, with an 80% uncertainty range.</li>
            </ul>
          </section>
          <section>
            <h3>What it does not do</h3>
            <ul>
              <li>It does not score streets, addresses, properties or people. The smallest unit is a whole neighbourhood in a whole month.</li>
              <li>It does not rate places as places to live or visit, and it is not advice for policing.</li>
              <li>It does not include homicides or traffic collisions (collisions were recorded differently from 2014).</li>
              <li>It is not live: the data stops at September 2026.</li>
            </ul>
          </section>
        </div>

        <h3>Why September 2026 is not on the timeline</h3>
        <p>
          The VPD extract ends on 25 September 2026, so September holds only about 70% of a normal month. Showing it
          would look like a sudden drop everywhere. The timeline stops at August 2026, the last complete month, and the
          forecast is made from data through August.
        </p>

        <h3>Stanley Park and Musqueam</h3>
        <p>
          VPD reports both as their own neighbourhoods, but the City of Vancouver boundary map has no separate shape
          for them, so they appear as circles. Musqueam is kept separate from Dunbar-Southlands; with about two
          reported incidents a month it is shown as insufficient data.
        </p>

        <h3>Sources</h3>
        <ul className="about__sources">
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
            Basemap: <a href="https://www.openstreetmap.org/copyright">&copy; OpenStreetMap contributors</a>,{' '}
            light grey canvas tiles by <a href="https://www.esri.com">Esri</a>. Map library:{' '}
            <a href="https://leafletjs.com">Leaflet</a>.
          </li>
        </ul>
      </div>
    </details>
  )
}
