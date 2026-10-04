# Pitch: NeighbourCast

The format is a 3-minute pitch plus 1 minute of Q&A at our table, from 1:00 PM on Sunday 2026-10-04. We may be judged twice, so give the same demo both times.

Judging criteria: technical complexity, design, pitch, originality. There are no slides: the app is the deck.

## Roles

- **Speaker 1, Humberto:** hook, demo narration, ethics, close.
- **Speaker 2, Chibueze:** the technical segment and model questions.
- **At the laptop, James:** does every demo click, so Speaker 1 can face the judges. Takes design questions.
- **Timekeeper, Andrew:** stopwatch, signals at 1:25 and 2:35, warms the app before each slot. Takes deployment questions.

## Bookmarks on the demo laptop

| Bookmark | URL | Use |
|---|---|---|
| Start | `<app-url>/?mode=historical&month=2019-10` | Loaded before the judges arrive |
| Kitsilano | `<app-url>/?mode=forecast&area=kitsilano` | Recovery if a map click misses |
| Musqueam | `<app-url>/?mode=forecast&area=musqueam` | Recovery |
| Offline | `http://localhost:4173/?mode=historical&month=2019-10` | Fallback when there is no network |

## Talk track

### 0:00–0:20 Hook (Speaker 1)

On screen: the start bookmark, the full map with no drawer.

> "Most maps of police data rank neighbourhoods against each other. That mostly shows where people live, work and shop. We asked a different question: is this month unusual for this neighbourhood? NeighbourCast compares every part of Vancouver only with its own history, and forecasts October with an honest uncertainty range."

### 0:20–1:30 Live demo (Speaker 1 talks, James clicks)

| Time | James clicks | Speaker 1 says |
|---|---|---|
| 0:20 | Nothing. Speaker 1 points at the map, then the legend. | "These are Vancouver's 24 police neighbourhoods in October 2019. Teal is below typical, grey is typical, amber is above typical, always relative to this area's own last three years." |
| 0:32 | **Play months**. After about 3 seconds, around mid-2020, **Pause**. | "Watch spring 2020. Almost every area drops below its own typical level. That's the pandemic, and nobody gets ranked." |
| 0:45 | **Forecast** | "Forecast mode: October 2026. VPD's data stops on September 25th, so we forecast October from data through August, two months ahead." |
| 0:55 | **Kitsilano** on the map. If the click misses, use "Choose from the list". | "Kitsilano: about [N] reported incidents, [tier] for Kitsilano. The bar is the 80% uncertainty range. The tick is the plain 12-month average we had to beat, shown on purpose. The chart is the last three years and where October lands." |
| 1:12 | The hatched **Musqueam** circle in the south-west | "Musqueam averages about two reported incidents a month. We'd rather say 'insufficient data' than invent a colour." |
| 1:20 | **How this works** | "Method, limitations, evaluation and sources all live inside the app." |
| 1:28 | Nothing | "Chibueze, what's underneath?" |

Fill in [N] and [tier] from the final build's drawer before 12:30 PM (see the checklist).

### 1:30–2:15 Technical (Speaker 2)

On screen: the How this works sheet stays open.

<!-- refresh from reports/evaluation.md -->
> "Under the map is every VPD record since 2003, and three traps nearly fooled us. VPD's all-years export is missing 2022 entirely, so we merged a separate download. Almost half the violent-offence rows look like duplicates, because VPD redacts them, so we kept every one. And September is only part-published, so we forecast from August. Then we tested a Poisson GLM and a Random Forest against three simple baselines on 20 held-out months, with the rule for picking the winner written down first. The GLM won, but by only 4% over a plain 12-month average, and in 2026 the average did better. So the app shows that average beside every forecast, and the range comes from our own backtest errors."
>
> Backup figures, only if asked: pooled MAE on the severity-weighted index is GLM 559.9, 12-month average 585.1, Random Forest 611.6. On the count it is 13.3 vs 13.7. The GLM is better in 14 of 24 areas. In 2026-01 to 2026-08 it scored 528.7 vs the average's 494.8. WAPE is 12.9%. The 80% range, fitted on 2025 errors, covered 79.7% of 2026 outcomes. Always guessing "below typical" would match 61.1% of tiers, beating every method (best 53.9%), so tier accuracy is never claimed as skill.

The one number to land is the gain over the plain 12-month average. Say it slowly.

### 2:15–2:40 Ethics (Speaker 1, unprompted)

Say the statement below word for word, before anyone asks.

### 2:40–3:00 Close (Speaker 1)

> "NeighbourCast asks one question, is this month unusual for this neighbourhood, and answers it with each area's own history, an honest forecast and its uncertainty. It's built for residents, visitors and community groups. Next, we want to put it in front of those groups and test whether it helps. We're Humberto, Chibueze, James and Andrew. Thank you. Happy to take questions."

## Ethics statement (verbatim, about 25 seconds)

> "A map like this could become a redlining tool, so we designed against that. These are reported incidents, which reflect what gets reported, not everything that happens. We never rank neighbourhoods: each colour compares an area only with its own history. Nothing goes below neighbourhood level, every forecast shows its uncertainty, and nothing feeds back into policing. And as VPD cautions, don't use this data to judge the safety of a specific location."

If a judge follows up on predictive policing: "Its harm comes from a feedback loop, where forecasts send patrols and patrols create more reports. NeighbourCast allocates nothing, so there is no loop."

## Q&A bank

Each answer takes about 15 seconds. The name in brackets is who answers.

1. **How accurate is it, compared with a baseline?** (Chibueze)
   Repeat the technical line, then add: "We fixed the rule for choosing the model before the final run, and we report the period where the average won. That's why the 12-month average sits beside every forecast."

2. **Why was 2022 missing?** (Humberto)
   "VPD's all-years export simply doesn't contain 2022. We spotted a 12-month hole in the monthly totals, downloaded 2022 on its own, and merged its 34,323 rows. Filling it with zeros would have looked like activity collapsing for a year."

3. **Why no street level?** (Humberto)
   "On purpose. VPD offsets property incidents to the hundred block and withholds violent-offence locations entirely. Street-level scores invite judgements about specific homes and people. Our smallest unit is a whole neighbourhood in a whole month."

4. **Why does Musqueam show no tier?** (James)
   "It averages about two reported incidents a month, so one extra incident moves it by 50%. Any colour would be noise. Areas averaging under 10 a month get 'insufficient data'. We keep it separate from Dunbar-Southlands rather than hiding it inside."

5. **What did ML add, if the baseline is that strong?** (Chibueze)
   "Honestly, little accuracy. It added a calibrated uncertainty range from backtest errors, month-of-year seasonality, and a fair, pre-registered test that tells you how much to trust it. Knowing that the baseline is strong is itself a result."

6. **Why not per capita?** (Humberto)
   "Census population counts residents, not who is actually there. Downtown has far more workers and visitors than residents, so per capita would mislead. It's also published for the City's 22 local areas, not VPD's 24. And since each area is compared only with itself, population mostly cancels out."

7. **How are the tiers defined?** (James)
   "Each month is compared with that area's own average over the previous 36 complete months. Within plus or minus 5% is typical; lower is below typical, higher is above typical. A busy area can be typical and a quiet one above typical. Nothing is ranked across areas."

8. **What does the range mean?** (Chibueze)
   "It's where 80% of outcomes should land. We took actual-over-forecast ratios from held-out months, used the 10th and 90th percentiles, and multiplied the forecast by them. So about one month in five lands outside, and the app says so."

9. **What would you do next?** (Humberto)
   "Put it in front of community groups and City staff and test whether 'unusual for this place' helps them. Then a weekly refresh from GeoDASH, per-type views, a correction for late-reported violent offences, and the clean table released as open data."

10. **Why these weights?** (Chibueze)
    "A plain count treats a bike theft and a break-in the same. We follow Statistics Canada's Crime Severity Index approach, where weights come from how often an offence leads to prison and for how long, so a break-in weighs about five times a theft. VPD publishes violent offences as one category, so they get one weight. The plain count is always shown beside the index."
    If pushed: "The weights live in one config file. Changing them re-runs everything in about 30 seconds, and the count never changes."

## Pre-demo checklist

### By 12:30 PM

- [ ] The final build is deployed. Open `<app-url>` in a private window and check that all 24 areas render in both modes.
- [ ] Open Kitsilano in forecast mode and write its [N] and [tier] into the demo script above.
- [ ] Check that **Play months** from October 2019 reaches mid-2020 in about 3 seconds and that spring 2020 turns mostly teal.
- [ ] Save all four bookmarks to the bookmarks bar.
- [ ] Rehearse the full 3:00 twice with the stopwatch. Rehearse Q&A once.

### Warm the app (2 minutes before each slot)

- [ ] Load `<app-url>`. If the deployed app uses the backend, open `<api-url>/health` and `<api-url>/forecast` once, so no cold start hits the judges.
- [ ] Load the start bookmark. The drawer is closed and playback is stopped.
- [ ] Browser full screen (F11), zoom 100%, other tabs closed, dev tools closed.
- [ ] Windows notifications off (Do not disturb), laptop on the charger, brightness up.

### Network

- [ ] Phone hotspot on, and the laptop has joined it once already.
- [ ] If the venue Wi-Fi is slow, switch to the hotspot before the judges arrive, not during the demo.

### Offline fallback

- [ ] In a spare terminal: `cd crime-tracker`, then `npm run build`, then `npm run preview` (static JSON, `VITE_API_URL` unset). Use the offline bookmark.
- [ ] Without a network the basemap tiles will not load, but the neighbourhood shapes, colours and drawer still work. Say so in one line and carry on.
- [ ] Last resort: the demo video MP4 saved on the desktop, ready to play full screen.

### Between judge groups

- [ ] Close the drawer, stop playback and load the start bookmark.
- [ ] Same speakers, same clicks, same order.
