# Demo video script: NeighbourCast

- **Target length:** 2:40. The hard limit is 3:00, and the video is mandatory on Devpost.
- **Voices:** Humberto reads shots 1–6, 9 and 10. Chibueze reads shots 7 and 8, as in the live pitch.
- **Upload by 11:15 AM** so YouTube finishes processing before the 11:40 AM submit target. The deadline is 12:00 PM PDT.

## Overview

| # | Time | Shot | Criterion it serves |
|---|---|---|---|
| 1 | 0:00–0:14 | Hook over the full map | Originality, pitch |
| 2 | 0:14–0:28 | Map and legend | Design |
| 3 | 0:28–0:42 | Play months through 2020 | Design |
| 4 | 0:42–0:54 | Switch to forecast | Technical complexity |
| 5 | 0:54–1:18 | Kitsilano drawer | Design, technical complexity |
| 6 | 1:18–1:30 | Musqueam, insufficient data | Design |
| 7 | 1:30–1:50 | Pipeline and data traps | Technical complexity |
| 8 | 1:50–2:14 | Evaluation against the baseline | Technical complexity |
| 9 | 2:14–2:30 | Responsible design | Pitch, originality |
| 10 | 2:30–2:40 | Phone view and end card | Design, pitch |

## Before recording

- **Source:** the deployed app at `<app-url>`. Otherwise use a production build on localhost: `cd crime-tracker`, `npm run build`, `npm run preview`, then open http://localhost:4173.
- **Screen:** 1920x1080, browser full screen (F11), zoom 100%, bookmarks bar and extensions hidden, notifications off, cursor visible.
- **Start state:** `/?mode=historical&month=2019-10`, with the drawer closed.
- **Recording tool:** OBS Studio (display capture, 1080p, 30 fps), or Xbox Game Bar (Win+Alt+R records the active window).
- **Editing:** Clipchamp, which is built into Windows 11, or any editor you know.
- **Graphics for shots 7 and 8:** screenshots of the architecture block in `README.md` and, from `reports/evaluation.md`, the "Model decision" table, the weighted-index results table and the "predicted chance of 'above'" reliability table under "Probabilities instead of tiers", all as rendered on GitHub. The numbers in them are final.
- **Kitsilano figures (shot 5):** from `ml/outputs/forecast_2026-10.json`: about 97 reported incidents, severity-weighted forecast 4,710 with an 80% range of 3,102 to 6,445, and chances of 56% above its usual October level, 19% below and 25% within 10% of it (`p_above` 0.563, `p_below` 0.193, `p_within` 0.244, rounded by the drawer to add to 100). Check that the final build's drawer shows the same before recording.
- Record each shot as its own clip, with two takes. Record the voice-over separately in a quiet room, then trim the clips to the timings.
- If time runs short, record the whole thing in one take with live narration over the app. A plain video beats a missing one.

## Shot list

### Shot 1: hook (0:00–0:14)

- **On screen:** the full map in historical mode, October 2019. A "NeighbourCast" title overlay for the first 3 seconds.
- **Voice-over:** "Most maps of police data rank neighbourhoods against each other. That mostly shows where people live, work and shop. We asked a different question: is this month unusual for this neighbourhood?"

### Shot 2: the map (0:14–0:28)

- **On screen:** hover over two or three areas so the hover card shows each one's deviation from its usual level, then rest the cursor on the gradient legend (30% below usual to 30% above usual).
- **Voice-over:** "NeighbourCast maps Vancouver's 24 police neighbourhoods, month by month, from 2003 to August 2026. Each colour compares an area only with its own usual level, the same month a year earlier: teal lower, amber higher, grey about the same. No labels, no ranking."

### Shot 3: playback (0:28–0:42)

- **On screen:** click **Play months** at October 2019. Click **Pause** around June 2020 and hold on the mostly teal map.
- **Voice-over:** "Press play and watch 2020. From May, most areas drop below where they were a year earlier. That's the pandemic, shown without ranking anyone."

### Shot 4: forecast mode (0:42–0:54)

- **On screen:** click **Forecast**. The map recolours and the month label reads October 2026.
- **Voice-over:** "Forecast mode shows October 2026. VPD's data stops on September 25th, so we forecast October from data through August, two months ahead."

### Shot 5: one neighbourhood (0:54–1:18)

- **On screen:** click **Kitsilano**. The drawer opens. In the edit, zoom in on the forecast number, then the range bar with its 12-month average tick, then the chances bar (teal, grey, amber) and the sentence under it, then the sparkline.
- **Voice-over:** "Kitsilano: a severity-weighted forecast, about 97 reported incidents, and an 80% uncertainty range. That tick is the plain 12-month average our model had to beat; we show it on purpose. Then the chances: 56% that Kitsilano ends above its usual October level, 19% below. Chances, not a label, because our error is wider than the 10% band."

### Shot 6: small areas (1:18–1:30)

- **On screen:** click the hatched **Musqueam** circle in the south-west. The drawer reads "Too few reported incidents here to forecast meaningfully".
- **Voice-over:** "Musqueam averages about two reported incidents a month. That's too few to compare, so it says insufficient data instead of inventing a colour."

### Shot 7: pipeline and data traps (1:30–1:50)

- **On screen:** the architecture diagram, then the cleaning-steps table from `data/README.md`. Optional overlay: "2022 missing from the all-years export", "42% of violent-offence rows are redacted copies", "September 2026 is partial".
- **Voice-over:** "Behind the map is VPD's open data since 2003. Their all-years export is missing 2022, so we merged a separate download. 42% of violent-offence rows look like duplicates because VPD redacts them, so we kept every one. That gives 942,457 incidents across 24 neighbourhoods and 285 months."

### Shot 8: evaluation (1:50–2:14)

- **On screen:** the "Model decision" table (five candidates, none qualifies), then the weighted-index results table with the `mean_12` and `C0 poisson_glm (reference)` rows highlighted, then the "predicted chance of 'above'" reliability table with its 80-100% row highlighted (the 2025->2026 columns).
  - Overlay over the results table: "Pooled MAE: GLM 713.1 vs 12-month average 745.5 (4.3% lower). In 2026 alone: 673.1 vs 630.2. 80% range covered 79.7% of 2026."
  - Overlay over the reliability table: "Built from 2025, checked on 2026: said 80–100% chance above, happened 90%. Ranked probability score 0.173 vs 0.241 for base rates (28% better)."
- **Voice-over:** "We wrote down a rule first: a new model ships only if it beats our Poisson GLM by at least 1%. Five alternatives failed. The GLM beats a plain 12-month average by only 4%, so we show both. The chances come from our own past errors, checked on a year they weren't built from: when we said 80 to 100%, it happened 90% of the time."

### Shot 9: responsible design (2:14–2:30)

- **On screen:** click **How this works** and scroll slowly through "What it does not do" and "Limitations".
- **Voice-over:** "We designed against misuse. These are reported incidents, not everything that happens. No neighbourhood is ranked, nothing goes below neighbourhood level, and every forecast shows its uncertainty. As VPD cautions, don't use this data to judge the safety of a specific location."

### Shot 10: phone and end card (2:30–2:40)

- **On screen:** the app on a phone, or the browser's device mode at 375 px wide, showing the bottom sheet. Then an end card:
  - NeighbourCast · `<app-url>` · github.com/Andrew4436/storm-hackathon-2026
  - Humberto, Chibueze, James, Andrew · StormHacks 2026
  - Data: VPD GeoDASH open data; boundaries: City of Vancouver Open Data. Not affiliated with the Vancouver Police Department.
- **Voice-over:** "NeighbourCast: is this month unusual for this neighbourhood? Built at StormHacks 2026 by Humberto, Chibueze, James and Andrew."

## Export and upload

1. Export as MP4, 1080p, 30 fps. Check that the length is 3:00 or less.
2. Go to YouTube Studio (studio.youtube.com) and choose **Create**, then **Upload videos**.
3. Title: "NeighbourCast: StormHacks 2026 demo".
4. Description: the elevator pitch from `docs/DEVPOST.md`, the repo link, and "Data: VPD GeoDASH open data and City of Vancouver Open Data. Not affiliated with the Vancouver Police Department."
5. Audience: "No, it's not made for kids".
6. Visibility: **Unlisted**. Save.
7. Wait until processing finishes. HD can take a few minutes longer than SD.
8. Copy the link. Open it in a private window, logged out, and confirm it plays.
9. Paste the link into the Devpost "Video demo link" field, then check the project preview shows the player.
10. Keep the MP4 on the demo laptop's desktop as the last-resort fallback for live judging.
