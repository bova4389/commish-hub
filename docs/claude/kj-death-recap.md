# King's Justice Death Recap — Commish Hub reference

Moved verbatim out of `CLAUDE.md` on 2026-11-11 so it loads only when needed. A cross-reference to another section may now point to a different `docs/claude/` file; grep the folder for the heading.

## King's Justice Death Recap

Added 2026-10-07 at the owner's request. A **Death Recap** panel opens the King's Justice
weekly evidence, right under the recap card: the team that died this week, with **Career in
review** (every season's finish and chop week), **Lifetime earnings**, **This season** (score
and rank among teams alive, week by week, plus one FAAB line), and **Cause of death**. It has
the usual Save image / Preview pair plus a **Copy text** button that puts a group-chat version
on the clipboard, so Matt can post the image and the text separately.

- **The facts are `leagues.kings_justice.death` in the week file**, built by
  `death_recap()` in build_week.py once every game is final (`null` while provisional).
  **The words are templated in hub.js** (`deathLines()`), and both the panel and the
  copy text are written from those same sentences, so the image and the text can never
  disagree. Change a sentence there, not in two places.
- **The epitaph is the only hand-written part**: `recaps/<season>.json`
  `leagues.kings_justice.<week>.epitaph`, one roast line written by the Tuesday hub task. The
  card works without it.
- **Career history for finished seasons is a frozen export**,
  `data/history/kings_justice.json`, written by `../kings-justice/export_hub_history.py` and
  read through `"history"` in the KJ config. The hub can't rebuild it: kings-justice is a
  private repo the Action can't read, and 2023–2024 can only be reconstructed by that
  pipeline (manual chops, a deleted manager, shuffled draft roster ids). It is keyed by
  **Sleeper user_id**, because handles change (CJElworth became Elworth). The current season
  comes from Sleeper in `death_recap()`. **After each season ends**, run
  `python ../kings-justice/pull_league_data.py`, then `python ../kings-justice/export_hub_history.py`,
  and commit the history file here. Otherwise that season vanishes from every later career.
- **Lifetime earnings = place prizes ($350/$150) + weekly highs ($25 each).** The history
  export reconciles to the dollar: 2023–2025 paid $2,775, which is 3 × ($500 + 17 × $25). Entry
  fees aren't in the data, so this is gross winnings, never net.
- **The dead team is Sleeper's chopped roster if the chop has posted, otherwise the lowest
  score** among teams alive going in (the league rule, which has matched every chop since
  2023). `confirmed` says which. The chop usually posts Tuesday afternoon, after the 5am
  build, so Tuesday's card carries a "Sleeper hasn't posted the chop yet" note. **The
  Wednesday waiver workflow re-runs King's Justice facts** (`--week latest --only
  kings_justice`) to confirm it. That re-run also picks up the claims Sleeper filed under the
  week that morning, so a week's Waiver wire panel fills in on Wednesday. It runs after the
  waiver commit, so a King's Justice failure can't cost the waiver analysis.
- **An `--only` rebuild that changes nothing writes nothing** (build_week.py compares the
  rebuilt leagues with the file on disk). Without that, every Wednesday re-run would commit
  three files differing only by `generated`.
- **Blame, in order:** a single bench swap worth more than the death margin (`start_sit`,
  with `out_proj` so a starter projected for 0.0 is called out); else a starter with no game
  (`no_game`); else the starter furthest under projection (`bust`). `optimal` is the best
  legal lineup from that roster, for the "left on the bench" line.
- **The final week has no death.** With two teams left, the lower score is second place and
  takes $150, so `kind` is `runner_up`, the card reads "Runner-up Recap", "Cause of death"
  becomes "How the final was lost", and `confirmed` is true by rule (there is no chop
  transaction to wait for).
- **Money on this card has thousands separators** (`cash()`, `$1,000`). It is local to the
  Death Recap so no other saved image changes.
