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
data/<season>/season.json     the week rollup the cumulative grids read  <- build_season.py
data/<season>/waivers.json    season-long waiver analysis  <- build_waivers.py (Wed cron)
recaps/<season>.json    THE WORDS, hand-written, keyed league -> week
scripts/build_week.py   pulls the week from Sleeper/ESPN, writes the facts file
scripts/build_season.py folds every week file into season.json (run by build_week.py)
scripts/build_waivers.py  the waiver wire analysis; Sleeper REST only, no token
scripts/_cache/         cached API responses (gitignored)
test/test_waivers.py    fixture test for the waiver metrics -- no network
.github/workflows/waivers.yml   Wednesday 11am ET waiver refresh
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

## Every table saves as an image

Added 2026-09-16 at the owner's request: **every panel on the page has its own Save image /
Preview image pair**, not just the recap card and the season grids, because any one of them
may be the thing worth posting to a league chat. `panel()` does it, so a new panel is
shareable without doing anything.

- **On the page a panel looks unchanged.** The league/week header and the footer are
  `.ex-only` and appear only in the exported image -- an image posted to a chat has no page
  around it and has to say which league and week it is. The buttons are hidden in the export.
- **A panel exports at 720px, widened to its widest table** (`fitPanel()`), so a wide table
  comes out whole instead of cropped to a phone's viewport. It is measured rather than set to
  `max-content`, which would lay a wrapping row of pick chips or a long dek out on one line.
- **Ids come from the title** (`p-lonely-winners`), so the saved file is named
  `<league>-<season>-week-1-lonely-winners.png` or `...-season-waste.png`. `PANEL_IDS` resets
  on every render and a repeated title gets `-2`.
- **`{ share: false }`** on a panel that is a message rather than numbers (the "no waiver
  analysis built yet" notice). Nobody posts that.
- The weekly footer carries **PROVISIONAL** when the week is not all final, same as the
  recap card, so a mid-week image cannot pass for a result.

## Season totals -- the cumulative grids

Added 2026-09-15. A **Season totals** button beside the week picker (hash
`#<league>/<season>/season`) swaps the weekly recap card for the cumulative
views. It stays a *view* of the same league rather than a new tab, because row 1
of the nav is the size of the *leagues*, not the count of views.

**It was a dropdown option only, for one day, and that was a mistake.** The
cumulative views existed, were deployed and were correct, and the owner reported
not seeing them on the site at all -- because "Season totals" was the last entry
in a `<select>` full of week numbers and nothing suggested looking there. A
feature nobody can find is a feature that does not exist. The toggle
(`#btn-season`, `paintViewToggle()`) is now the signpost: it reads
**Season totals** / **Back to a week**, highlights when on, and greys the week
picker out while it is, since a week number means nothing to a season total.
The dropdown option is kept so existing `#.../season` links still resolve, but
nothing depends on anybody finding it. **Do not demote this back into the
dropdown.**

Three grids, all the same shape -- **weeks across, entries down, season total in
the last column** -- and all drawn by one `grid()` helper that takes
`cell(row, week)` and `total(row)` callbacks. A fourth cumulative table is a few
lines, not another copy of the sticky-column markup.

| Grid | League | A cell holds |
|---|---|---|
| Money won | Infinity War | the weekly $20 (plus any rolled-in pot) on the week they took it |
| Correct picks | Infinity War | that week's correct count; highlighted if it tied or set the week's best |
| Weekly high money | King's Justice | the score that won the $25, blank on every other week |

Each sits in a `.sharecard` with its **own** Save image / Preview pair, because
these get posted to the chat on their own rather than as part of a weekly
recap. The buttons are handled by one delegated listener on `#evidence`, so
adding a card costs no wiring.

Things in here that are decisions, not details:

- **The cumulative views read `season.json`, never the week files.** A
  `week-NN.json` is ~250 KB; eighteen of them is 4.5 MB and the page would be
  unusable on a phone by December. `scripts/build_season.py` carries only the
  fields these grids read -- a few KB for a whole season -- and **build_week.py
  runs it at the end of every run**, so it cannot go stale relative to the weeks
  on disk. It calls no API and invents nothing.
- **The last column is sticky to the right, the name column sticky to the
  left.** The total is the answer and the weeks are the working; without the pin
  the one column anybody reads first is the one off the edge of a phone. That is
  also why `.gridwrap` does NOT bleed to the card edge the way `.tbl-wrap` does:
  `right: 0` resolves against the scrollport, so a negative margin pins the
  total outside the card and lets the next week's column show in the gap beside
  it. Hit and fixed the day it was built.
- **Infinity War always carries a week-18 column, played or not**, because that
  is where the season trophies go and seeing them coming is the point. While the
  week is still ahead the column is amber-tinted and the trophies are dimmed --
  they are where it stands today, never a result. `iwSeason()` unions the built
  weeks with `last_week` for this; every per-week read tolerates a column with
  no week behind it. The first version derived its columns from the built weeks
  alone and the trophies silently never rendered.
- **The trophies rank on cumulative CORRECT PICKS**, and they appear on *both*
  Infinity War grids, because the season money IS that ranking -- showing them
  apart would invite two different answers. $380 to first, $160 to second
  (owner, 2026-09-14; also recorded in Bova's Picks). **A tie at the top is
  reported and never resolved**: the pool has no season tiebreaker on record.
  Ask and write the answer here the first time it happens.
- **The weekly pot is never split, so money is just `pot` to `winners[0]`.**
  `pot` already carries any rolled-over money in, and a rollover week pays
  nobody -- do not also add `pot_carried` anywhere or a rolled week pays twice.
- **King's Justice shows the weekly $25 only.** Its season prizes ($350 / $150)
  are deliberately NOT on that table: the league is chopped, so first and second
  are settled whenever the field gets down to two, not in week 18. (Owner's
  call, 2026-09-15.)
- **A King's Justice cell is blank unless that team won the week.** Eighteen
  columns of everyone's score would be a heat map nobody can find themselves in.
- **Per week / Running total is a toggle, not two tables.** Both readings of
  "cumulative" are legitimate and the toggle is ten lines.
- **Every money grid is sorted highest-total-first and hides its $0 rows by
  default.** Sorted that way the $0 rows are a block of nothing at the bottom,
  which is dead weight in a shared image. `grid()` takes an `isZero(row)`
  predicate; the button is labelled with the count (`Show 10 $0 rows`) so the
  filter's state is never a guess, and it **never filters down to an empty
  table** -- a grid with no rows reads as broken data rather than as a filter
  working. The picks grid deliberately has no such button: a 0 there means
  "submitted no card", which is worth seeing.
- **A card with rows hidden says so in its own footnote.** An export drops the
  controls (`.sharecard.exporting .gctl { display: none }`), so without
  `hiddenNote()` a saved image would quietly claim the league is smaller than it
  is. **A tied trophy does not save a row from the filter** -- a tie is not
  money, and the tie note above the grid says so either way.
- **The `$0` button is a standalone control, not a third segment of the
  per-week/running pair.** It answers a different question, and as one
  three-across group the two would read as one three-way choice.
- **`#evidence`'s delegated listener matches on `[data-save],[data-preview],
  [data-gmode],[data-zero]`.** Adding a control means adding its attribute to
  that selector -- the first version of the `$0` button handled `data-zero`
  inside the callback but left it out of the `closest()` call, so it silently
  did nothing.
- **`.sharecard.exporting` widens the card to `max-content` and unclips the
  scroller**, which is what makes an 18-week grid come out whole instead of
  cropped to the phone's viewport (measured: 1508px for the money grid). The
  prose blocks keep a 760px measure inside it, because text set 1500px wide is
  unreadable in a chat image.
- **Sleeper keeps its own running pick total and the page cross-checks it.**
  Ours is graded from ESPN finals. They have agreed so far; if they ever part,
  `pickCheck()` says so on the card rather than quietly showing one of two
  numbers.

## Waiver wire analysis

Added 2026-09-15. `scripts/build_waivers.py` -> `data/<season>/waivers.json`,
rendered under **Season totals** for **King's Justice only**.

**It is opt-in, via `"waivers": true` in `data/config.json`** (owner's call,
2026-09-16). `build_waivers.py` skips any league without the flag and
`renderSeason()` reads the same field, so the script and the page can never
disagree about which leagues have a wire — and adding one is a line of config,
not a code change. King's Justice is the FAAB league the analysis is about
($1000 budgets, 28 claims and 42 failed bids in week 1 alone); 2 Mitchs was
included at first and its seven $0-to-$15 claims were noise sitting beside it.
A pick'em or survivor pool has no players to claim at all.

**It runs on `.github/workflows/waivers.yml`, Wednesdays at 8am ET** (owner's
call, 2026-09-16) -- after Sleeper has processed the week's claims, so the
analysis on the hub includes them. **Do not move it earlier in the week:** a
Tuesday run was tried for one commit and is complete only through *last*
Wednesday's waivers, which is correct but omits the bids for the week about to
start -- exactly the ones anybody reading it on a Wednesday wants to see.

Everything it reads is **Sleeper REST and keyless**:
it deliberately never touches the pick'em GraphQL, so an expired Sleeper login
can never break this job. That is the reason it is its own script rather than a
branch of `build_week.py`.

The four metrics, defined here because they are easy to re-derive differently:

| Metric | Is |
|---|---|
| **spent** | sum of WINNING bids. A failed claim costs nothing. |
| **waste** | **the headline number.** The winning bid minus the next-best bid on that player, on **every** claim. Bid $400 against a next-best $150 and you own the player either way, so $250 went in the bin. Tracked per week AND cumulatively, because the season figure is the one that settles an argument. |
| **waste_solo** | the part of waste that came from **uncontested** claims, so "paid over the odds in a bidding war" can be told apart from "paid for a player nobody wanted". |
| **return** | the player's points in the weeks **strictly after** the claim, split into points actually STARTED by the winner and points merely ROSTERED. A guy you paid for and benched got nothing out of the money either. Sleeper's own `players_points` is already scored through the league's settings. |
| **shut out** | failed claims: how many, how much was bid and lost, and the current run of weeks bidding with nothing to show. |

**An uncontested claim is wasted IN FULL, and the only exclusion is a $0
pickup** (owner's call, 2026-09-15). $100 for a player nobody else bid a cent on
is $100 that a $0 claim would have won. **This reverses an earlier version of
this file**, which counted uncontested claims as wasting nothing on the
reasoning that there is no runner-up to measure against; the owner's position is
that $0 *is* the runner-up, which is also what the arithmetic already said
(`bid - (runner_up or 0)`). Do not re-litigate it back. A $0 pickup falls out on
its own — $0 − $0 — and is counted separately as `free_claims` rather than
special-cased.

**`waste_rate` is waste over TOTAL spend**, not over contested spend, now that
waste is measured on every claim. It needs $10 of spend to be reported at all,
and the sharpest/loosest awards are only both shown when they are two different
people.

**A contested claim whose loser bid $0 has waste equal to the full bid**, the
same as an uncontested one, which is the consistent answer rather than a leak:
$0 is the real reference price either way.

- **`week_transactions()` in build_week.py now keeps every losing bid, bidder and
  all.** It used to throw them away and keep only the runner-up *amount*. Sleeper
  returns failed claims alongside the winning one, and they are the only record
  of who keeps getting outbid -- the whole "who continues to lose out" half of
  this rests on it. **Do not narrow it back.**
- **ONE BID PER ROSTER, and this is the subtle one.** Sleeper returns *more than
  one transaction for the same roster and player*: the completed claim plus a
  superseded, non-complete record of the same bid. Treating every transaction as
  its own bidder makes **the winner its own runner-up**, and the claim then
  reports $0 wasted precisely when it walked the field. Found by the owner on
  2026-09-16: his $169 Joe Burrow claim came back carrying a $169 "losing" bid
  from himself, which hid a **$158 overpay** over the real runner-up at $11 and
  crowned him *Sharpest bidder* at 0% waste. Two of 28 claims were affected and
  league waste was understated by $158 ($696 against $854).
  `week_transactions()` now collapses bids per `roster_id` before picking a
  winner: the record that actually processed is the price paid, a roster that
  never won keeps its highest bid, and `others` excludes the winning roster by
  id rather than by "did not win". `bidders` counts rosters, not transactions.
  **Reverting this reintroduces a silent understatement of the headline number**
  -- `test_waivers.py` carries the exact Sleeper shape and 18 assertions fail
  without the fix.
- **Spend is bucketed by the acquired player's original round in THIS LEAGUE'S
  OWN draft** (`undrafted` is its own bucket) -- the "what the room paid in
  August against what it pays in October" read the owner asked for. It is not the
  NFL draft.
- **The ROI AWARDS are end-of-season; the ROI TABLE is weekly.** `best_value`,
  `worst_value`, `dead_money` and `biggest_bust` are withheld until
  `played_through >= ROI_AWARD_WEEK` (18, overridable per league with
  `roi_award_week`). A player claimed this morning has not had a chance to
  perform, and even at mid-season a "biggest bust" is a verdict on a handful of
  games — the owner's framing, 2026-09-16, and it is right. The money-in/
  money-out awards (`most_wasted`, `biggest_overpay`, `outbid`, `cold_streak`,
  `sharpest`/`loosest`) are **not** gated: they are true the day a claim clears.
  `test_waivers.py` asserts both sides — withheld at week 3, published when the
  same league is judged with `roi_week=3`. **A gate nobody proves opens is a
  gate that silently never opens.**
- **Bid-versus-points is a LOOKBACK and lives in its own panel** ("Did the money
  buy anything?"), not in the spending ledger. Spend and waste are knowable the
  morning a claim clears; whether the money bought anything cannot be known
  until weeks have been played. Mixing them put two columns of `new` / `dead`
  down every row of the ledger and invited exactly the misreading the window bug
  caused. With no settled claims the panel prints one sentence saying so rather
  than a table of dashes, and it fills in on its own from the week after the
  first claims. `best_buy` sits opposite `worst_buy` there, because "did anybody
  actually hit" is half the lookback and had no home before.
- **Waste gets its own cumulative grid with its own Save image button**
  (`sc-waste`), the same weeks-across shape as the money grids, plus a
  claim-level **Biggest overpays** panel (where an uncontested row prints its
  next bid as "none") and a "worst of the season" line naming the concrete
  case. Burying it as one ledger column was the first version's
  mistake — it is the number the owner asked for, week by week *and* cumulative.
- **`cost_per_point` is `null`, never zero, when there is nothing to judge.**
  Money spent with no started points renders as **dead**, which is a different
  statement from "cheap". The awards skip an owner under $10 of spend entirely.
- **Best and worst spenders are ranked in the script, not the page**, so the two
  can't drift into two different answers.
- **A claim's return is measured STRICTLY AFTER its week, and is `None` until
  there is a played week to measure.** Sleeper files a Wednesday waiver run under
  the week whose games just finished, so a claim tagged week 1 first plays in
  week 2. Counting from the claim's own week credits the player with a game he
  was not on the roster for -- which always comes out 0.0, so it does not look
  like a bug, **it looks like a bust**. The live 2026-09-16 run proved it: all 35
  claims read 0.0 and the script called a $502 Puka Nacua claim the season's
  biggest bust hours after it cleared. `played_through` is the last week anybody
  actually scored (NOT the last week with a transaction, which always runs
  further), and a claim with an empty window gets `None`, never 0.0 -- *not yet
  measurable* and *bought nothing* are different statements and must not render
  the same. The UI says `new` for the first and `dead` for the second.
- **`cost_per_point` divides MEASURED spend by measured points**, so an owner
  whose claims are all still too new reads null instead of infinitely expensive.
- **A claim's return also stops when the player leaves the roster.** Points are
  only counted for weeks the player is still in the winner's `players_points`, so
  a trade or a drop ends the tally by itself.
- **A comparative award needs `MIN_FIELD_FOR_AWARD` (3) candidates and two
  different people at the ends**, or it is not published. With two candidates the
  same owner can top and bottom one ranking: the live run made CodyPowers28 both
  *Best value* and *Worst value* because he was the only owner with a measured
  point, and crowned a *Sharpest bidder* who had wasted 56%. `pair()` in
  `awards()` enforces both conditions; every comparative award goes through it.
- **The workflow has two cron entries and a guard step.** GitHub cron is UTC and
  has no idea DST exists, so 8am ET is two different UTC hours: `0 12 * * 3`
  (8am EDT, Mar-Nov) and `0 13 * * 3` (8am EST, Nov-Mar). The guard runs
  whichever entry matches the offset in force today and skips the other, so the
  job never drifts to 7am or 9am across the time change. A manual
  `workflow_dispatch` skips the guard entirely.
- **The guard keys on `github.event.schedule`, NOT on the current Eastern
  hour.** That field hands the job the exact cron string that fired it. An
  hour-equality guard (`is it 8 in New York right now?`) was the first version
  and it has a silent failure: GitHub delays scheduled runs under load, and a
  run delayed past the hour would skip — **both** entries, so the week's
  analysis just never happens and nothing says so. Verified against real
  Wednesdays either side of 2026-11-01, including a one-hour-delayed run, which
  the new guard still executes.
- **Action majors are pinned to the Node 24 releases** (`checkout@v5`,
  `setup-python@v6`). The v4/v5 pair still worked but every run printed a Node 20
  deprecation warning, and GitHub's force-onto-Node-24 fallback is temporary --
  left alone it becomes a broken Wednesday with nobody watching. Bumped
  2026-09-16 after the owner flagged the warning.
- **The commit step rebases before pushing.** The bot pushes to `main` and a
  human may have pushed since the job started; a race should cost a rebase, not
  a failed run and a missing week.
- **The commit step drops a run where only `generated` moved**, or every
  Wednesday would produce a commit differing by a timestamp.
- **`test/test_waivers.py` is a fixture test with no network** (44 assertions),
  because Sleeper is not reachable from every environment this repo gets worked
  in -- a Claude Code web session has a GitHub-only egress allowlist -- and these
  are arithmetic on a shape that is easy to get subtly wrong. Run it with
  `python test/test_waivers.py` after touching a metric, and change it in the
  same pass.

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
- **Odds** come from Bova's Picks' snapshots at `../bovas-picks/data/odds/history/`, last
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
- **Partly automated now.** `.github/workflows/waivers.yml` rebuilds the waiver analysis every
  Wednesday at 11am ET. `build_week.py` is still run by hand on Tuesdays, because the pick'em
  GraphQL needs Matt's Sleeper login token and putting it in this public repo's secrets was not
  wanted; the prose has to be hand-written anyway. A Tuesday Action for King's Justice and
  2 Mitchs alone (the REST leagues) would work if it is ever worth it.
- The King's Justice history dashboard (`../kings-justice/dashboard.html`, private repo `bova4389/kings-justice`) is separate. The hub's
  KJ tab is the *weekly* view; the dashboard is four seasons of FAAB history. Link, don't merge.
