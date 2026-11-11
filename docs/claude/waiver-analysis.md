# Waiver Wire Analysis — Commish Hub reference

Moved verbatim out of `CLAUDE.md` on 2026-11-11 so it loads only when needed. A cross-reference to another section may now point to a different `docs/claude/` file; grep the folder for the heading.

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
- **A claim that failed for any reason but a higher bid never happened** (owner's call,
  2026-09-30). Sleeper also fails claims for "your roster will have too many players after
  this transaction" (no valid drop) and for lack of budget; those are not a rival bid, not a
  lost bid and not a shut-out week. `outbid()` in build_week.py keeps a failed claim only
  when Sleeper's note says "This player was claimed by another owner" -- an allowlist, so an
  unseen reason is dropped rather than counted -- and `week_transactions()` also drops any
  losing bid above the price paid *before* the one-bid-per-roster collapse. Found live: an
  invalid $54 avobttam claim stood as runner-up to nelsolson's $16 Rachaad White win, read
  as **-$38 wasted**, and crowned him Sharpest bidder at -238%. Fixed: 7 invalid claims out
  of the lost bids, league waste $1,454 -> $1,516, and `test_waivers.py` carries the case.
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
