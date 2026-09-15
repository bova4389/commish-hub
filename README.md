# Commish Hub

Weekly recaps for four Sleeper leagues, one page, one shareable card per league per week.

- **The King's Justice** — chopped league. Who got the axe, who barely lived, who took the $25.
- **2 Mitchs 1 Cup** — head-to-head. Start/sit crimes, bench points, projections vs reality.
- **Infinity War** — 8-pick pick'em. Upsets, bad picks, who took the $20 (ties go to the MNF total-points tiebreaker, never split).
- **Deadpool** — survivor. Who died and on what.

Static HTML and vanilla JS. The numbers are pulled from Sleeper and ESPN by
`scripts/build_week.py`; the words are written by hand into `recaps/<season>.json`.

```bash
python scripts/build_week.py --week 3 --refresh
```

Then open the page, pick the league, hit **Save image**, post it to the chat.
