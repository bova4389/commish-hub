# Season Totals and Save-as-Image — Commish Hub reference

Moved verbatim out of `CLAUDE.md` on 2026-11-11 so it loads only when needed. A cross-reference to another section may now point to a different `docs/claude/` file; grep the folder for the heading.

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
- **On a phone, Save image opens the share sheet** (owner, 2026-09-29): Save Image is one
  tap and so is posting straight to the Sleeper app. The old path -- a download that lands in
  Files behind an "Open in..." bar, or a long-press on a preview that some mobile browsers
  only *select* -- was too many taps. `canShareFile()` gates it to a coarse pointer plus
  `navigator.canShare({files})`, so a desktop still downloads. Drawing the card can outlast
  the tap, and the browser then refuses the share; the overlay opens with a **Share** button
  instead, which is a fresh tap. The preview is a blob URL, not a data URL, for the same
  long-press reason.
- **No control above a grid appears in an image**: `.sharecard.exporting .gctl` is hidden
  whole. It hid only `.gtoggle` at first, so every money image carried a "Show 14 $0 rows"
  button.

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
| Money won | Infinity War | the weekly $20 (plus any rolled-in pot) on the week they took it; the season prizes only once week 18 is final |
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
- **The money grid shows the weekly $20s ONLY until week 18 is final** (owner's
  call, 2026-09-29): no trophies, no season prize in the totals, no week-18
  column. A projected $380 sitting in someone's "Season $" read as money already
  paid. When the last week is final the prize lands in its column and the total
  becomes every dollar taken. `paid()` in `iwCards()` is the switch.
- **The picks grid still carries a week-18 column, played or not**, because that
  is where the season trophies go and seeing them coming is the point. While the
  week is still ahead the column is amber-tinted and the trophies are dimmed --
  they are where it stands today, never a result. `iwSeason()` unions the built
  weeks with `last_week` for this; every per-week read tolerates a column with
  no week behind it. The first version derived its columns from the built weeks
  alone and the trophies silently never rendered.
- **The trophies rank on cumulative CORRECT PICKS**, shown on the picks grid all
  season and on the money grid once week 18 is final -- the season money IS that
  ranking, so the money grid adopts it only when it is a result.
- **The picks card opens with what is at stake**: a strip reading 1st place $380, 2nd place
  $160, paid after week 18 (owner, 2026-09-29), off `payouts` in config. It sits above the
  grid controls, so it is in the saved image too.
- **The saved picks image carries the top 6 and anyone tied with sixth**
  (`PICKS_IN_IMAGE`, owner 2026-09-29); the page keeps every entry. Rows below the
  cut get `ex-cut`, hidden only under `.sharecard.exporting`, and an `.ex-only`
  footnote says "Top 6 and ties: N of M entries" so the image never passes for
  the whole pool. Cutting inside a tie would pick arbitrarily, so ties stay. $380 to first, $160 to second
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
  [data-gmode],[data-zero],[data-copy]`.** Adding a control means adding its attribute to
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
