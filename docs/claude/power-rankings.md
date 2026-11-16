# Power Rankings and Playoff Odds — Commish Hub reference

Moved verbatim out of `CLAUDE.md` on 2026-11-11 so it loads only when needed. A cross-reference to another section may now point to a different `docs/claude/` file; grep the folder for the heading.

## Power rankings and playoff odds (2 Mitchs, since 2026-10-12)

`scripts/outlook.py` adds `leagues.<key>.outlook` to the week file for every h2h league with
`"outlook": true` in `data/config.json` (only `two_mitchs` today). `build_week.py` calls it for
**final weeks only**, so the 5am Action produces it with everything else. The page draws a
**Power rankings** and a **Playoff odds** panel under Standings, and adds "Power #1" and "Title
favorite" to the card facts. The `2-mitchs-1-cup` Tuesday task copies the same numbers into
`LEAGUE.md`, so the two never disagree.

- **Power rankings use results only:** all-play win % 50%, points per game 30%, last three weeks'
  PPG 20%, as z-scores. `luck` = actual wins minus all-play rate × games. `prev_rank` is the same
  calculation through the previous week.
- **Odds are a Monte Carlo** (10,000 seasons, about 10 seconds): current rosters, Sleeper's
  projection for every remaining week rescored with the league's scoring, best lineup *by
  projection*, empty slots streamed at 80% of the best free agent, real schedule to week 14, top
  6 on wins then points, real bracket (wk 15: 3v6, 4v5; wk 16: 1 and 2 enter; wk 17 final).
  Every game gets a random swing; **without it every team is 0% or 100%**.
- **The odds ALWAYS publish (owner, 11/16/2026), every season, every final week from week 1
  through week 14.** They are there for fun; a high-variance number beats an empty table. Until
  that date a calibration gate hid them whenever the simulated weekly swing left 25-28%, which
  hid them every week from 6 through 9 of 2026 and nobody saw them all year. **Don't reinstate
  the gate, and don't write "held back" in a recap.** `odds.in_band` and `calibration` are still
  written as diagnostics: when `in_band` is false the panel adds one "grain of salt" line, and
  the recap may mention it in a clause, but the table and the numbers still go out.
  `TEAM_CV` is 0.17: 0.16 read 24.8% at the low end, 0.18 read 28.2% at the top.
- **The seed is season×100+week**, so a rerun on the same Sleeper data gives the same numbers.
  Sleeper's projections do move during the week, so a Tuesday-afternoon rerun can differ by a
  point or so from the 5am build. The bot's file wins (see the Tuesday routine).
- **2026 weeks 1-4 carry power rankings only** (`odds: null` with `odds_note`), because the model
  didn't exist yet. From 2027 the odds start with week 1. A past week's odds
  can't be rebuilt honestly: Sleeper only serves today's rosters and projections. To backfill or
  repair a week's power rankings without touching its other facts:
  `python scripts/outlook.py --week N --no-odds`. Without `--no-odds` it rewrites the odds too.
- **After week 14** the seeds are real and only the bracket (weeks 15-17) is simulated: playoff %
  is 0 or 100, `calibration` is null, and the title odds are the story for that recap. From week
  15 on nothing runs (`odds_note` says the playoffs are under way).

## Odds through the season — the line chart (since 11/16/2026)

The **Odds through the season** panel draws one line per team, weeks across. It sits under
Playoff odds on every 2 Mitchs week (showing weeks up to that one) and in that league's Season
totals view (all weeks). A toggle at the top switches **Make playoffs / Win it all**.

- It reads `season.json` → `odds_history.<league>` (`names`, and `weeks.<N>.<handle>` =
  `[playoff, title]`), written by `build_season.py` from each week file's `outlook.odds`, so it
  never loads a dozen week files. Any league with `"outlook": true` gets it, any season.
- **Twelve colored lines can't be read**, so every team is a gray line and up to four picked teams
  get a color (from the dataviz skill's dark categorical slots 1-4). Colors go by pick order and
  stay put while picked. Default: the top three by title odds. The chips under the chart are the
  legend and the picker, and show each team's number.
- Tapping or hovering the plot moves a dashed rule to the nearest week, and the chips switch to
  that week's numbers. A floating 12-row tooltip was taller than the chart on a phone and hid
  the lines it described, which is why it isn't one.
- The toggle is hidden in a saved image; the panel title says which odds it shows.
