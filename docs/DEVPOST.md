# Devpost submission: NeighbourCast

Paste each block into the matching Devpost field. The story starts at "Inspiration" and goes into "About the project", which accepts Markdown.

## Project name

NeighbourCast

## Elevator pitch (190 of 200 characters)

A Vancouver map that asks one question: is this month unusual for this neighbourhood? Reported-incident history, a one-month forecast and its uncertainty, compared with each area's own past.

---

## Inspiration

Vancouver publishes more than 20 years of police incident data. Most maps built on it rank neighbourhoods against each other. That mostly shows where people live, work and shop, and it puts a label on whole communities.

We wanted to ask a more useful question for residents, visitors and community groups: **is this month unusual for this neighbourhood?** Answering it means comparing each area only with its own past.

## What it does

NeighbourCast is a full-screen map of Vancouver's 24 VPD neighbourhoods.

- **Historical mode:** any month from January 2003 to August 2026. Use the slider, the arrows or **Play months** to watch the city change, for example the dip in spring 2020.
- **Colours relative to this area's own history:** each area is below typical, typical or above typical compared with its own average over the previous 36 complete months. A busy area can be typical and a quiet one above typical. Areas are never ranked against each other.
- **Forecast mode:** October 2026, forecast from data through August, two months ahead (VPD's extract stops on 25 September, so September is incomplete). Every forecast shows an 80% uncertainty range and the plain 12-month average it was tested against.
- **Drawer:** severity-weighted activity, the count of reported incidents, the range, and a 36-month sparkline.
- **How this works:** method, limitations, evaluation and sources, inside the app.
- **Honest edges:** Musqueam averages about two reported incidents a month, so it says "insufficient data" instead of getting a colour. Stanley Park and Musqueam have no City boundary shape, so they are drawn as circles.
- **Usable anywhere:** a bottom sheet on phones, a neighbourhood list for keyboard and screen-reader users, and views saved in the URL.

## How we built it

- **Data (Python, pandas, Jupyter):** a documented notebook turns 962,117 VPD rows into a 24 x 285 neighbourhood-month table. Asserts check the output adds up to the 942,457 cleaned incidents, overall and per type.
- **Target:** a severity-weighted index, using per-type weights that follow the Statistics Canada Crime Severity Index approach (a break-in weighs about five times a theft). The plain count is forecast too, because "about 95 reported incidents" is easier to read than an index.
- **Models (scikit-learn):** a Poisson GLM on log-transformed lag features plus month of year, and a Random Forest. Both were tested against three baselines: the 3-month mean, the 12-month mean and the same month last year.
- **Evaluation:** expanding-window backtest split by target month, over 20 held-out months (2025-01 to 2026-08, 480 neighbourhood-months). The rule for picking the shipped model was written down before the final run.
- **Uncertainty:** the 80% range comes from the model's own backtest errors (ratios of actual to forecast, 10th to 90th percentile), not from tree spread.
- **Serving:** the pipeline writes `history.json` and `forecast_2026-10.json`. A FastAPI service serves them, and the frontend falls back to bundled static copies, so nothing is computed during the demo.
- **Frontend:** Vite, React and react-leaflet on an Esri dark basemap, with City of Vancouver boundary polygons.
- **Process:** a written team contract fixed the data rules, field names, decision rule and wording before code was written. Each part lived on its own branch and merged into `main`. We used AI coding assistants for drafting and review under that contract.

## Challenges we ran into

- **The missing year.** VPD's all-years export has no 2022 at all. We caught it when monthly totals showed a 12-month hole. Zero-filling it would have taught the model a fake collapse. We merged a separate 2022 download (34,323 rows).
- **Duplicates that are real.** 42% of Offence Against a Person rows are exact copies of another row, because VPD redacts their time, block and coordinates for privacy. A routine `drop_duplicates()` would have silently deleted real incidents, so we kept them all.
- **The partial month.** The extract stops on 25 September 2026, so September holds about 70% of a normal month and looks like a sudden drop everywhere. We flag it, keep it off the timeline, and forecast October from data through August.
- **The flat map.** Our first tier rule (each area's own interquartile range) coloured all 24 areas "typical". A same-October norm swung on noise from only three Octobers. We switched to each area's own trailing 36-month mean with ±5% bands, and checked at a checkpoint that the map varies. The drawer always shows the number and its range next to the colour.
- **A model that barely beats an average.** See the next paragraph.

<!-- refresh from reports/evaluation.md -->
**The model barely beats a 12-month average, and we say so.** The Poisson GLM won the pre-registered comparison against the Random Forest (pooled MAE 559.9 vs 611.6 on the severity-weighted index). But its error is only 4.3% lower than a plain 12-month average (585.1), and 3.2% lower on the count. It is better in 14 of 24 areas, and in 2026-01 to 2026-08 the average was more accurate (494.8 vs 528.7). We ship the GLM because the rule said so, and we show the 12-month average beside every forecast in the app. The 80% range held up: fitted on 2025 errors, it covered 79.7% of 2026 outcomes. Tier accuracy is not skill: always guessing "below typical" would have matched 61.1% of test neighbourhood-months, more than any method (best 53.9%), so we never present the colour as a forecast score.

## Accomplishments that we're proud of

- Every incident is accounted for. The notebook's asserts tie the 6,840-row table back to the 942,457 cleaned incidents, per type.
- The model choice was fixed before the final run and is reported with its baseline, including the test period the baseline won.
- The pipeline is deterministic: re-runs give byte-identical files in about 30 seconds.
- The map informs without alarm. It uses teal, grey and amber with no red, hatches "insufficient data", and shows uncertainty as a range bar.
- One wording rule ran everywhere, from the UI to the API to this page: reported incidents, severity-weighted activity, relative to this area's own history, uncertainty range.
- Four people on four branches, working from one contract.

## What we learned

- Check the calendar before the model. A missing year looks exactly like a drop in activity.
- Duplicates are not always errors. Read the publisher's privacy rules before cleaning.
- A strong baseline is a result, not a failure. Saying "about as good as an average" earns more trust than hiding it.
- Framing is a design decision. "Unusual for this place" changes what people do with a map.
- A shared contract lets four people, and their AI assistants, build in parallel without drift.

## What's next for NeighbourCast

- Show it to community groups, neighbourhood houses and City staff, and test whether "unusual for this place" is useful to them.
- Refresh weekly from GeoDASH, which updates every Sunday.
- Add per-type views, for example bike theft by season.
- Correct for reporting lag in Offence Against a Person, where recent months are under-reported.
- Publish the full mapping from each VPD type to its Crime Severity Index category next to the weights.
- Release the clean neighbourhood-month table as an open dataset.

---

## Built with

python, pandas, numpy, scikit-learn, matplotlib, jupyter, fastapi, uvicorn, javascript, react, vite, leaflet, react-leaflet, geojson, openstreetmap, esri, github

Add the hosting service (for example vercel) if the app is deployed there.

## Try it out links

- App: `<app-url>`
- Code: https://github.com/Andrew4436/storm-hackathon-2026

## Track opt-ins

- **SSSS Python:** the cleaning, modelling, evaluation and API are all Python (pandas, scikit-learn, FastAPI).
- **IATSU Best Design:** a calm palette with no red, colour relative to each area's own history, a visible uncertainty range, a phone bottom sheet and a keyboard route to every area.
- **Enactus UNSDG:** SDG 16.10 (public access to information: makes VPD open data readable). SDG 11.7 (inclusive, accessible public spaces: context for residents and visitors without stigmatising areas). SDG 11.3 (participatory planning: a shared neighbourhood-level view for community groups and planners).
- **MLH .Tech domain:** only if `neighbourcast.tech` (or another .tech name) is registered through the MLH offer and points to the app.
- **Best Beginner:** only if at least two of the four of us are first-time hackers.

## Submission checklist

Deadline: **Sunday 2026-10-04, 12:00 PM PDT**. Aim to press submit by **11:40 AM**. Judging starts at 1:00 PM.

- [ ] Project name: NeighbourCast
- [ ] Elevator pitch pasted (190 characters)
- [ ] "About the project": Inspiration to What's next, pasted, with the refreshed numbers paragraph
- [ ] Built with tags added
- [ ] Try it out links: app URL (tested in a private window) and GitHub repo
- [ ] Video demo link: unlisted YouTube, 3:00 or less, plays logged out (mandatory)
- [ ] Image gallery: 3 to 5 screenshots (forecast view with drawer, spring 2020 in historical mode, How this works, phone view)
- [ ] All four teammates have accepted the Devpost team invite
- [ ] Track opt-ins ticked, only the ones we qualify for
- [ ] Hardware: No
- [ ] AI-assistance line kept in "How we built it" (check the StormHacks rules)
- [ ] Any event questions answered (for example the table number)
- [ ] The project shows "Submitted", not "Draft", before 12:00 PM PDT
