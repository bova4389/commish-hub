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
- **Calibration gate:** simulated team weekly scores must swing 25-28% (sd/mean). `odds.in_band`
  false means the page shows "held back" instead of the table, and the recaps say so.
  `TEAM_CV` is 0.17: 0.16 read 24.8% at the low end, 0.18 read 28.2% at the top.
- **The seed is season×100+week**, so a rerun on the same Sleeper data gives the same numbers.
  Sleeper's projections do move during the week, so a Tuesday-afternoon rerun can differ by a
  point or so from the 5am build. The bot's file wins (see the Tuesday routine).
- **Weeks 1-4 carry power rankings only** (`odds: null` with `odds_note`). A past week's odds
  can't be rebuilt honestly: Sleeper only serves today's rosters and projections. To backfill or
  repair a week's power rankings without touching its other facts:
  `python scripts/outlook.py --week N --no-odds`. Without `--no-odds` it rewrites the odds too.
- Odds aren't simulated once week 14 is final (`odds_note` says so); the bracket is set by then.
