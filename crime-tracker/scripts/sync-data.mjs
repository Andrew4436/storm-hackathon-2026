// Copy the ML pipeline's outputs into public/data/ (Node, no dependencies).
//
//   npm run sync-data              from ../ml/outputs (the repo's ml/outputs, next to this package)
//   npm run sync-data -- <dir>     from another folder holding the same files
//
// Copies meta.json, history.json and forecast_<forecast_month>.json (the month is read from meta.json), then
// deletes every other forecast_*.json in public/data/. Every file is checked (present, valid JSON) before any is
// copied, so public/data/ is never left half-updated. local-area-boundary.geojson is not touched.
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const pkgDir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const from = process.argv[2] ? resolve(process.argv[2]) : resolve(pkgDir, '..', 'ml', 'outputs')
const to = join(pkgDir, 'public', 'data')
const show = (p) => relative(process.cwd(), p) || '.'

function fail(message) {
  console.error(`sync-data: ${message}`)
  process.exit(1)
}

function readJson(file) {
  let text
  try {
    text = readFileSync(file, 'utf8')
  } catch {
    fail(`${show(file)} is missing.`)
  }
  try {
    return JSON.parse(text)
  } catch (e) {
    fail(`${show(file)} is not valid JSON (${e.message}).`)
  }
}

function size(bytes) {
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(2)} MB`
  if (bytes >= 1e3) return `${(bytes / 1e3).toFixed(1)} kB`
  return `${bytes} B`
}

if (!existsSync(from)) {
  fail(`no folder at ${show(from)}. Run the ML pipeline first, or pass the outputs folder: npm run sync-data -- <dir>`)
}

const meta = readJson(join(from, 'meta.json'))
const month = meta?.forecast_month
if (typeof month !== 'string' || !/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) {
  fail(`meta.json has no valid forecast_month (YYYY-MM); found ${JSON.stringify(month)}.`)
}
const forecastFile = `forecast_${month}.json`

for (const name of ['history.json', forecastFile]) {
  if (!Array.isArray(readJson(join(from, name)))) fail(`${name} should be a JSON array.`)
}

mkdirSync(to, { recursive: true })
console.log(`sync-data: ${show(from)} -> ${show(to)}`)
for (const name of ['meta.json', 'history.json', forecastFile]) {
  copyFileSync(join(from, name), join(to, name))
  console.log(`  copied  ${name} (${size(statSync(join(to, name)).size)})`)
}
for (const name of readdirSync(to)) {
  if (/^forecast_.*\.json$/.test(name) && name !== forecastFile) {
    rmSync(join(to, name))
    console.log(`  removed ${name} (not the current forecast month)`)
  }
}
console.log(
  `Forecast month ${month}, data through ${meta.data_through ?? 'unknown'}, model ${meta.model ?? 'unknown'}.`,
)
