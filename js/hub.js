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

  let CONFIG = null, INDEX = null, RECAPS = null, WEEK = null;
  const state = { league: null, season: null, week: null };

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
    $('#week-select').onchange = (e) => { state.week = +e.target.value; loadWeek(); };
    $('#btn-save').onclick = () => exportCard('save');
    $('#btn-preview').onclick = () => exportCard('preview');
    $('#btn-close').onclick = () => { $('#overlay').hidden = true; };
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
    if (m[2]) state.week = +m[2];
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
    const weeks = Object.keys(INDEX.weeks).map(Number).sort((a, b) => a - b);
    if (!weeks.length) {
      $('#card-wrap').hidden = true; $('#evidence').innerHTML = '';
      return fail(`No weeks built for ${state.season} yet. Run: python scripts/build_week.py --week N`);
    }
    if (!state.week || !weeks.includes(state.week)) state.week = weeks[weeks.length - 1];
    fillSelect($('#week-select'), weeks.map((w) => [w, `Week ${w}${INDEX.weeks[w].final ? '' : ' (live)'}`]), state.week);
    await loadWeek();
  }

  async function loadWeek() {
    $('#status').hidden = false; $('#status').textContent = 'Loading…';
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
  async function exportCard(mode) {
    const card = $('#recap-card');
    const btn = $('#btn-save'), btn2 = $('#btn-preview');
    btn.disabled = btn2.disabled = true;
    card.classList.add('exporting');
    try {
      const canvas = await html2canvas(card, { scale: 2, backgroundColor: '#0f1115', useCORS: true, logging: false });
      card.classList.remove('exporting');
      const name = `${state.league}-${state.season}-week-${state.week}.png`;
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
      btn.disabled = btn2.disabled = false;
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
