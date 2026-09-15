# Commish Hub — CLAUDE.md

One page where Matt, as commissioner, publishes a weekly recap for every league he runs
and grabs a phone-sized image of it for the Sleeper group chat. Built 2026-09-09, the day
before the 2026 NFL season kicked off.

**Static HTML + vanilla JS, no build step, no npm.** The only external script is
`html2canvas` from cdnjs (the "Save image" button). Python is used offline for data prep
only, same carve-out as Draft Assistant and Kings Justice.

Hosting: **its own repo `bova4389/commish-hub`, GitHub Pages**, live at
https://bova4389.github.io/commish-hub/ (pushed 2026-09-09). The repo is
**public**: it carries Sleeper handles for every league, real names for 2 Mitchs 1 Cup
(Matt's call, same as `LEAGUE.md` in Draft Assistant), and deliberately savage commentary.
Don't re-litigate the names; don't add contact details of any kind.

## The four leagues

| Key | League (as named in Sleeper) | Kind | Names shown | What the recap is about |
|---|---|---|---|---|
| `kings_justice` | 🪓 The King's Justice (18 teams) | chopped — lowest score each week is eliminated, no matchups | Sleeper handle | who got chopped, who *barely* lived (roast them), who took the $25 weekly high, and **how the week unfolded slot by slot** — the Monday night saviors and failures |
| `two_mitchs` | 2 Mitchs 1 Cup (12 teams) | head-to-head | **real names** (map in `data/config.json`) | start/sit decisions, actual vs projected, points left on the bench, injuries, waivers |
| `infinity_war` | Infinity War (Sleeper spells it "Inifnity War") | classic pick'em, 8 picks a week, $20 weekly + season prize | Sleeper handle | the games, the upsets, the bad picks, who took the $20 (ties go to the MNF total-points tiebreaker, never split) |
| `deadpool` | Deadpool (20 entries, 2 revives) | survivor | Sleeper handle | who died and on what, the killer game, the consensus |

**The Other League is deliberately NOT here.** Its recaps live on its own site
(`Sleeper FF/The Other League/`); the hub only links out. Don't mirror them in.

## Files

```
index.html              the page: header, league tabs, week picker, card, evidence panels
css/hub.css             one stylesheet, dark, mobile first; --accent is set per league
js/hub.js               the renderer (plain script, no modules)
data/config.json        league ids per season, display names, accents, payouts, the OTL link
data/<season>/index.json      which weeks have been built (Pages can't list a folder)
data/<season>/week-NN.json    THE FACTS for one week, all four leagues  <- build_week.py
recaps/<season>.json    THE WORDS, hand-written, keyed league -> week
scripts/build_week.py   pulls the week from Sleeper/ESPN, writes the facts file
scripts/_cache/         cached API responses (gitignored)
```

## The Tuesday routine (how a week gets recapped)

1. **Pull the facts.** Always `--refresh` for the live week — the cache is only for finished weeks.
   ```bash
   python scripts/build_week.py --week N --refresh
   ```
   It prints whether the NFL week is final. If it isn't, the file is marked `provisional`, the
   card says so, and no chop/winner is treated as confirmed.
2. **Read `data/2026/week-NN.json`** and write four entries into `recaps/2026.json`
   (`leagues.<key>.<week>`): `headline`, optional `facts` (3–5 `{k, v}`; omit to auto-build from
   the data), `paragraphs` (2–3, ~200 words). Every number must trace to the facts file.
3. **Check it in the browser** (`commish-hub` in the workspace `.claude/launch.json`, port 8799),
   phone width, every tab.
4. Commit and push. Pages serves it. Open the tab, **Save image** (or **Preview image** and
   long-press on a phone), post the PNG to the league chat.

The card is what gets screenshotted, so **it has to stand alone**: league name, week, headline,
facts strip, paragraphs, provisional flag. Everything under it is evidence for the writer and
for anyone who wants to argue.

## Voice

Same register as The Other League's Phase 8/9 write-ups: **Hall of Fame & Shame roast level,
punch at the decision, not the person.** Matt is `avobttam` and is in every one of these
leagues; roast his weeks on the same terms as everyone else's. Per league:

- **King's Justice** — the survivor who scraped by gets it worse than the corpse. The weekly
  high gets a genuine compliment and a reminder that it paid $25. Use the chop-seat timeline:
  who was lowest after each window, how many players they had left, what Monday did. The
  script gives every alive team's running total per kickoff slot and the last-slot players.
- **2 Mitchs** — bench points, zeros started, injured starters, proj-vs-actual **net of
  `proj_bias`** (Sleeper's projections run hot by a different amount each week; the raw delta
  is not the story). One roast and one real compliment every week, per `LEAGUE.md` §13.
- **Infinity War** — the $20 is won by being different *and* right: `lonely_wins` is the stat.
  Chalk that burned, upsets and how many saw them coming. **The weekly $20 is never split.**
  A tie on correct picks goes to the tiebreaker (guess closest to total points in the Monday
  night game); if that is tied too, the pot rolls to next week. The script writes `winners`
  (0 or 1), `tied`, `tiebreak` (actual total + each tied guess), `rollover` and `pot` (which
  carries a previous week's rolled pot forward).
- **Deadpool** — bodies, the game that did it, whether the consensus pick got everyone killed.
  A "loss" with revives left is a strike, not a death; the card says `strikes`.

## Things that will bite

- **The kickoff gate.** Sleeper's API hands over pick'em picks days before kickoff; its app
  does not. `build_week.py` records a pre-kickoff pick only as "made" (`hidden: true`, no team),
  and the page shows a padlock. **This file is committed to a public repo — never remove the
  gate**, and don't build the live week on a Sunday morning expecting to see picks.
- **Pick'em GraphQL needs Matt's Sleeper login token (since 2026-09-15).** Unauthenticated
  calls now return `Unauthorized`, even for 2025 leagues that worked in testing, so Infinity War
  and Deadpool fail while King's Justice and 2 Mitchs (REST) still build. The script reads
  `SLEEPER_TOKEN` or `scripts/.sleeper_token` (gitignored; never print, commit or paste it in
  chat). Matt copies it from sleeper.com → F12 → Network → a `graphql` request → the
  `authorization` request header. It expires; a "token rejected" error means copy a fresh one.
  Notepad saves it as `.sleeper_token.txt` unless told otherwise, which reads as "no token found".
- **Sleeper's `outcome` on a pick is always `"win"`.** It is the pick type, not a result. Picks
  are graded in the script against ESPN finals. `points_by_leg` / `lost_leg_ids` on the roster
  are Sleeper's own grading and agree (checked on 2025 week 5: 10 losses, same ten people).
- **`is_eliminated` and `points_by_leg` are current state, not history.** For the *current* week
  they are the truth. For a past week the strike counts are recomputed from `lost_leg_ids` but
  ALIVE/OUT reflects today. The hub is a current-week tool; old weeks are an archive.
- **King's Justice alive signal** is `roster.settings.eliminated` = the week that roster was
  chopped (2025+ leagues, which use Sleeper's native chopped format). Chopped rosters keep
  appearing in every later week's matchups at 0.0 — the script only ranks teams alive going in.
- **A player's kickoff slot comes from the projections feed** (`team` + `game_id` for that exact
  week), not from the roster, so a mid-season trade lands in the right game. DEF ids are the team
  code. A player with no game that week has `slot: null` and is listed under `no_game`.
- **Kickoff slots are distinct kickoff times**, labeled in Eastern ("Sun 4:25 PM"). Two Monday
  games are two slots — which is the point.
- **Odds** come from Bova's Picks' snapshots at `../NFL Pickems/data/odds/history/`, last
  snapshot before kickoff. If that folder is missing, nothing breaks; games just have no
  favorite and no upset flag. 2025 has no odds, which is why the 2025 sample shows none.
- **ESPN spells Washington `WSH`**; everything here uses Sleeper's `WAS`. Sleeper spells
  Jacksonville `JAX`. Don't add a second crosswalk.
- **The projections list endpoint is the one that works:**
  `https://api.sleeper.app/projections/nfl/<season>/<week>?season_type=regular&position[]=QB&...`
  It is undocumented and ~2 MB. The `/v1/projections/nfl/regular/<season>/<week>` form returns a
  bare stats dict with no team or game id and is not enough for the timeline.
- **Testing without 2026 data.** `--season 2025 --override two_mitchs=<id> --override deadpool=<id>`
  points a league at a stand-in Sleeper league (The Other League's 2025 id
  `1196516179326291968`, East Orange Squeeze 2025 `1259331335542030336`). That is how the
  h2h and survivor builders were verified before week 1 existed. The King's Justice 2025 id is
  real and stays in config as an archive.

## Cache busting

GitHub Pages sends `max-age=600` on everything and there is no `.htaccess`. `index.html`
references `css/hub.css?v=YYYYMMDD` and `js/hub.js?v=YYYYMMDD`; **bump both on every change**
per the workspace rules (same-day → add a letter). Data files are fetched with a one-minute
buster in `hub.js`, so a fresh facts file or recap shows within a minute of the push.

## Deploy

Live since 2026-09-09 at https://bova4389.github.io/commish-hub/ — GitHub Pages from
`main` / root, `.nojekyll` in place. Push to `main` and the site updates within a minute or
two; the page fetches data files with a one-minute cache buster, and `?v=` on the CSS/JS must
be bumped when those change.

## Not built yet

- Week 1 of 2026 was the first real run (2026-09-15). Infinity War and Deadpool grading was
  re-checked pick by pick against ESPN finals that day: 164 picks, 0 mismatches.
- Sleeper's `injury` field on a starter is *today's* status, not game-day: Zay Flowers showed
  "Out" after scoring 26.0 in week 1. Don't write "started an injured player" off it alone.
- No automation. A GitHub Action could run `build_week.py` on Tuesday mornings like The Other
  League's bot does; the prose still has to be written by hand, so it was left manual.
- The King's Justice history dashboard (`Kings Justice/dashboard.html`) is separate. The hub's
  KJ tab is the *weekly* view; the dashboard is four seasons of FAAB history. Link, don't merge.
