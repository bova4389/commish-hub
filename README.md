# Commish Hub

Weekly recaps for four Sleeper leagues, one page, one shareable card per league per week.

- **The King's Justice** — chopped league. Who got the axe, who barely lived, who took the $25.
- **2 Mitchs 1 Cup** — head-to-head. Start/sit crimes, bench points, projections vs reality.
- **Infinity War** — 8-pick pick'em. Upsets, bad picks, who took the $20 (ties go to the MNF total-points tiebreaker, never split).
- **Deadpool** — survivor. Who died and on what.

Static HTML and vanilla JS. The numbers are pulled from Sleeper and ESPN by
`scripts/build_week.py`; the words are written by hand into `recaps/<season>.json`.

```bash
python scripts/build_week.py --week 3 --refresh      # the week's facts (+ the season rollup)
python scripts/build_waivers.py --refresh            # the waiver analysis (Wednesdays, automated)
```

Then open the page, pick the league, hit **Save image**, post it to the chat.
Every table under the recap has its own **Save image** button too, and the
saved picture carries the league and week so it makes sense on its own.

The **Season totals** button beside the week picker swaps the weekly recap for
the cumulative views, each with its own Save image button:

- **Infinity War** — money won week by week, and correct picks week by week,
  with gold and silver trophies in the week-18 column for the $380 / $160
  season prizes (dimmed until the season is actually over).
- **The King's Justice** — the $25 weekly high, week by week, and the season
  total.
- **The King's Justice** — the waiver wire (this is the only league it runs for;
  flip `"waivers": true` in `data/config.json` to add another). **Money wasted at
  auction**
  gets its own savable grid: pay $400 for a player whose next-best bid was $150
  and $250 of that bought nothing, tracked week by week and cumulatively. An
  uncontested claim counts in full — nobody else bidding means $0 would have won
  him — and only a free $0 pickup is excluded. Plus
  spend, what each claim actually returned in started lineups, who keeps getting
  outbid, spend by the player's original draft round and by position, and the
  season's best and worst spenders — those awards are handed out at the end of
  the season, since a player picked up this morning has not had a chance to
  perform yet. **Rebuilt automatically every Wednesday at
  8am ET** by `.github/workflows/waivers.yml` — after Sleeper has processed the
  week's claims, so they are in it.

```bash
python test/test_waivers.py                          # fixture test, no network
```
