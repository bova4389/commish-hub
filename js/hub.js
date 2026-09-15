/* Commish Hub -- renders one week of one league: the shareable recap card on
   top, the numbers it was written from underneath.

   Data in:  data/config.json                 leagues, ids, names, accents
             data/<season>/index.json         which weeks exist
             data/<season>/week-NN.json       the facts (scripts/build_week.py)
             recaps/<season>.json             the hand-written prose (optional)

   No framework, no build. The only external script is html2canvas, used for
   "Save image". Everything else is plain DOM. */

(function () {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const f2 = (n) => (Math.round((+n || 0) * 100) / 100).toFixed(2);
  const money = (n) => '$' + Math.round(+n || 0);
  const pct = (p) => (p == null ? '' : Math.round(p * 100) + '%');
  const bust = () => '?_=' + Math.floor(Date.now() / 60000);   // one-minute cache buster

  async function j(path, optional) {
    try {
      const r = await fetch(path + bust(), { cache: 'no-store' });
      if (!r.ok) throw new Error(r.status + ' ' + path);
      return await r.json();
    } catch (e) {
      if (optional) return null;
      throw e;
    }
  }

  let CONFIG = null, INDEX = null, RECAPS = null, WEEK = null, SEASON = null, WAIVERS = null;
  // week is a number, or the string 'season' for the cumulative views.
  // hideZero defaults ON: the money grids are sorted highest-first, so the $0
  // rows are a block of nothing at the bottom and the shareable image is better
  // without them. The toggle says how many it is hiding, so nobody goes missing
  // silently.
  const state = { league: null, season: null, week: null, gridMode: 'weekly', hideZero: true };

  /* ---------------------------------------------------------------- boot */
  async function boot() {
    try {
      CONFIG = await j('data/config.json');
    } catch (e) {
      return fail('Could not load data/config.json. Open this page through a web server, not as a file.');
    }
    readHash();
    const seasons = allSeasons();
    if (!state.season || !seasons.includes(state.season)) state.season = CONFIG.site.season;
    if (!state.league || !CONFIG.leagues[state.league]) state.league = Object.keys(CONFIG.leagues)[0];
    fillSelect($('#season-select'), seasons.map((s) => [s, s]), state.season);
    $('#season-select').onchange = (e) => { state.season = +e.target.value; state.week = null; loadSeason(); };
    $('#week-select').onchange = (e) => {
      const v = e.target.value;
      state.week = v === SEASON_VIEW ? SEASON_VIEW : +v;
      loadWeek();
    };
    $('#btn-save').onclick = () => exportCard('save');
    $('#btn-preview').onclick = () => exportCard('preview');
    $('#btn-close').onclick = () => { $('#overlay').hidden = true; };
    // The season cards are rebuilt on every render, so their buttons are
    // handled by delegation rather than wired one by one.
    $('#evidence').addEventListener('click', (e) => {
      const b = e.target.closest('[data-save],[data-preview],[data-gmode],[data-zero]');
      if (!b) return;
      if (b.dataset.zero) {
        state.hideZero = !state.hideZero;
        return render();
      }
      if (b.dataset.gmode) {
        if (b.dataset.gmode === state.gridMode) return;
        state.gridMode = b.dataset.gmode;
        return render();
      }
      const id = b.dataset.save || b.dataset.preview;
      exportEl(document.getElementById(id), `${state.league}-${state.season}-${id}.png`,
        b.dataset.save ? 'save' : 'preview');
    });
    $('#overlay').onclick = (e) => { if (e.target.id === 'overlay') $('#overlay').hidden = true; };
    buildTabs();
    await loadSeason();
  }

  function fail(msg) {
    const s = $('#status');
    s.textContent = msg; s.classList.add('err'); s.hidden = false;
  }

  function allSeasons() {
    const set = new Set();
    Object.values(CONFIG.leagues).forEach((l) => Object.keys(l.ids || {}).forEach((y) => set.add(+y)));
    return [...set].sort((a, b) => b - a);
  }

  function readHash() {
    const m = location.hash.replace('#', '').split('/');
    if (m[0]) state.league = m[0];
    if (m[1]) state.season = +m[1];
    if (m[2]) state.week = m[2] === SEASON_VIEW ? SEASON_VIEW : +m[2];
  }
  function writeHash() {
    const h = `#${state.league}/${state.season}/${state.week}`;
    if (location.hash !== h) history.replaceState(null, '', h);
  }

  function fillSelect(sel, pairs, value) {
    sel.innerHTML = pairs.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join('');
    sel.value = String(value);
  }

  function buildTabs() {
    const el = $('#tabs');
    el.innerHTML = Object.entries(CONFIG.leagues).map(([k, l]) =>
      `<button type="button" class="tab" data-k="${esc(k)}" style="--accent:${esc(l.accent)}">${esc(l.name)}</button>`).join('');
    el.querySelectorAll('.tab').forEach((b) => {
      b.onclick = () => { state.league = b.dataset.k; render(); };
    });
  }

  async function loadSeason() {
    $('#status').hidden = false; $('#status').textContent = 'Loading…';
    $('#season-select').value = String(state.season);
    INDEX = await j(`data/${state.season}/index.json`, true) || { weeks: {} };
    RECAPS = await j(`recaps/${state.season}.json`, true) || { leagues: {} };
    // Both are optional. The rollup is written by build_season.py at the end of
    // every build_week run; waivers.json by the Wednesday cron. A season view
    // with neither says what to run, rather than breaking the page.
    SEASON = await j(`data/${state.season}/season.json`, true);
    WAIVERS = await j(`data/${state.season}/waivers.json`, true);
    const weeks = Object.keys(INDEX.weeks).map(Number).sort((a, b) => a - b);
    if (!weeks.length) {
      $('#card-wrap').hidden = true; $('#evidence').innerHTML = '';
      return fail(`No weeks built for ${state.season} yet. Run: python scripts/build_week.py --week N`);
    }
    if (state.week !== SEASON_VIEW && (!state.week || !weeks.includes(state.week))) state.week = weeks[weeks.length - 1];
    fillSelect($('#week-select'),
      weeks.map((w) => [w, `Week ${w}${INDEX.weeks[w].final ? '' : ' (live)'}`])
        .concat([[SEASON_VIEW, 'Season totals']]), state.week);
    await loadWeek();
  }

  async function loadWeek() {
    $('#status').hidden = false; $('#status').textContent = 'Loading…';
    if (state.week === SEASON_VIEW) { writeHash(); return renderSeason(); }
    try {
      WEEK = await j(`data/${state.season}/week-${String(state.week).padStart(2, '0')}.json`);
    } catch (e) {
      WEEK = null;
      return fail(`No data file for ${state.season} week ${state.week}.`);
    }
    render();
  }

  /* ---------------------------------------------------------------- render */
  function render() {
    writeHash();
    const cfg = CONFIG.leagues[state.league];
    document.documentElement.style.setProperty('--accent', cfg.accent);
    document.querySelectorAll('.tab').forEach((b) => b.classList.toggle('active', b.dataset.k === state.league));
    if (state.week === SEASON_VIEW) return renderSeason();
    const L = WEEK && WEEK.leagues[state.league];
    const status = $('#status');
    if (!L || L.error) {
      $('#card-wrap').hidden = true; $('#evidence').innerHTML = '';
      return fail(L && L.error ? `The facts script failed for this league: ${L.error}` : `${cfg.name} was not built for week ${state.week}.`);
    }
    status.hidden = true; status.classList.remove('err');
    const recap = ((RECAPS.leagues || {})[state.league] || {})[String(state.week)] || null;
    $('#recap-card').innerHTML = cardHtml(cfg, L, recap);
    $('#card-wrap').hidden = false;
    const kind = cfg.kind;
    $('#evidence').innerHTML =
      kind === 'chopped' ? evidenceChopped(L) :
      kind === 'h2h' ? evidenceH2H(L) :
      kind === 'pickem' ? evidencePickem(L) :
      kind === 'survivor' ? evidenceSurvivor(L) : '';
    $('#foot').innerHTML =
      `Facts pulled ${esc(WEEK.generated.replace('T', ' ').slice(0, 16))}` +
      (WEEK.all_final ? '' : ' &middot; <span class="warn">week still in progress</span>') +
      ` &middot; <a href="${esc(CONFIG.site.other_league_url)}" target="_blank" rel="noopener">The Other League recap &rarr;</a>`;
  }

  /* ---------------------------------------------------------------- the card */
  function cardHtml(cfg, L, recap) {
    const facts = (recap && recap.facts) || autoFacts(cfg.kind, L);
    const paras = recap && recap.paragraphs && recap.paragraphs.length
      ? recap.paragraphs.map((p) => `<p>${md(p)}</p>`).join('')
      : `<p class="none">Recap not written yet. The numbers below are live; the words come Tuesday.</p>`;
    const head = (recap && recap.headline) || autoHeadline(cfg.kind, L);
    return `
      <div class="card-top">
        <span class="card-league">${esc(cfg.name)}</span>
        <span class="card-week">Week ${esc(state.week)} &middot; ${esc(state.season)}</span>
      </div>
      <h2 class="card-head">${esc(head)}</h2>
      <div class="card-facts">${facts.map((f) => `<div class="fact"><div class="k">${esc(f.k)}</div><div class="v">${esc(f.v)}</div></div>`).join('')}</div>
      <div class="card-body">${paras}</div>
      <div class="card-foot"><span>Commish Hub &middot; Weekly Recap</span><span>${L.provisional ? '<span class="prov">PROVISIONAL &middot; games still to play</span>' : 'Final'}</span></div>`;
  }

  // **bold** and *italic* only; everything else is escaped.
  function md(s) {
    return esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\*(.+?)\*/g, '<i>$1</i>');
  }

  function autoHeadline(kind, L) {
    if (kind === 'chopped' && L.chopped) return L.provisional ? `${L.chopped.handle} is in the chop seat` : `${L.chopped.handle} has been chopped`;
    if (kind === 'h2h') return L.provisional ? 'Week in progress' : `${L.high} scores the week high`;
    if (kind === 'pickem') return L.rollover ? `Tiebreaker tied: the ${money(potOf(L))} rolls over`
      : L.winners && L.winners.length ? `${L.winners[0]} takes the ${money(potOf(L))} at ${L.best}/${L.weekly_pick_limit}` : 'Week in progress';
    if (kind === 'survivor') return L.died && L.died.length ? `${L.died.length} down, ${L.alive_after} still alive` : `Everyone survived`;
    return `Week ${state.week}`;
  }

  // Infinity War's weekly money is never split: a tie on picks goes to the Monday
  // night total-points tiebreaker, and a tie on that rolls the pot to next week.
  function potOf(L) { return L.pot || (L.payouts && L.payouts.weekly) || 20; }

  function weeklyResult(L) {
    const w = L.winners || [];
    const lim = L.weekly_pick_limit || 8;
    if (L.rollover) return `${(L.tied || []).length}-way tie at ${L.best}/${lim} and on the tiebreaker: the ${money(potOf(L))} rolls to next week`;
    if (!w.length) return L.provisional ? 'Games still to play' : 'No winner';
    const tb = L.tiebreak && (L.tiebreak.guesses || []).find((g) => g.handle === w[0]);
    return `${w[0]} takes the ${money(potOf(L))} at ${L.best}/${lim}` +
      (tb ? `, winning a ${L.tied.length}-way tie on the tiebreaker (${tb.guess} vs ${L.tiebreak.actual} in ${L.tiebreak.game})` : '');
  }

  function autoFacts(kind, L) {
    const out = [];
    if (kind === 'chopped') {
      if (L.chopped) out.push({ k: L.provisional ? 'Chop seat' : 'Chopped', v: `${L.chopped.handle} · ${f2(L.chopped.points)}` });
      if (L.high) out.push({ k: `Week high · ${money(L.payouts.weekly_high || 25)}`, v: `${L.high.handle} · ${f2(L.high.points)}` });
      if (L.survivor) out.push({ k: 'Survived by', v: `${f2(L.survivor.margin)} · ${L.survivor.handle}` });
      out.push({ k: 'Still alive', v: `${L.provisional ? L.alive_before : L.alive_after} of 18` });
    } else if (kind === 'h2h') {
      const hi = L.matchups.map((m) => m.winner).sort((a, b) => b.points - a.points)[0];
      const lo = L.matchups.map((m) => m.loser).sort((a, b) => a.points - b.points)[0];
      const close = [...L.matchups].sort((a, b) => a.margin - b.margin)[0];
      const bench = L.bench_kings[0];
      if (hi) out.push({ k: 'Week high', v: `${hi.name} · ${f2(hi.points)}` });
      if (lo) out.push({ k: 'Week low', v: `${lo.name} · ${f2(lo.points)}` });
      if (close) out.push({ k: 'Closest game', v: `${close.winner.name} by ${f2(close.margin)}` });
      if (bench) out.push({ k: 'Left on bench', v: `${bench.name} · ${f2(bench.left)}` });
    } else if (kind === 'pickem') {
      const w = L.winners || [];
      out.push({ k: `Weekly ${money(potOf(L))}`, v: L.rollover ? 'Rolls over' : w.length ? `${w[0]} · ${L.best}/${L.weekly_pick_limit}` : 'pending' });
      if (L.tiebreak && !L.provisional) {
        const tb = (L.tiebreak.guesses || []).find((g) => g.handle === w[0]);
        out.push({ k: `Tiebreaker · ${L.tiebreak.game}`, v: tb ? `${tb.guess} vs ${L.tiebreak.actual}` : `tied · ${L.tiebreak.actual}` });
      }
      if (L.provisional) { out.push({ k: 'Cards in', v: `${L.entries.filter((e) => !e.no_pick).length} of ${L.entries_total}` }); return out; }
      out.push({ k: 'Upsets', v: String((L.upsets || []).length) });
      if (L.worst && L.worst.length) out.push({ k: 'Worst card', v: L.worst.slice(0, 2).join(', ') });
      if (L.leaderboard && L.leaderboard[0]) out.push({ k: 'Season leader', v: `${L.leaderboard[0].handle} · ${L.leaderboard[0].points}` });
    } else if (kind === 'survivor') {
      // `died` holds every losing pick; with revives left a loss is a strike, not a death.
      const lost = L.died || [];
      const out_now = lost.filter((d) => d.eliminated_now).length;
      out.push(out_now
        ? { k: 'Eliminated', v: `${out_now} · ${lost.length - out_now} strikes` }
        : { k: 'Strikes this week', v: `${lost.length} · 0 out` });
      out.push({ k: 'Still alive', v: `${L.alive_after} of ${L.entries_total}` });
      const burned = (g) => Object.entries(g.picks).filter(([t]) => t !== g.winner).reduce((a, [, n]) => a + n, 0);
      const k = (L.killer_games || []).slice().sort((a, b) => burned(b) - burned(a))[0];
      if (k) out.push({ k: 'Killer game', v: `${k.game} · ${burned(k)}` });
      const cons = L.consensus || [];
      const top = cons.filter((c) => cons[0] && c.count === cons[0].count);
      if (top.length) out.push({ k: 'Consensus pick', v: `${top.map((c) => c.team).join(' / ')} ×${top[0].count}` });
    }
    return out;
  }

  /* ---------------------------------------------------------------- evidence: Kings Justice */
  function evidenceChopped(L) {
    const slots = WEEK.nfl.slots;
    const board = L.scoreboard;
    const rows = board.map((r) => {
      const cls = r.chopped || r.rank === board.length ? 'hl-bad' : r.rank === 1 ? 'hl-good' : (r.rank === board.length - 1 ? 'hl-warn' : '');
      const pills = (r.rank === 1 ? `<span class="pill good">${money(L.payouts.weekly_high || 25)}</span>` : '') +
        (r.rank === board.length ? `<span class="pill bad">${L.provisional ? 'CHOP SEAT' : 'CHOPPED'}</span>` : '');
      return `<tr class="${cls}"><td class="num">${r.rank}</td><td>${esc(r.handle)}${pills}<div class="sub">${esc(r.team_name)}</div></td>` +
        `<td class="num"><b>${f2(r.points)}</b></td><td class="num muted">${f2(r.proj)}</td><td class="num ${r.points - r.proj >= 0 ? 'good' : 'bad'}">${(r.points - r.proj >= 0 ? '+' : '') + f2(r.points - r.proj)}</td></tr>`;
    }).join('');

    // The story of the week, one line per kickoff slot, skipping the slots
    // before anyone had a player on the field.
    const seat = (L.chop_seat || []).filter((s) => s.points > 0 || s.slot === slots.length - 1);
    const story = seat.map((s) =>
      `<li><span class="when">After ${esc(s.label)}</span><span><b>${esc(s.handle)}</b> in the seat at ${f2(s.points)}, ` +
      `${f2(s.margin)} behind ${esc(s.next_handle)}${s.left ? `, ${s.left} still to play` : ', nobody left to play'}</span></li>`).join('');

    // Running totals for the bottom of the table, slot by slot.
    const bottom = [...board].sort((a, b) => a.points - b.points).slice(0, 6);
    const firstLive = Math.max(0, seat.length ? seat[0].slot : 0);
    const liveSlots = slots.filter((s) => s.i >= firstLive);
    const timeline = `<div class="tbl-wrap"><table><thead><tr><th>Team</th>${liveSlots.map((s) => `<th class="num">${esc(s.label)}</th>`).join('')}</tr></thead><tbody>` +
      bottom.map((r) => `<tr class="${r.rank === board.length ? 'hl-bad' : ''}"><td>${esc(r.handle)}</td>` +
        liveSlots.map((s) => `<td class="num">${f2(r.running[s.i])}${r.left_after[s.i] ? `<div class="sub">${r.left_after[s.i]} left</div>` : ''}</td>`).join('') + '</tr>').join('') +
      '</tbody></table></div>';

    // Monday night watch: who was near the bottom going into the last slot,
    // and what their last players did.
    const last = slots.length - 1;
    const pen = last - 1;
    const watch = [...board].sort((a, b) => a.running[pen] - b.running[pen]).slice(0, 5).map((r) => {
      const gained = r.points - r.running[pen];
      const players = r.last_slot_players.map((p) => `${esc(p.name)} ${f2(p.pts)}`).join(', ');
      return `<tr class="${r.rank === board.length ? 'hl-bad' : ''}"><td>${esc(r.handle)}</td><td class="num">${f2(r.running[pen])}</td>` +
        `<td>${players || '<span class="muted">nobody playing</span>'}</td><td class="num ${gained > 0 ? 'good' : 'muted'}">${gained > 0 ? '+' + f2(gained) : '—'}</td><td class="num"><b>${f2(r.points)}</b></td></tr>`;
    }).join('');

    const tops = L.top_starters.slice(0, 6).map((p) => `<tr><td>${esc(p.name)} <span class="sub">${esc(p.pos)} ${esc(p.team || '')}</span></td><td>${esc(p.handle)}</td><td class="num good">${f2(p.pts)}</td></tr>`).join('');
    const duds = L.dud_starters.slice(0, 6).map((p) => `<tr><td>${esc(p.name)} <span class="sub">${esc(p.pos)} ${esc(p.team || '')}</span></td><td>${esc(p.handle)}</td><td class="num bad">${f2(p.pts)}</td></tr>`).join('');

    const tx = L.transactions || {};
    const waivers = (tx.waivers || []).slice(0, 8).map((w) => `<tr><td>${esc(w.player)} <span class="sub">${esc(w.pos)}</span></td><td>${esc(w.handle)}</td><td class="num"><b>${money(w.bid)}</b></td>` +
      `<td class="num muted">${w.bidders > 1 ? `${w.bidders} bids · next ${money(w.runner_up)}` : 'uncontested'}</td></tr>`).join('');

    return panel('Scoreboard', `${L.alive_before} alive going in · median ${f2(L.median)} · spread ${f2(L.spread)}`,
        tbl('<th class="num">#</th><th>Team</th><th class="num">Pts</th><th class="num">Proj</th><th class="num">+/-</th>', rows)) +
      panel('How the week unfolded', 'Who sat in the chop seat after each kickoff window',
        story ? `<ul class="story">${story}</ul>` : '<div class="empty">No games played yet.</div>') +
      panel('Bottom six, slot by slot', 'Running totals after each kickoff window', timeline) +
      panel(`${esc(slots[last] ? slots[last].label : 'Last')} watch`, 'The bottom of the table going into the final window, and what their last players did',
        tbl('<th>Team</th><th class="num">Before</th><th>Last players</th><th class="num">Gained</th><th class="num">Final</th>', watch)) +
      panel('Top starters', '', tbl('<th>Player</th><th>Team</th><th class="num">Pts</th>', tops)) +
      panel('Worst starters', 'Players who actually had a game', tbl('<th>Player</th><th>Team</th><th class="num">Pts</th>', duds)) +
      panel('Waiver wire', tx.faab_spent ? `${money(tx.faab_spent)} changed hands across ${(tx.waivers || []).length} winning claims` : 'No money moved',
        waivers ? tbl('<th>Player</th><th>Won by</th><th class="num">Bid</th><th class="num">Auction</th>', waivers) : '<div class="empty">No waiver claims this week.</div>');
  }

  /* ---------------------------------------------------------------- evidence: 2 Mitchs */
  function evidenceH2H(L) {
    const games = L.matchups.map((m) => {
      const w = m.winner, l = m.loser;
      const side = (s, cls) => `<div class="row ${cls}"><span class="who">${esc(s.name)} <span class="sub">${esc(s.record)}</span></span><span class="pts">${f2(s.points)} <span class="sub">proj ${f2(s.proj)}</span></span></div>`;
      const notes = [];
      if (l.best_swap) notes.push(`${esc(l.name)} left ${f2(l.left_on_bench)} on the bench (${esc(l.best_swap.in)} ${f2(l.best_swap.in_pts)} over ${esc(l.best_swap.out)} ${f2(l.best_swap.out_pts)})`);
      if (l.zeros.length) notes.push(`${esc(l.name)} started a zero: ${esc(l.zeros.join(', '))}`);
      if (w.zeros.length) notes.push(`${esc(w.name)} started a zero and still won: ${esc(w.zeros.join(', '))}`);
      if (l.injured_starters.length) notes.push(`${esc(l.name)} started ${esc(l.injured_starters.join(', '))}`);
      return `<div class="match">${side(w, 'win')}${side(l, 'lose')}` +
        `<div class="meta">Margin ${f2(m.margin)}${m.tags.length ? ` <span class="tags">${m.tags.map((t) => `<span class="pill ${t === 'UPSET' || t === 'BENCHED THE WIN' ? 'warn' : 'gray'}">${esc(t)}</span>`).join('')}</span>` : ''}</div>` +
        (notes.length ? `<div class="meta">${notes.join('<br>')}</div>` : '') + '</div>';
    }).join('');

    const perf = (list, cls) => list.slice(0, 6).map((p) => `<tr><td>${esc(p.name)} <span class="sub">${esc(p.pos)}</span></td><td>${esc(nameFor(p.handle))}</td><td class="num muted">${f2(p.proj)}</td><td class="num ${cls}">${f2(p.pts)}</td></tr>`).join('');
    const bench = L.bench_kings.map((b) => `<tr><td>${esc(b.name)}</td><td class="num bad">${f2(b.left)}</td><td class="muted">${b.swap ? `${esc(b.swap.in)} (${f2(b.swap.in_pts)}) over ${esc(b.swap.out)} (${f2(b.swap.out_pts)}) at ${esc(b.swap.slot)}` : ''}</td></tr>`).join('');
    const stand = L.standings.map((s, i) => `<tr><td class="num">${i + 1}</td><td>${esc(s.name)}</td><td class="num">${esc(s.record)}</td><td class="num muted">${f2(s.pf)}</td></tr>`).join('');
    const tx = L.transactions || {};
    const moves = (tx.waivers || []).map((w) => `<tr><td>${esc(w.player)} <span class="sub">${esc(w.pos)}</span></td><td>${esc(nameFor(w.handle))}</td><td class="num"><b>${money(w.bid)}</b></td><td class="num muted">${w.bidders > 1 ? `${w.bidders} bids` : 'uncontested'}</td></tr>`).join('') +
      (tx.free_agents || []).map((a) => `<tr><td>${esc(a.player)}</td><td>${esc(nameFor(a.handle))}</td><td class="num muted">FA</td><td class="muted">${a.drops.length ? 'dropped ' + esc(a.drops.join(', ')) : ''}</td></tr>`).join('');
    const trades = (tx.trades || []).map((t) => `<div class="match"><div class="meta">${Object.entries(t.sides).map(([h, ps]) => `<b>${esc(nameFor(h))}</b> gets ${esc(ps.join(', '))}`).join(' &middot; ')}</div></div>`).join('');

    return panel('Matchups', `Projections run hot by ${f2(L.proj_bias)} league-wide this week; judge over/under against that`, games || '<div class="empty">No matchups.</div>') +
      panel('Overperformers', 'Actual vs projected, starters only', tbl('<th>Player</th><th>Manager</th><th class="num">Proj</th><th class="num">Actual</th>', perf(L.over, 'good'))) +
      panel('Underperformers', 'Players who had a game and did not show up', tbl('<th>Player</th><th>Manager</th><th class="num">Proj</th><th class="num">Actual</th>', perf(L.under, 'bad'))) +
      panel('Points left on the bench', 'Optimal lineup minus what was actually started', tbl('<th>Manager</th><th class="num">Left</th><th>Best single swap</th>', bench)) +
      panel('Standings', 'As of now', tbl('<th class="num">#</th><th>Manager</th><th class="num">W-L</th><th class="num">PF</th>', stand)) +
      panel('Moves', tx.faab_spent ? `${money(tx.faab_spent)} in FAAB` : '', (moves ? tbl('<th>Player</th><th>Manager</th><th class="num">Cost</th><th></th>', moves) : '') + trades || '<div class="empty">No moves this week.</div>');
  }

  /* ---------------------------------------------------------------- evidence: Infinity War */
  function evidencePickem(L) {
    const lim = L.weekly_pick_limit || 8;
    const rows = L.entries.map((e, i) => {
      const chips = e.picks.map((p) => p.hidden
        ? `<span class="chip" title="${esc(p.game)} has not kicked off">&#128274;</span>`
        : `<span class="chip ${p.outcome || ''} ${e.lonely_wins.includes(p.team) ? 'lonely' : ''}" title="${esc(p.game)}">${esc(p.team)}</span>`).join('');
      const cls = e.no_pick ? 'dim' : (L.winners.includes(e.handle) ? 'hl-good' : (L.worst.includes(e.handle) ? 'hl-bad' : ''));
      const tbg = e.tiebreaker ? (e.tiebreaker.hidden ? '<div class="sub">tiebreaker &#128274;</div>' : `<div class="sub">tiebreaker ${e.tiebreaker.guess}</div>`) : '';
      return `<tr class="${cls}"><td>${esc(e.handle)}${L.winners.includes(e.handle) ? `<span class="pill good">${money(potOf(L))}</span>` : ''}${tbg}</td>` +
        `<td class="num"><b>${e.no_pick ? '—' : e.correct}</b><span class="muted">/${lim}</span>${e.pending ? `<div class="sub">${e.pending} pending</div>` : ''}</td>` +
        `<td><div class="picks">${chips || '<span class="muted">no picks</span>'}</div></td><td class="num">${e.season_points}</td></tr>`;
    }).join('');
    const ups = (L.upsets || []).map((g) => `<tr><td>${esc(g.game)}</td><td>${esc(g.winner)} <span class="sub">over ${esc(g.fav)} (${pct(g.fav_prob)})</span></td><td class="num">${(g.picks[g.winner] || 0)} had it</td></tr>`).join('');
    const field = L.field.map((g) => {
      const parts = Object.entries(g.picks).sort((a, b) => b[1] - a[1]).map(([t, n]) => `<span class="chip ${g.winner ? (t === g.winner ? 'win' : 'loss') : ''}">${esc(t)} ${n}</span>`).join(' ');
      return `<tr><td>${esc(g.game)}${g.upset ? '<span class="pill warn">UPSET</span>' : ''}<div class="sub">${g.fav ? `${esc(g.fav)} ${pct(g.fav_prob)}` : 'no line'}</div></td><td><div class="picks">${parts}</div></td></tr>`;
    }).join('');
    const board = L.leaderboard.map((e, i) => `<tr><td class="num">${i + 1}</td><td>${esc(e.handle)}</td><td class="num">${e.points}</td></tr>`).join('');
    const lonely = L.entries.filter((e) => e.lonely_wins.length).map((e) => `<tr><td>${esc(e.handle)}</td><td>${esc(e.lonely_wins.join(', '))}</td></tr>`).join('');
    const chalk = L.entries.filter((e) => e.chalk_losses.length).map((e) => `<tr><td>${esc(e.handle)}</td><td>${esc(e.chalk_losses.join(', '))}</td></tr>`).join('');
    const tbRows = L.tiebreak ? L.tiebreak.guesses.map((g) => `<tr class="${L.winners.includes(g.handle) ? 'hl-good' : ''}"><td>${esc(g.handle)}</td><td class="num">${g.guess == null ? '—' : g.guess}</td><td class="num">${g.off == null ? 'no guess' : g.off}</td></tr>`).join('') : '';
    return panel('This week', weeklyResult(L),
        tbl('<th>Entry</th><th class="num">Right</th><th>Picks (outlined = nobody else had it)</th><th class="num">Season</th>', rows)) +
      (L.tiebreak ? panel('Tiebreaker', `Total points in ${esc(L.tiebreak.game)}: ${L.tiebreak.actual}. Closest guess wins; a tie on this rolls the pot to next week.`,
        tbl('<th>Tied at ' + L.best + '</th><th class="num">Guess</th><th class="num">Off by</th>', tbRows)) : '') +
      panel('Upsets', 'Winners that were not favored, and how many saw it coming', ups ? tbl('<th>Game</th><th>Result</th><th class="num">Picked</th>', ups) : '<div class="empty">No upsets, or no lines for this week.</div>') +
      panel('Lonely winners', 'A correct pick nobody else made. That is how the weekly money is actually won.', lonely ? tbl('<th>Entry</th><th>Picks</th>', lonely) : '<div class="empty">Nobody went alone and got it right.</div>') +
      panel('Chalk that burned', 'Picked a 65%+ favorite that lost', chalk ? tbl('<th>Entry</th><th>Picks</th>', chalk) : '<div class="empty">None.</div>') +
      panel('The field, game by game', 'How the pool split each game', tbl('<th>Game</th><th>Picks</th>', field)) +
      panel('Season standings', 'Total correct picks', tbl('<th class="num">#</th><th>Entry</th><th class="num">Pts</th>', board));
  }

  /* ---------------------------------------------------------------- evidence: Deadpool */
  function evidenceSurvivor(L) {
    const died = (L.died || []).map((d) => `<tr class="hl-bad"><td>${esc(d.handle)}</td><td>${d.pick ? `${esc(d.pick.team)} <span class="sub">${esc(d.pick.score || d.pick.game)}</span>` : '—'}</td>` +
      `<td class="num">${d.strikes_after}</td><td>${d.eliminated_now ? '<span class="pill bad">OUT</span>' : `<span class="pill warn">STRIKE</span>`}</td></tr>`).join('');
    const rows = L.entries.map((e) => {
      const p = e.picks[0];
      const cls = e.eliminated_now ? 'dim' : (p && p.outcome === 'loss' ? 'hl-bad' : '');
      const pickCell = !p ? '<span class="muted">no pick</span>'
        : p.hidden ? `<span class="chip">&#128274;</span> <span class="sub">locked until ${esc(p.slot_label || 'kickoff')}</span>`
        : `<span class="chip ${p.outcome || ''}">${esc(p.team)}</span> <span class="sub">${esc(p.game)}${p.prob != null ? ` · ${pct(p.prob)}` : ''}</span>`;
      return `<tr class="${cls}"><td>${esc(e.handle)}</td><td>${pickCell}</td>` +
        `<td class="num">${e.strikes_after}</td><td>${e.eliminated_now ? '<span class="pill bad">OUT</span>' : '<span class="pill good">ALIVE</span>'}</td></tr>`;
    }).join('');
    const cons = (L.consensus || []).map((c) => `<span class="chip">${esc(c.team)} ${c.count}</span>`).join(' ');
    const killers = (L.killer_games || []).map((g) => `<tr><td>${esc(g.game)}${g.upset ? '<span class="pill warn">UPSET</span>' : ''}</td><td>${esc(g.winner)} won</td><td class="num">${Object.entries(g.picks).filter(([t]) => t !== g.winner).reduce((a, [, n]) => a + n, 0)} died</td></tr>`).join('');
    return panel('The dead', `${(L.died || []).length} lost this week · ${L.alive_after} of ${L.entries_total} still alive · ${L.revives_allowed || 0} revives allowed`,
        died ? tbl('<th>Entry</th><th>Pick</th><th class="num">Strikes</th><th></th>', died) : '<div class="empty">Nobody died. Boring.</div>') +
      panel('Killer games', 'Where the bodies came from', killers ? tbl('<th>Game</th><th>Result</th><th class="num"></th>', killers) : '<div class="empty">No game claimed anyone.</div>') +
      panel('Where the pool went', 'Consensus picks', `<div class="picks">${cons || '<span class="muted">no picks yet</span>'}</div>`) +
      panel('Every entry', L.no_pick && L.no_pick.length ? `No pick submitted: ${esc(L.no_pick.join(', '))}` : '', tbl('<th>Entry</th><th>Pick</th><th class="num">Strikes</th><th></th>', rows));
  }


  /* ================================================================ season
     Everything below renders the CUMULATIVE views -- the ones reached by
     picking "Season totals" in the week dropdown instead of a week number.

     They read data/<season>/season.json (the week rollup, written by
     scripts/build_season.py) and data/<season>/waivers.json (written by
     scripts/build_waivers.py on the Wednesday cron). Both are optional: a
     season with no rollup yet says so rather than breaking the page.

     A grid here is `weeks across, entries down, season total in the last
     column`, which is the shape asked for. Each one sits in a .sharecard --
     its own Save image button, because these get posted to the chat on their
     own, not as part of a weekly recap. */

  const SEASON_VIEW = 'season';
  const TROPHY = { 1: '\u{1F947}', 2: '\u{1F948}' };   // gold, silver

  // The last week of the season, off the rollup. The Infinity War grids always
  // carry a column for it even before it is played, because that is where the
  // season trophies live and seeing them coming is the point.
  function lastWeek() {
    return (SEASON && SEASON.last_week) || 18;
  }

  // Cumulative money and picks for Infinity War, straight off the rollup.
  // The weekly pot is never split, so a week pays its one winner the whole
  // `pot` (which already carries any rolled-over money) and a rollover week
  // pays nobody. Season prizes rank on TOTAL CORRECT PICKS.
  function iwSeason(L) {
    const last = lastWeek();
    const built = Object.keys(L.weeks).map(Number).sort((a, b) => a - b);
    const weeks = built.includes(last) ? built : built.concat([last]);
    const rows = L.entries.map((e) => {
      const money = {}, correct = {};
      let mt = 0, ct = 0;
      weeks.forEach((w) => {
        const W = L.weeks[String(w)];
        if (!W) { money[w] = 0; correct[w] = null; return; }   // the unplayed week-18 column
        const won = W.winners.includes(e.handle) ? (W.pot || 0) : 0;
        if (won) mt += won;
        money[w] = won;
        const c = W.correct[e.handle];
        if (c != null) ct += c;
        correct[w] = c;
      });
      return { handle: e.handle, name: e.name, money, correct, money_total: mt, correct_total: ct };
    });
    // Trophies follow cumulative correct. A tie is reported, never resolved --
    // the pool has no season tiebreaker on record.
    const byCorrect = [...rows].sort((a, b) => b.correct_total - a.correct_total);
    const p = L.payouts || {};
    const prize = { 1: p.first || 0, 2: p.second || 0 };
    const place = {};
    let seen = [];
    byCorrect.forEach((r) => {
      if (!seen.length || r.correct_total !== seen[seen.length - 1]) seen.push(r.correct_total);
      const rank = seen.length;
      if (rank <= 2) place[r.handle] = rank;
    });
    const tied = {};
    [1, 2].forEach((rk) => {
      const at = byCorrect.filter((r) => place[r.handle] === rk);
      if (at.length > 1) tied[rk] = at.length;
    });
    // A TIED PLACE CARRIES NO MONEY. The trophy still shows -- they really are
    // tied -- but the prize is not added to anyone's total, because who gets it
    // is undetermined and the pool has no season tiebreaker on record. Without
    // this, week 1 2026 (three at 7, eleven at 6) put $380 on three people and
    // $160 on eleven, which is $2,140 of a $540 prize pool.
    rows.forEach((r) => {
      r.place = place[r.handle] || null;
      r.tied_at = r.place ? (tied[r.place] || 0) : 0;
      r.prize = r.place && !r.tied_at ? prize[r.place] || 0 : 0;
    });
    const final = !!(L.weeks[String(last)] || {}).final;
    return { weeks, rows, prize, tied, final, last, payouts: p };
  }

  // King's Justice weekly high. A cell holds the winner's score for the week
  // they won it and is blank otherwise -- that was the ask, and it also makes
  // the table readable: 18 columns of everyone's score would be a heat map
  // nobody can find themselves in.
  function kjSeason(L) {
    const weeks = Object.keys(L.weeks).map(Number).sort((a, b) => a - b);
    const rows = L.entries.map((e) => {
      const wins = {};
      let total = 0, n = 0;
      weeks.forEach((w) => {
        const W = L.weeks[String(w)];
        if (W.high && W.high.handle === e.handle) {
          wins[w] = W.high.points;
          total += W.prize || 0;
          n += 1;
        }
      });
      return { handle: e.handle, name: e.name, wins, total, n };
    });
    return { weeks, rows };
  }

  /* ---- the grid ------------------------------------------------------
     One function draws all three grids. `cell(row, week)` returns the HTML for
     a cell and `total(row)` the last column, so a new cumulative table is a
     few lines rather than another copy of the sticky-column markup. */
  function grid(o) {
    const cols = o.weeks;
    const running = state.gridMode === 'running';
    // `isZero` marks a row as having won nothing. Never filter down to an empty
    // table -- a grid showing no rows at all reads as broken data, not as a
    // filter doing its job.
    let rows = o.rows;
    if (state.hideZero && o.isZero) {
      const kept = rows.filter((r) => !o.isZero(r));
      if (kept.length) rows = kept;
    }
    const head = `<tr><th class="gname">${esc(o.nameHead || 'Entry')}</th>` +
      cols.map((w) => `<th class="num${o.softWeeks && o.softWeeks.includes(w) ? ' soft' : ''}">${w}</th>`).join('') +
      `<th class="num gtotal">${esc(o.totalHead)}</th></tr>`;
    const body = rows.map((r, i) => {
      let run = 0;
      const cells = cols.map((w) => {
        const c = o.cell(r, w, running ? (run += (o.step ? o.step(r, w) : 0)) : null);
        return `<td class="num${o.softWeeks && o.softWeeks.includes(w) ? ' soft' : ''}">${c}</td>`;
      }).join('');
      return `<tr class="${o.rowClass ? o.rowClass(r, i) : ''}"><th class="gname" scope="row">${esc(r.name || r.handle)}` +
        (o.rowNote ? o.rowNote(r) : '') + `</th>${cells}<td class="num gtotal">${o.total(r)}</td></tr>`;
    }).join('');
    return `<div class="gridwrap"><table class="grid"><thead>${head}</thead><tbody>${body}</tbody></table></div>`;
  }

  // A .sharecard is a panel with its own Save image / Preview pair. The buttons
  // carry the target id in a data attribute and are handled by one delegated
  // listener, so adding a card costs no wiring.
  function shareCard(id, title, dek, body, note) {
    return `<section class="sharecard-wrap">` +
      `<div class="sharecard" id="${esc(id)}">` +
        `<div class="sc-top"><span class="sc-league">${esc(CONFIG.leagues[state.league].name)}</span>` +
        `<span class="sc-season">${esc(state.season)} season</span></div>` +
        `<h3 class="sc-head">${esc(title)}</h3>` +
        (dek ? `<div class="sc-dek">${dek}</div>` : '') +
        body +
        (note ? `<div class="sc-note">${note}</div>` : '') +
        `<div class="sc-foot"><span>Commish Hub</span><span>${esc(seasonStamp())}</span></div>` +
      `</div>` +
      `<div class="card-actions"><button type="button" class="btn" data-save="${esc(id)}">Save image</button>` +
      `<button type="button" class="btn ghost" data-preview="${esc(id)}">Preview image</button>` +
      `<span class="hint">On a phone: Preview, then long-press the picture to save it.</span></div>` +
      `</section>`;
  }

  /* An export drops the controls, so the card itself has to say what is missing
     or the image quietly claims the league is smaller than it is. */
  function hiddenNote(zeros, why) {
    if (!zeros || !state.hideZero) return '';
    return `${zeros} row${zeros === 1 ? '' : 's'} hidden: they ${why}.`;
  }

  function seasonStamp() {
    const s = (SEASON && SEASON.generated) || '';
    return s ? 'Through ' + s.replace('T', ' ').slice(0, 10) : '';
  }

  /* The controls above a grid. `zeros` is how many rows carry nothing; pass it
     and a Hide/Show $0 button appears, labelled with the count so the state of
     the filter is never a guess. Both controls are hidden in an export. */
  function gridToggle(zeros, unit) {
    const modes = `<div class="gtoggle" role="group" aria-label="Cell values">` +
      ['weekly', 'running'].map((m) =>
        `<button type="button" class="gt ${state.gridMode === m ? 'on' : ''}" data-gmode="${m}">` +
        (m === 'weekly' ? 'Per week' : 'Running total') + '</button>').join('') + '</div>';
    if (!zeros) return `<div class="gctl">${modes}</div>`;
    const label = state.hideZero
      ? `Show ${zeros} ${unit || '$0'} row${zeros === 1 ? '' : 's'}`
      : `Hide ${zeros} ${unit || '$0'} row${zeros === 1 ? '' : 's'}`;
    return `<div class="gctl">${modes}` +
      `<button type="button" class="gt zt ${state.hideZero ? '' : 'on'}" data-zero="1" ` +
      `aria-pressed="${state.hideZero ? 'false' : 'true'}">${esc(label)}</button></div>`;
  }

  function renderSeason() {
    const cfg = CONFIG.leagues[state.league];
    const status = $('#status');
    $('#card-wrap').hidden = true;
    const parts = [];

    const S = SEASON && (SEASON.leagues || {})[state.league];
    if (S && cfg.kind === 'pickem') parts.push(...iwCards(S));
    else if (S && cfg.kind === 'chopped') parts.push(kjCard(S));

    const W = WAIVERS && (WAIVERS.leagues || {})[state.league];
    if (W && !W.error) parts.push(...waiverPanels(W));
    else if (['chopped', 'h2h'].includes(cfg.kind)) {
      parts.push(panel('Waiver wire', 'Rebuilt every Wednesday at 11am ET',
        W && W.error ? `<div class="empty">The waiver script failed: ${esc(W.error)}</div>`
          : '<div class="empty">No waiver analysis built yet. Run: python scripts/build_waivers.py</div>'));
    }

    if (!parts.length) {
      $('#evidence').innerHTML = '';
      return fail(`No season totals for ${cfg.name} yet.` +
        (SEASON ? '' : ` Run: python scripts/build_season.py --season ${state.season}`));
    }
    status.hidden = true; status.classList.remove('err');
    $('#evidence').innerHTML = parts.join('');
    $('#foot').innerHTML = `Season totals rolled up ${esc((SEASON && SEASON.generated || '').replace('T', ' ').slice(0, 16))}` +
      (WAIVERS ? ` &middot; waivers through week ${esc(WAIVERS.through_week)}` : '') +
      ` &middot; <a href="${esc(CONFIG.site.other_league_url)}" target="_blank" rel="noopener">The Other League recap &rarr;</a>`;
  }

  /* ---- Infinity War: money and picks ---------------------------------- */
  function iwCards(L) {
    const D = iwSeason(L);
    const last = D.last;
    // The week-18 column is tinted while it is still ahead of us, so a trophy
    // sitting in it never reads as a settled result.
    const soft = D.final ? [] : [last];
    const trophyOf = (r) => (r.place
      ? `<span class="trophy${D.final && !r.tied_at ? '' : ' proj'}" title="${r.place === 1 ? 'First' : 'Second'} place` +
        `${r.tied_at ? `, ${r.tied_at}-way tie` : ''}, ${money(D.prize[r.place])}">${TROPHY[r.place]}</span>`
      : '');
    const prizeNote = D.final
      ? `Season prizes paid: ${money(D.prize[1])} to first, ${money(D.prize[2])} to second.`
      : `Season prizes (${money(D.prize[1])} / ${money(D.prize[2])}) are awarded after week ${last}. The trophies below are where it stands today, not a result.`;
    const tieNote = Object.keys(D.tied).length
      ? ` <b>Tied for ${Object.keys(D.tied).map((k) => `${(k === '1' ? 'first' : 'second')} (${D.tied[k]}-way)`).join(' and ')}</b> ` +
        `on correct picks, so that prize is not counted in anyone's total -- the pool has no season tiebreaker on record.`
      : '';

    // Money. Weekly pot to the one winner, plus the season prize in the week-18
    // column, so the last column is every dollar the entry has taken.
    const moneyRows = [...D.rows].sort((a, b) => (b.money_total + b.prize) - (a.money_total + a.prize) ||
      b.correct_total - a.correct_total || a.handle.localeCompare(b.handle));
    // A $0 row here is an entry that has taken neither a weekly pot nor a
    // (settled) season prize. A tied trophy is not money, so it does not save a
    // row from the filter -- the trophy is still on the grid when the rows are
    // shown, and the tie note above says it either way.
    const moneyZeros = moneyRows.filter((r) => !(r.money_total + r.prize)).length;
    const moneyGrid = grid({
      weeks: D.weeks, rows: moneyRows, softWeeks: soft, totalHead: 'Season $',
      isZero: (r) => !(r.money_total + r.prize),
      step: (r, w) => r.money[w] || 0,
      cell: (r, w, run) => {
        const t = w === last ? trophyOf(r) : '';
        const won = r.money[w] || 0;
        if (run != null) return (run ? `<span class="v">${money(run)}</span>` : '<span class="z">—</span>') + t;
        return (won ? `<span class="v win">${money(won)}</span>` : '<span class="z">—</span>') + t;
      },
      total: (r) => `<b>${money(r.money_total + r.prize)}</b>` +
        (r.prize ? `<div class="sub${D.final ? '' : ' proj'}">${money(r.money_total)} weekly + ${money(r.prize)}</div>` :
          r.tied_at ? `<div class="sub proj">+ ${money(D.prize[r.place])}? ${r.tied_at}-way tie</div>` : ''),
      rowClass: (r) => (r.place === 1 ? 'hl-good' : ''),
    });
    const rolled = D.weeks.filter((w) => (L.weeks[String(w)] || {}).rollover);
    const moneyDek = `${money((L.payouts || {}).weekly || 20)} a week to the most correct, never split: a tie goes to the Monday-night tiebreaker and a tie on that rolls the pot forward. ` +
      (rolled.length ? `Rolled over: week ${rolled.join(', ')}.` : '') + ' ' + prizeNote + tieNote;

    // Picks correct. Same layout, same trophies -- the season money IS this
    // ranking, so showing them apart would invite two different answers.
    const pickRows = [...D.rows].sort((a, b) => b.correct_total - a.correct_total || a.handle.localeCompare(b.handle));
    const pickGrid = grid({
      weeks: D.weeks, rows: pickRows, softWeeks: soft, totalHead: 'Correct',
      step: (r, w) => r.correct[w] || 0,
      cell: (r, w, run) => {
        const t = w === last ? trophyOf(r) : '';
        const c = r.correct[w];
        if (run != null) return (run ? `<span class="v">${run}</span>` : '<span class="z">—</span>') + t;
        const W = L.weeks[String(w)] || {};
        const best = W.best != null && c === W.best && c > 0;
        return (c == null ? '<span class="z">—</span>' : `<span class="v${best ? ' win' : ''}">${c}</span>`) + t;
      },
      total: (r) => `<b>${r.correct_total}</b>`,
      rowClass: (r) => (r.place === 1 ? 'hl-good' : ''),
    });
    const lim = 8;
    const pickDek = `Correct picks out of ${lim} a week, graded against final scores. A highlighted cell tied or set that week's best. ` + prizeNote + tieNote;
    const check = pickCheck(L, D);

    return [
      shareCard('sc-iw-money', 'Money won, week by week', moneyDek,
        gridToggle(moneyZeros) + moneyGrid, hiddenNote(moneyZeros, 'have not won a dollar yet')),
      // No filter on the picks grid: everyone has a pick count, and a 0 there
      // would mean "submitted no card", which is worth seeing rather than hiding.
      shareCard('sc-iw-picks', 'Correct picks, week by week', pickDek, gridToggle() + pickGrid, check),
    ];
  }

  // Sleeper keeps its own running total. Ours is graded here against ESPN
  // finals, and they have agreed so far -- but if they ever part, the page says
  // so rather than quietly showing one of two numbers.
  function pickCheck(L, D) {
    const sp = L.sleeper_points || {};
    const off = D.rows.filter((r) => sp[r.handle] != null && Math.abs(sp[r.handle] - r.correct_total) > 0.01);
    if (!off.length) return '';
    return `<b>Heads up:</b> Sleeper's own total disagrees for ` +
      off.slice(0, 4).map((r) => `${esc(r.handle)} (${sp[r.handle]} vs ${r.correct_total})`).join(', ') +
      `. The figures above are graded from final scores; Sleeper's are its own.`;
  }

  /* ---- King's Justice: the weekly high ------------------------------- */
  function kjCard(L) {
    const D = kjSeason(L);
    const prize = ((L.payouts || {}).weekly_high) || 25;
    const rows = [...D.rows].sort((a, b) => b.total - a.total || a.handle.localeCompare(b.handle));
    const zeros = rows.filter((r) => !r.total).length;
    const g = grid({
      weeks: D.weeks, rows, totalHead: 'Season $',
      isZero: (r) => !r.total,
      step: (r, w) => (r.wins[w] != null ? prize : 0),
      cell: (r, w, run) => {
        if (run != null) return run ? `<span class="v">${money(run)}</span>` : '<span class="z">—</span>';
        const p = r.wins[w];
        return p == null ? '<span class="z">—</span>'
          : `<span class="v win">${f2(p)}</span><div class="sub">${money(prize)}</div>`;
      },
      total: (r) => (r.total ? `<b>${money(r.total)}</b><div class="sub">${r.n} week${r.n === 1 ? '' : 's'}</div>` : '<span class="z">$0</span>'),
      rowClass: (r) => (r.total ? '' : 'dim'),
    });
    const taken = D.rows.filter((r) => r.n).length;
    const paid = D.rows.reduce((a, r) => a + r.total, 0);
    const dek = `${money(prize)} to the highest score each week. A cell shows the score that won it; blank means they did not. ` +
      `${money(paid)} paid out over ${D.weeks.length} week${D.weeks.length === 1 ? '' : 's'}, split between ${taken} team${taken === 1 ? '' : 's'}. ` +
      `The season prizes are not on this table -- this league is chopped, so first and second are settled whenever the field gets down to two.`;
    return shareCard('sc-kj-money', 'Weekly high money', dek, gridToggle(zeros) + g,
      hiddenNote(zeros, 'have never taken the weekly high'));
  }

  /* Money wasted at auction, week by week and cumulatively -- the same
     weeks-across / total-at-the-right shape as the money grids, and savable on
     its own. A cell is the winning bid minus the next-best bid, summed over
     that week's contested claims; blank means they won nothing contested. */
  function wasteCard(W) {
    const weeks = (W.weeks || []).slice().sort((a, b) => a - b);
    const rows = (W.owners || []).map((o) => ({
      handle: o.handle, name: o.name,
      week: Object.fromEntries(weeks.map((w) => [w, (o.by_week[String(w)] || {}).waste || 0])),
      total: o.waste, contested: o.contested_won, rate: o.waste_rate,
    })).sort((a, b) => b.total - a.total || a.handle.localeCompare(b.handle));
    const worst = (W.claims || []).filter((c) => c.waste > 0)
      .sort((a, b) => b.waste - a.waste).slice(0, 3);
    const zeros = rows.filter((r) => !r.total).length;
    const g = grid({
      weeks, rows, nameHead: 'Owner', totalHead: 'Wasted',
      isZero: (r) => !r.total,
      step: (r, w) => r.week[w] || 0,
      cell: (r, w, run) => {
        const v = run != null ? run : r.week[w];
        return v ? `<span class="v bad">${money(v)}</span>` : '<span class="z">—</span>';
      },
      total: (r) => (r.total
        ? `<b class="bad">${money(r.total)}</b>` +
          (r.rate != null ? `<div class="sub">${Math.round(r.rate * 100)}% of contested</div>` : '')
        : '<span class="z">$0</span>'),
      rowClass: (r) => (r.total ? '' : 'dim'),
    });
    const dek = `The winning bid minus the next-best bid on every contested claim, added up. ` +
      `${money(T_of(W).waste)} of ${money(T_of(W).contested_spend)} in contested bidding went in the bin -- ` +
      `money that bought nothing, because the claim was already won at the price below. ` +
      `Uncontested claims are excluded: there is no runner-up to have paid instead.`;
    const note = worst.length
      ? 'Worst of the season: ' + worst.map((c) =>
          `${esc(nameFor(c.handle))} paid ${money(c.bid)} for ${esc(c.player)} in week ${c.week} ` +
          `with the next bid at ${money(c.runner_up)} (<b>${money(c.waste)}</b> wasted)`).join('; ') + '.'
      : '';
    const hid = hiddenNote(zeros, 'have wasted nothing -- no contested claim, or they won it at the next-best bid');
    return shareCard('sc-waste', 'Money wasted at auction', dek, gridToggle(zeros) + g,
      [note, hid].filter(Boolean).join(' '));
  }

  function T_of(W) { return W.totals || {}; }

  /* ---- waivers -------------------------------------------------------- */
  function waiverPanels(W) {
    const T = W.totals || {};
    const own = W.owners || [];
    const mny = (n) => (n ? money(n) : '<span class="z">$0</span>');

    // The ledger. One row an owner, every metric the analysis defines.
    const ledger = own.map((o) => {
      const cls = o.spent === 0 && o.lost ? 'dim' : '';
      return `<tr class="${cls}"><th class="gname" scope="row">${esc(o.name || o.handle)}</th>` +
        `<td class="num"><b>${mny(o.spent)}</b></td>` +
        `<td class="num">${o.won}<span class="muted">/${o.bids}</span></td>` +
        `<td class="num ${o.win_rate != null && o.win_rate < 0.4 ? 'bad' : ''}">${o.win_rate == null ? '<span class="z">—</span>' : Math.round(o.win_rate * 100) + '%'}</td>` +
        `<td class="num ${o.waste > 0 ? 'bad' : ''}">${o.waste ? '<b>' + money(o.waste) + '</b>' : '<span class="z">$0</span>'}` +
          `${o.waste_rate != null ? `<div class="sub">${Math.round(o.waste_rate * 100)}% of contested</div>` : ''}</td>` +
        `<td class="num muted">${mny(o.solo_spend)}</td>` +
        `<td class="num">${f2(o.points_started)}</td>` +
        `<td class="num ${o.cost_per_point == null ? 'bad' : ''}">${o.cost_per_point == null ? (o.spent ? 'dead' : '<span class="z">—</span>') : '$' + f2(o.cost_per_point)}</td>` +
        `<td class="num muted">${o.budget_left == null ? '—' : money(o.budget_left)}</td></tr>`;
    }).join('');
    const ledgerCard = shareCard('sc-waivers', 'Waiver spending',
      `${mny(T.spent)} across ${T.claims || 0} winning claims, ${T.failed || 0} failed. ` +
      `<b>Wasted</b> is the winning bid minus the next-best bid on a contested claim -- bid ${mny(400)} ` +
      `against a next-best ${mny(150)} and you own the player either way, so ${mny(250)} went in the bin. ` +
      `<b>Solo</b> is spend on claims nobody else bid on, which wastes nothing by this measure because ` +
      `there was no runner-up to have paid instead. ` +
      `<b>$/pt</b> divides spend by the points those players actually STARTED for; "dead" means money spent and nothing started.`,
      `<div class="gridwrap"><table class="grid"><thead><tr><th class="gname">Owner</th>` +
      `<th class="num">Spent</th><th class="num">Won</th><th class="num">Win%</th><th class="num">Wasted</th>` +
      `<th class="num">Solo</th><th class="num">Pts</th><th class="num">$/pt</th>` +
      `<th class="num gtotal">Left</th></tr></thead><tbody>${ledger}</tbody></table></div>`,
      `Through week ${esc(W.through_week)}. FAAB budget ${W.budget == null ? 'not set' : money(W.budget)}.`);

    // Best and worst, computed in the script so the page can't rank it a
    // second, different way.
    const aw = (W.awards || []).map((a) =>
      `<div class="award"><div class="aw-label">${esc(a.label)}</div><div class="aw-who">${esc(a.name || a.handle)}</div>` +
      `<div class="aw-val">${esc(a.value)}</div><div class="aw-dek">${esc(a.dek)}</div></div>`).join('');

    const bucketTbl = (obj, label, order) => {
      const keys = order || Object.keys(obj).sort((a, b) => (a === 'undrafted') - (b === 'undrafted') || (+a) - (+b));
      const rows = keys.filter((k) => obj[k]).map((k) => {
        const b = obj[k];
        return `<tr><td>${esc(k === 'undrafted' ? 'Undrafted' : (label === 'Round' ? 'Round ' + k : k))}</td>` +
          `<td class="num"><b>${mny(b.spent)}</b></td><td class="num">${b.won}</td>` +
          `<td class="num muted">${b.won ? '$' + f2(b.spent / b.won) : '—'}</td>` +
          `<td class="num ${b.waste ? 'bad' : 'muted'}">${mny(b.waste || 0)}</td>` +
          `<td class="num muted">${b.lost || 0}${b.lost_bid ? ` <span class="sub">${money(b.lost_bid)}</span>` : ''}</td></tr>`;
      }).join('');
      return tbl(`<th>${esc(label)}</th><th class="num">Spent</th><th class="num">Won</th><th class="num">Avg</th><th class="num">Wasted</th><th class="num">Lost bids</th>`, rows);
    };

    const claims = (W.claims || []).slice(0, 20).map((c) => {
      const waste = c.bid - c.points_started;
      return `<tr><td>${esc(c.player)} <span class="sub">${esc(c.pos)}${c.round ? ' &middot; rd ' + c.round : ' &middot; undrafted'}</span></td>` +
        `<td>${esc(nameFor(c.handle))}<div class="sub">wk ${c.week}</div></td>` +
        `<td class="num"><b>${money(c.bid)}</b>${c.bidders > 1 ? `<div class="sub">next ${money(c.runner_up)}</div>` : '<div class="sub">uncontested</div>'}</td>` +
        `<td class="num ${c.points_started > c.bid ? 'good' : (waste > 10 ? 'bad' : '')}">${f2(c.points_started)}<div class="sub">${c.starts} start${c.starts === 1 ? '' : 's'}</div></td></tr>`;
    }).join('');

    const overpays = (W.claims || []).filter((c) => c.waste > 0)
      .sort((a, b) => b.waste - a.waste).slice(0, 15).map((c) =>
        `<tr><td>${esc(c.player)} <span class="sub">${esc(c.pos)}${c.round ? ' &middot; rd ' + c.round : ' &middot; undrafted'}</span></td>` +
        `<td>${esc(nameFor(c.handle))}<div class="sub">wk ${c.week}</div></td>` +
        `<td class="num"><b>${money(c.bid)}</b></td><td class="num muted">${money(c.runner_up)}</td>` +
        `<td class="num bad"><b>${money(c.waste)}</b></td></tr>`).join('');

    const shut = own.filter((o) => o.lost).sort((a, b) => b.lost_bid_total - a.lost_bid_total).map((o) =>
      `<tr class="${o.shutout_streak >= 2 ? 'hl-warn' : ''}"><td>${esc(o.name || o.handle)}</td>` +
      `<td class="num">${o.lost}</td><td class="num">${money(o.lost_bid_total)}</td>` +
      `<td class="num">${o.shutout_streak || '—'}</td>` +
      `<td class="muted">${o.shutout_weeks.length ? 'wk ' + o.shutout_weeks.join(', ') : '—'}</td></tr>`).join('');

    return [
      ledgerCard,
      wasteCard(W),
      aw ? panel('Best and worst spenders', 'Cumulative, through week ' + esc(W.through_week), `<div class="awards">${aw}</div>`) : '',
      panel('Spend by draft round', 'What the room paid in August against what it pays now. The round is the player\'s original pick in THIS league\'s draft; undrafted is its own bucket.',
        bucketTbl(T.by_round || {}, 'Round')),
      panel('Spend by position', '', bucketTbl(T.by_pos || {}, 'Pos', Object.keys(T.by_pos || {}).sort((a, b) => (T.by_pos[b].spent - T.by_pos[a].spent)))),
      panel('Biggest claims', 'And what they have returned in started lineups since',
        claims ? tbl('<th>Player</th><th>Won by</th><th class="num">Bid</th><th class="num">Started pts</th>', claims) : '<div class="empty">No claims yet.</div>'),
      overpays ? panel('Biggest overpays', 'Contested claims won by the widest margin over the next-best bid. Every dollar in the last column bought nothing.',
        tbl('<th>Player</th><th>Won by</th><th class="num">Paid</th><th class="num">Next bid</th><th class="num">Wasted</th>', overpays)) : '',
      panel('Who keeps losing out', 'Failed claims, money bid and lost, and the current run of weeks bidding with nothing to show',
        shut ? tbl('<th>Owner</th><th class="num">Lost</th><th class="num">$ lost</th><th class="num">Streak</th><th>Shut out</th>', shut) : '<div class="empty">Nobody has lost a claim yet.</div>'),
    ].filter(Boolean);
  }

  /* ---------------------------------------------------------------- helpers */
  function nameFor(handle) {
    const names = CONFIG.leagues[state.league].names || {};
    return names[handle] || handle;
  }
  function panel(title, dek, body) {
    return `<div class="panel"><h3>${title}</h3>${dek ? `<div class="dek">${dek}</div>` : ''}${body}</div>`;
  }
  function tbl(head, rows) {
    return rows ? `<div class="tbl-wrap"><table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>` : '<div class="empty">Nothing here.</div>';
  }

  /* ---------------------------------------------------------------- export */
  function exportCard(mode) {
    return exportEl($('#recap-card'), `${state.league}-${state.season}-week-${state.week}.png`, mode);
  }

  /* Render any element to a PNG. `.exporting` widens the node and unclips its
     scrollers, which is what makes an 18-week grid come out whole instead of
     cropped to the phone's viewport. */
  async function exportEl(card, name, mode) {
    if (!card) return;
    const btns = [...document.querySelectorAll('.btn')];
    btns.forEach((b) => { b.disabled = true; });
    card.classList.add('exporting');
    try {
      const canvas = await html2canvas(card, { scale: 2, backgroundColor: '#0f1115', useCORS: true, logging: false,
                                               windowWidth: Math.max(card.scrollWidth + 80, 900) });
      card.classList.remove('exporting');
      if (mode === 'preview') {
        $('#overlay-img').src = canvas.toDataURL('image/png');
        $('#overlay').hidden = false;
      } else {
        canvas.toBlob((blob) => {
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
          setTimeout(() => URL.revokeObjectURL(url), 5000);
        }, 'image/png');
      }
    } catch (e) {
      card.classList.remove('exporting');
      alert('Could not render the image: ' + e.message);
    } finally {
      btns.forEach((b) => { b.disabled = false; });
    }
  }

  window.addEventListener('hashchange', () => {
    const before = { ...state };
    readHash();
    if (state.season !== before.season) { loadSeason(); }
    else if (state.week !== before.week) { $('#week-select').value = String(state.week); loadWeek(); }
    else if (state.league !== before.league) render();
  });

  boot();
})();
