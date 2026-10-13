#!/usr/bin/env python3
"""
outlook.py -- power rankings and playoff/title odds for a head-to-head league.

Runs inside build_week.py for every h2h league with "outlook": true in
data/config.json, and writes leagues.<key>.outlook into the week file. Run it
on its own to (re)write only that key in an existing week file:

    python scripts/outlook.py --week 5                 # every outlook league
    python scripts/outlook.py --week 5 --only two_mitchs --sims 2000

POWER RANKINGS (results only, weeks 1..N)
  All-play record: every team against all eleven others every week, so the
  schedule's luck is gone. Blended, as z-scores:
      50% all-play win %    30% points per game    20% last three weeks' PPG
  Luck = actual wins minus the wins the all-play rate says you'd have.

PLAYOFF + TITLE ODDS (Monte Carlo over the rest of the season)
  * Current Sleeper rosters, not draft rosters.
  * Sleeper's projection for every player for every remaining week, rescored
    with the league's own scoring settings. A player on bye or ruled out
    projects zero, so the lineup subs around him.
  * Each team starts its best lineup BY PROJECTION (what a manager can know
    before kickoff), then the week is played out with randomness: a season-
    long error on each player's projection, a weekly swing per player, and a
    shared team-wide swing (TEAM_CV). Without the randomness every game goes
    to the higher projection and every team is 0% or 100%.
  * An empty slot is streamed at 80% of the best unrostered player there.
  * Real results for weeks 1..N; weeks N+1..14 simulated. Top 6 make it, by
    wins then points for. Week 15: 3v6 and 4v5, 1 and 2 on bye. Week 16: 1 v
    the 4/5 winner, 2 v the 3/6 winner. Week 17: the final.

Calibration: simulated team weekly scores must swing 25-28% (sd / mean), the
same band as ../2-mitchs-1-cup/season_sim.py. The result carries `in_band`;
the page and the recaps do not publish odds when it is false.
"""
import argparse
import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict

import build_week as BW

REGULAR_WEEKS = 14
PLAYOFF_WEEKS = (15, 16, 17)
PLAYOFF_TEAMS = 6
SIMS = 10000
CAL_BAND = (25.0, 28.0)

# Same risk model as 2-mitchs-1-cup/season_sim.py, except TEAM_CV. That was
# 0.15 there and came out 0.4 under the band every week. The owner approved
# raising it on 2026-10-12; in this model 0.16 still read 24.8-26.9% on week 4,
# 0.17 read 25.5-27.6% and 0.18 overshot (28.2%), so 0.17.
BASE_CV = {'QB': 0.30, 'RB': 0.44, 'WR': 0.50, 'TE': 0.54, 'K': 0.40, 'DEF': 0.60}   # weekly swing
TALENT_CV = {'QB': 0.20, 'RB': 0.28, 'WR': 0.30, 'TE': 0.32, 'K': 0.20, 'DEF': 0.30}  # projection error
TEAM_CV = 0.17                                                                        # shared team swing
STREAM_FRAC = 0.80

POWER_WEIGHTS = (('allplay_pct', 0.5), ('ppg', 0.3), ('last3', 0.2))


def lognorm(cv):
    """(mu, sigma) of a lognormal with mean 1 and the given coefficient of variation."""
    s2 = math.log(1 + cv * cv)
    return -s2 / 2, math.sqrt(s2)


# ---------------------------------------------------------------- results
def results(lid, through):
    """{week: {roster_id: points}} and {week: [(a, b), ...]} for weeks 1..through."""
    pts, pairs = {}, {}
    for wk in range(1, through + 1):
        m = BW.get(f'{BW.REST}/league/{lid}/matchups/{wk}', cacheable=False)
        pts[wk] = {e['roster_id']: e.get('points') or 0.0 for e in m}
        pairs[wk] = matchup_pairs(m)
    return pts, pairs


def matchup_pairs(entries):
    by = defaultdict(list)
    for e in entries:
        if e.get('matchup_id') is not None:
            by[e['matchup_id']].append(e['roster_id'])
    return [tuple(v) for v in by.values() if len(v) == 2]


def records(pts, pairs, weeks):
    w = defaultdict(float); l = defaultdict(float); pf = defaultdict(float)
    for wk in weeks:
        for a, b in pairs[wk]:
            pa, pb = pts[wk].get(a, 0), pts[wk].get(b, 0)
            if pa > pb: w[a] += 1; l[b] += 1
            elif pb > pa: w[b] += 1; l[a] += 1
            else: w[a] += .5; w[b] += .5; l[a] += .5; l[b] += .5
        for r, p in pts[wk].items():
            pf[r] += p
    return w, l, pf


def fmt_record(w, l):
    t = 0.0
    if w != int(w):  # a tie shows as a half win and a half loss
        t, w, l = 1.0, w - .5, l - .5
    return f'{int(w)}-{int(l)}' + (f'-{int(t)}' if t else '')


# ---------------------------------------------------------------- power
def power(pts, pairs, through, rids):
    """Power ranking from results through `through`. Returns {rid: row}."""
    weeks = list(range(1, through + 1))
    w, l, pf = records(pts, pairs, weeks)
    rows = {}
    for r in rids:
        apw = apl = 0.0
        for wk in weeks:
            me = pts[wk].get(r, 0)
            for o in rids:
                if o == r:
                    continue
                them = pts[wk].get(o, 0)
                if me > them: apw += 1
                elif me < them: apl += 1
                else: apw += .5; apl += .5
        last = weeks[-3:]
        rows[r] = {
            'wins': w[r], 'losses': l[r], 'record': fmt_record(w[r], l[r]),
            'allplay_w': apw, 'allplay_l': apl, 'allplay_pct': apw / (apw + apl) if apw + apl else 0,
            'ppg': pf[r] / len(weeks), 'last3': sum(pts[wk].get(r, 0) for wk in last) / len(last),
            'pf': pf[r],
        }
    for key, wt in POWER_WEIGHTS:
        vals = [rows[r][key] for r in rids]
        mu, sd = statistics.mean(vals), statistics.pstdev(vals) or 1.0
        for r in rids:
            rows[r]['score'] = rows[r].get('score', 0.0) + wt * (rows[r][key] - mu) / sd
    for r in rids:
        x = rows[r]
        x['luck'] = x['wins'] - x['allplay_pct'] * len(weeks)
    for i, r in enumerate(sorted(rids, key=lambda r: (-rows[r]['score'], -rows[r]['pf']))):
        rows[r]['rank'] = i + 1
    return rows


# ---------------------------------------------------------------- projections
def lineup_slots(slot_list):
    """Fill order: strict slots first, then the narrowest flex first, so a TE
    is saved for FLEX rather than burned where only RB/WR could go."""
    slots = [s for s in slot_list if s in BW.SLOT_ELIGIBILITY]
    return sorted(slots, key=lambda s: len(BW.SLOT_ELIGIBILITY[s]))


def week_projection(season, wk, calc):
    """player_id -> (pos, projected points under league scoring)."""
    pos = '&'.join(f'position[]={p}' for p in ('QB', 'RB', 'WR', 'TE', 'K', 'DEF'))
    raw = BW.get(f'{BW.BASE}/projections/nfl/{season}/{wk}?season_type=regular&{pos}', cacheable=False)
    out = {}
    for row in raw:
        pid = row.get('player_id')
        p = (row.get('player') or {}).get('position') or ''
        if pid and p:
            out[str(pid)] = (p, max(0.0, calc(row.get('stats') or {}, p)))
    return out


def plan_week(roster, proj, slots, stream):
    """Best lineup by projection: [(pid or None, pos, mu)] one per slot."""
    pool = sorted(((proj[p][1], p, proj[p][0]) for p in roster if p in proj and proj[p][1] > 0), reverse=True)
    used, plan = set(), []
    for s in slots:
        ok = BW.SLOT_ELIGIBILITY[s]
        pick = next((x for x in pool if x[1] not in used and x[2] in ok), None)
        if pick:
            used.add(pick[1]); plan.append((pick[1], pick[2], pick[0]))
        else:
            best = max(ok, key=lambda q: stream.get(q, 0))
            plan.append((None, best, stream.get(best, 0)))
    return plan


def stream_values(proj, rostered):
    """Per position: 80% of the best unrostered projection that week."""
    best = defaultdict(float)
    for pid, (pos, mu) in proj.items():
        if pid not in rostered and mu > best[pos]:
            best[pos] = mu
    return {pos: STREAM_FRAC * v for pos, v in best.items()}


# ---------------------------------------------------------------- simulation
def simulate(rids, pts, pairs, through, future, plans, pf_pos, sims, seed):
    """`future[wk]` = pairs; `plans[wk][rid]` = lineup. Returns per-team tallies
    and the calibration range."""
    rnd = random.Random(seed)
    W0, L0, PF0 = records(pts, pairs, range(1, through + 1))
    shock = lognorm(TEAM_CV)
    wkly = {p: lognorm(BASE_CV.get(p, 0.5)) for p in pf_pos}
    tal = {p: lognorm(TALENT_CV.get(p, 0.3)) for p in pf_pos}
    players = {}
    for wk in plans:
        for plan in plans[wk].values():
            for pid, pos, _ in plan:
                if pid:
                    players[pid] = pos
    tally = {r: defaultdict(float) for r in rids}
    seeds = {r: [0] * PLAYOFF_TEAMS for r in rids}
    cal = defaultdict(lambda: [0.0, 0.0, 0])  # rid -> sum, sumsq, n

    def score(r, wk, talent):
        tot = 0.0
        for pid, pos, mu in plans[wk][r]:
            if mu <= 0:
                continue
            m, s = wkly[pos]
            x = mu * math.exp(m + s * rnd.gauss(0, 1))
            if pid:
                x *= talent[pid]
            tot += x
        m, s = shock
        return tot * math.exp(m + s * rnd.gauss(0, 1))

    for _ in range(sims):
        talent = {pid: math.exp(tal[pos][0] + tal[pos][1] * rnd.gauss(0, 1)) for pid, pos in players.items()}
        w = dict(W0); pf = dict(PF0)
        for r in rids:
            w.setdefault(r, 0.0); pf.setdefault(r, 0.0)
        for wk in sorted(future):
            sc = {r: score(r, wk, talent) for r in rids}
            for r, x in sc.items():
                pf[r] += x
                c = cal[r]; c[0] += x; c[1] += x * x; c[2] += 1
            for a, b in future[wk]:
                if sc[a] > sc[b]: w[a] += 1
                elif sc[b] > sc[a]: w[b] += 1
                else: w[a] += .5; w[b] += .5
        order = sorted(rids, key=lambda r: (-w[r], -pf[r]))
        for i, r in enumerate(order):
            t = tally[r]
            t['wins'] += w[r]; t['pf'] += pf[r]
            if i < PLAYOFF_TEAMS:
                t['playoff'] += 1; seeds[r][i] += 1
            if i < 2:
                t['bye'] += 1
        s = order[:PLAYOFF_TEAMS]
        wk1, wk2, wk3 = PLAYOFF_WEEKS

        def game(a, b, wk):
            return a if score(a, wk, talent) >= score(b, wk, talent) else b
        q45, q36 = game(s[3], s[4], wk1), game(s[2], s[5], wk1)
        f1, f2 = game(s[0], q45, wk2), game(s[1], q36, wk2)
        for r in (f1, f2):
            tally[r]['final'] += 1
        tally[game(f1, f2, wk3)]['title'] += 1

    cvs = []
    for r, (sm, sq, n) in cal.items():
        if n > 1:
            mean = sm / n
            cvs.append(100 * math.sqrt(max(0.0, sq / n - mean * mean)) / mean)
    return tally, seeds, (min(cvs), max(cvs)) if cvs else None


# ---------------------------------------------------------------- entry point
def build_outlook(cfg, season, week, league, teams, calc, slot_list, sims=SIMS, prev=None, odds=True):
    """The `outlook` block for one league after `week`. `prev` is last week's
    outlook block (for movement), or None. `odds=False` writes the power
    rankings only: a past week's odds can't be rebuilt honestly, because
    Sleeper serves today's rosters and projections, not that week's."""
    lid = cfg['ids'][str(season)]
    rids = sorted(teams)
    pts, pairs = results(lid, week)
    now = power(pts, pairs, week, rids)
    before = power(pts, pairs, week - 1, rids) if week > 1 else None
    name = lambda r: teams[r]['name']
    out = {
        'through_week': week,
        'power': [{
            'rank': now[r]['rank'], 'prev_rank': before[r]['rank'] if before else None,
            'name': name(r), 'handle': teams[r]['handle'], 'record': now[r]['record'],
            'allplay': f"{now[r]['allplay_w']:g}-{now[r]['allplay_l']:g}",
            'allplay_pct': round(100 * now[r]['allplay_pct'], 1),
            'ppg': round(now[r]['ppg'], 2), 'last3': round(now[r]['last3'], 2),
            'luck': round(now[r]['luck'], 1), 'score': round(now[r]['score'], 3),
        } for r in sorted(rids, key=lambda r: now[r]['rank'])],
        'power_weights': {k: v for k, v in POWER_WEIGHTS},
    }
    if not odds:
        out['odds'] = None
        out['odds_note'] = 'Odds start in week 5, the first week they were run live.'
        return out
    if week >= REGULAR_WEEKS:
        out['odds'] = None
        out['odds_note'] = 'Regular season over; odds are not simulated once the bracket is set.'
        return out

    rosters = BW.get(f'{BW.REST}/league/{lid}/rosters', cacheable=False)
    rostered = {str(p) for r in rosters for p in (r.get('players') or [])}
    roster_of = {r['roster_id']: [str(p) for p in (r.get('players') or [])] for r in rosters}
    slots = lineup_slots(slot_list)
    future, plans, positions = {}, {}, set()
    for wk in list(range(week + 1, REGULAR_WEEKS + 1)) + list(PLAYOFF_WEEKS):
        proj = week_projection(season, wk, calc)
        stream = stream_values(proj, rostered)
        plans[wk] = {r: plan_week(roster_of.get(r, []), proj, slots, stream) for r in rids}
        positions |= {pos for plan in plans[wk].values() for _, pos, _ in plan}
        if wk <= REGULAR_WEEKS:
            future[wk] = matchup_pairs(BW.get(f'{BW.REST}/league/{lid}/matchups/{wk}', cacheable=False))
    tally, seeds, cal = simulate(rids, pts, pairs, week, future, plans, positions, sims, seed=season * 100 + week)
    pct = lambda r, k: round(100 * tally[r][k] / sims, 1)
    prev_odds = {t['handle']: t for t in ((prev or {}).get('odds') or {}).get('teams', [])}
    rows = []
    for r in rids:
        mean_w = tally[r]['wins'] / sims
        p = prev_odds.get(teams[r]['handle']) or {}
        rows.append({
            'name': name(r), 'handle': teams[r]['handle'], 'record': now[r]['record'],
            'proj_record': f'{mean_w:.1f}-{REGULAR_WEEKS - mean_w:.1f}',
            'proj_pf': round(tally[r]['pf'] / sims, 1),
            'playoff': pct(r, 'playoff'), 'bye': pct(r, 'bye'),
            'final': pct(r, 'final'), 'title': pct(r, 'title'),
            'seed_pct': [round(100 * n / sims, 1) for n in seeds[r]],
            'prev_playoff': p.get('playoff'), 'prev_title': p.get('title'),
        })
    rows.sort(key=lambda x: (-x['playoff'], -x['title']))
    out['odds'] = {
        'sims': sims, 'team_cv': TEAM_CV,
        'calibration': [round(cal[0], 1), round(cal[1], 1)] if cal else None,
        'in_band': bool(cal) and CAL_BAND[0] <= cal[0] and cal[1] <= CAL_BAND[1],
        'teams': rows,
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--week', type=int, required=True)
    ap.add_argument('--season', type=int)
    ap.add_argument('--only', help='comma list of league keys')
    ap.add_argument('--sims', type=int, default=SIMS)
    ap.add_argument('--no-odds', action='store_true', help='power rankings only (backfilling a past week)')
    args = ap.parse_args()
    root = BW.ROOT
    with open(os.path.join(root, 'data', 'config.json'), encoding='utf-8') as f:
        config = json.load(f)
    season = args.season or config['site']['season']
    path = os.path.join(root, 'data', str(season), f'week-{args.week:02d}.json')
    with open(path, encoding='utf-8') as f:
        doc = json.load(f)
    prev_doc = {}
    prev_path = os.path.join(root, 'data', str(season), f'week-{args.week - 1:02d}.json')
    if os.path.exists(prev_path):
        with open(prev_path, encoding='utf-8') as f:
            prev_doc = json.load(f)
    only = set(args.only.split(',')) if args.only else None
    done = []
    for key, cfg in config['leagues'].items():
        if not cfg.get('outlook') or (only and key not in only):
            continue
        L = doc['leagues'].get(key)
        if not L or 'error' in L:
            print(f'  {key}: not in {os.path.basename(path)}, skipped')
            continue
        cfg = dict(cfg, key=key)
        lid = cfg['ids'][str(season)]
        league, teams = BW.league_bundle(lid, cfg.get('names') or {})
        calc = BW.make_calc_pts(league.get('scoring_settings') or {})
        slot_list = [s for s in (league.get('roster_positions') or []) if s != 'BN']
        prev = ((prev_doc.get('leagues') or {}).get(key) or {}).get('outlook')
        L['outlook'] = build_outlook(cfg, season, args.week, league, teams, calc, slot_list, args.sims, prev,
                                     odds=not args.no_odds)
        report(key, L['outlook'])
        done.append(key)
    if not done:
        sys.exit('no outlook league found')
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1)
    os.replace(tmp, path)
    print(f'wrote outlook for {", ".join(done)} into {os.path.relpath(path, root)}')


def report(key, o):
    print(f'  {key} power rankings through week {o["through_week"]}:')
    for p in o['power']:
        mv = '' if p['prev_rank'] is None else f'{p["prev_rank"] - p["rank"]:+d}'
        print(f'    {p["rank"]:>2} {mv:>3}  {p["name"]:<20} {p["record"]:>5}  all-play {p["allplay"]:>6}'
              f'  ppg {p["ppg"]:6.1f}  last3 {p["last3"]:6.1f}  luck {p["luck"]:+.1f}')
    od = o.get('odds')
    if od:
        print(f'  calibration: team weekly CV {od["calibration"][0]}%-{od["calibration"][1]}% '
              f'(target {CAL_BAND[0]:.0f}-{CAL_BAND[1]:.0f}%) -> {"OK" if od["in_band"] else "OUT OF BAND"}')
        for t in od['teams']:
            print(f'    {t["name"]:<20} {t["record"]:>5} -> {t["proj_record"]:>9}  playoff {t["playoff"]:5.1f}%'
                  f'  bye {t["bye"]:5.1f}%  title {t["title"]:5.1f}%')


if __name__ == '__main__':
    main()
