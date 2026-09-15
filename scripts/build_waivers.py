#!/usr/bin/env python3
"""
build_waivers.py -- season-long waiver wire analysis for the FAAB leagues,
written to data/<season>/waivers.json.

    python scripts/build_waivers.py                  # current season, every FAAB league
    python scripts/build_waivers.py --refresh        # ignore the cache (use this in CI)
    python scripts/build_waivers.py --only kings_justice --through 6

Runs on Wednesdays at 11am ET from .github/workflows/waivers.yml, which is the
morning after waivers clear. Everything it reads is Sleeper REST and keyless --
it deliberately does NOT touch the pick'em GraphQL, so an expired Sleeper login
can never break this job.

Sources (all /v1, all cached in scripts/_cache):
  league / users / rosters        who's who, the FAAB budget, budget used
  transactions/<week>            EVERY waiver claim, winning AND failed, with bids
  matchups/<week>                players_points + starters, for what a claim returned
  drafts -> draft/<id>/picks     the round each player originally went in

The four things it measures, defined here so nobody re-derives them differently:

  spent        sum of WINNING bids. Failed claims cost nothing.
  waste        THE HEADLINE NUMBER. On a CONTESTED claim, the winning bid minus
               the runner-up bid: bid $400 against a next-best $150 and you own
               the player either way, so $250 was thrown away. It is tracked per
               week and cumulatively, because the season figure is the one that
               settles an argument.
  solo_spend   spend on claims NOBODY ELSE BID ON, kept separate and never added
               to waste. There is no runner-up to have paid instead, so there is
               no defensible amount that was "wasted" -- the whole bid could in
               theory have been $0, which would make every uncontested claim
               100% waste and swamp the contested cases the metric is about.
               Reported beside waste so the reader can judge it themselves.
  return       the player's points AFTER the claim week, split into points
               actually STARTED by the winner and points merely ROSTERED. A guy
               you paid for and benched is still wasted money, so both are kept.
               Points come from Sleeper's own players_points, already scored
               through the league's settings.
  shut out     failed claims: how many, how much was bid and lost, and the
               current run of weeks bidding with nothing to show for it.

Per the user's ask, spend is also bucketed by the acquired player's ORIGINAL
draft round IN THAT LEAGUE'S OWN DRAFT (undrafted is its own bucket). That is
the "what the market pays in October vs what the room paid in August" read;
it is not the NFL draft.
"""

import argparse
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import build_week as bw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ET = ZoneInfo('America/New_York')

LAST_WEEK = 18
# A claim has to have returned something to be judged on value. Below this the
# cost-per-point number is noise, so the awards skip the owner entirely.
MIN_SPEND_FOR_AWARD = 10


def draft_rounds(lid, season):
    """player_id -> round they were drafted in, for this league's own draft."""
    out = {}
    try:
        drafts = bw.get(f'{bw.REST}/league/{lid}/drafts') or []
    except Exception as e:
        print(f'    no draft data: {e}', file=sys.stderr)
        return out
    for d in drafts:
        if str(d.get('season')) != str(season):
            continue
        try:
            picks = bw.get(f"{bw.REST}/draft/{d['draft_id']}/picks") or []
        except Exception as e:
            print(f'    draft picks failed: {e}', file=sys.stderr)
            continue
        for p in picks:
            pid = str(p.get('player_id') or '')
            if pid and p.get('round'):
                out[pid] = int(p['round'])
    return out


def week_points(lid, week):
    """roster_id -> ({player_id: points}, {started player ids})."""
    try:
        rows = bw.get(f'{bw.REST}/league/{lid}/matchups/{week}') or []
    except Exception:
        return {}
    out = {}
    for e in rows:
        pts = {str(k): (v or 0.0) for k, v in (e.get('players_points') or {}).items()}
        started = set(str(x) for x in (e.get('starters') or []) if x and x != '0')
        out[e['roster_id']] = (pts, started)
    return out


EMPTY_BUCKET = {'spent': 0, 'won': 0, 'lost': 0, 'lost_bid': 0, 'waste': 0}


def bucket(d, key, **kw):
    b = d.setdefault(str(key), dict(EMPTY_BUCKET))
    for k, v in kw.items():
        b[k] = b.get(k, 0) + v


def build_league(key, cfg, season, through):
    lid = cfg['ids'][str(season)]
    league, teams = bw.league_bundle(lid, cfg.get('names') or {})
    settings = league.get('settings') or {}
    budget = settings.get('waiver_budget')
    rounds = draft_rounds(lid, season)

    # --- every claim, week by week -------------------------------------
    claims, lost_bids, free_agents, weeks_seen = [], [], [], []
    for w in range(1, LAST_WEEK + 1):
        if through and w > through:
            break
        tx = bw.week_transactions(lid, w, teams, {})
        if tx['waivers'] or tx['lost_bids'] or tx['free_agents'] or tx['trades']:
            weeks_seen.append(w)
        for c in tx['waivers']:
            contested = c['bidders'] > 1
            claims.append(dict(c, week=w, round=rounds.get(str(c.get('player_id') or '')),
                               contested=contested,
                               waste=(c['bid'] - (c['runner_up'] or 0)) if contested else 0,
                               solo=0 if contested else c['bid']))
        for b in tx['lost_bids']:
            lost_bids.append(dict(b, week=w, round=rounds.get(str(b.get('player_id') or ''))))
        for a in tx['free_agents']:
            free_agents.append(dict(a, week=w))
    last_week = max(weeks_seen) if weeks_seen else 0

    # --- what each winning claim went on to return ----------------------
    by_roster = {t['handle']: rid for rid, t in teams.items()}
    pts_cache = {}
    for c in claims:
        rid = by_roster.get(c['handle'])
        started = rostered = 0.0
        starts = 0
        for w in range(c['week'], (through or last_week) + 1):
            if w not in pts_cache:
                pts_cache[w] = week_points(lid, w)
            got = (pts_cache[w].get(rid) if rid is not None else None)
            if not got:
                continue
            pts, lineup = got
            pid = str(c.get('player_id') or '')
            if pid not in pts:
                continue           # off this roster by then (dropped or traded)
            rostered += pts[pid]
            if pid in lineup:
                started += pts[pid]
                starts += 1
        c['points_started'] = round(started, 2)
        c['points_rostered'] = round(rostered, 2)
        c['starts'] = starts

    # --- per owner -------------------------------------------------------
    owners = {}
    for rid, t in teams.items():
        owners[t['handle']] = {
            'handle': t['handle'], 'name': t['name'],
            'spent': 0, 'waste': 0, 'solo_spend': 0, 'contested_spend': 0, 'contested_won': 0,
            'won': 0, 'lost': 0, 'lost_bid_total': 0,
            'free_agents': 0, 'points_started': 0.0, 'points_rostered': 0.0, 'starts': 0,
            'budget_used': (t['settings'] or {}).get('waiver_budget_used'),
            'by_week': {}, 'by_pos': {}, 'by_round': {},
            'biggest_bid': None, 'biggest_waste': None, 'worst_buy': None,
            'shutout_weeks': [], 'shutout_streak': 0,
        }
    for c in claims:
        o = owners.get(c['handle'])
        if not o:
            continue
        o['spent'] += c['bid']
        o['waste'] += c['waste']
        o['solo_spend'] += c['solo']
        if c['contested']:
            o['contested_spend'] += c['bid']
            o['contested_won'] += 1
        o['won'] += 1
        o['points_started'] += c['points_started']
        o['points_rostered'] += c['points_rostered']
        o['starts'] += c['starts']
        bucket(o['by_week'], c['week'], spent=c['bid'], won=1, waste=c['waste'])
        bucket(o['by_pos'], c['pos'] or '?', spent=c['bid'], won=1, waste=c['waste'])
        bucket(o['by_round'], c['round'] or 'undrafted', spent=c['bid'], won=1, waste=c['waste'])
        if not o['biggest_bid'] or c['bid'] > o['biggest_bid']['bid']:
            o['biggest_bid'] = c
        if not o['biggest_waste'] or c['waste'] > o['biggest_waste']['waste']:
            o['biggest_waste'] = c
        # The worst buy is the most money for the fewest started points.
        if c['bid'] > 0 and (not o['worst_buy'] or
                             (c['bid'] - c['points_started']) > (o['worst_buy']['bid'] - o['worst_buy']['points_started'])):
            o['worst_buy'] = c
    for b in lost_bids:
        o = owners.get(b['handle'])
        if not o:
            continue
        o['lost'] += 1
        o['lost_bid_total'] += b['bid']
        bucket(o['by_week'], b['week'], lost=1, lost_bid=b['bid'])
        bucket(o['by_pos'], b['pos'] or '?', lost=1, lost_bid=b['bid'])
        bucket(o['by_round'], b['round'] or 'undrafted', lost=1, lost_bid=b['bid'])
    for a in free_agents:
        if a['handle'] in owners:
            owners[a['handle']]['free_agents'] += 1

    for o in owners.values():
        # A shut-out week is one where they bid and won nothing. The streak is
        # the run of those ending at the most recent week they bid in -- that is
        # the "still can't win a claim" number, not a season count.
        bid_weeks = sorted(int(w) for w, v in o['by_week'].items() if v['won'] or v['lost'])
        o['shutout_weeks'] = [w for w in bid_weeks if not o['by_week'][str(w)]['won']]
        streak = 0
        for w in reversed(bid_weeks):
            if o['by_week'][str(w)]['won']:
                break
            streak += 1
        o['shutout_streak'] = streak
        o['bids'] = o['won'] + o['lost']
        o['win_rate'] = round(o['won'] / o['bids'], 3) if o['bids'] else None
        o['points_started'] = round(o['points_started'], 2)
        o['points_rostered'] = round(o['points_rostered'], 2)
        # Cost per point is only meaningful with money spent AND points on the
        # board; null means "not enough to judge", never zero.
        o['cost_per_point'] = (round(o['spent'] / o['points_started'], 2)
                               if o['spent'] > 0 and o['points_started'] > 0 else None)
        o['points_per_dollar'] = (round(o['points_started'] / o['spent'], 2)
                                  if o['spent'] > 0 else None)
        o['budget_left'] = (budget - o['spent']) if budget is not None else None
        # Waste as a share of contested spend: $250 thrown away on $400 of
        # contested bidding is a different story from $250 on $4,000.
        o['waste_rate'] = (round(o['waste'] / o['contested_spend'], 3)
                           if o['contested_spend'] > 0 else None)
        for k in ('biggest_bid', 'biggest_waste', 'worst_buy'):
            c = o[k]
            if c:
                o[k] = {f: c[f] for f in ('week', 'player', 'pos', 'bid', 'runner_up', 'waste',
                                          'contested', 'round', 'points_started', 'starts')}

    # --- league totals ---------------------------------------------------
    totals = {'spent': sum(c['bid'] for c in claims), 'claims': len(claims),
              'contested': sum(1 for c in claims if c['contested']),
              'waste': sum(c['waste'] for c in claims),
              'solo_spend': sum(c['solo'] for c in claims),
              'contested_spend': sum(c['bid'] for c in claims if c['contested']),
              'failed': len(lost_bids), 'budget': budget,
              'by_pos': {}, 'by_round': {}, 'by_week': {}}
    for c in claims:
        bucket(totals['by_pos'], c['pos'] or '?', spent=c['bid'], won=1, waste=c['waste'])
        bucket(totals['by_round'], c['round'] or 'undrafted', spent=c['bid'], won=1, waste=c['waste'])
        bucket(totals['by_week'], c['week'], spent=c['bid'], won=1, waste=c['waste'])
    for b in lost_bids:
        bucket(totals['by_pos'], b['pos'] or '?', lost=1, lost_bid=b['bid'])
        bucket(totals['by_round'], b['round'] or 'undrafted', lost=1, lost_bid=b['bid'])
        bucket(totals['by_week'], b['week'], lost=1, lost_bid=b['bid'])

    return {
        'name': cfg['name'], 'league_id': lid, 'budget': budget,
        'weeks': weeks_seen, 'through_week': through or last_week,
        'drafted_rounds': sorted(set(rounds.values())) if rounds else [],
        'owners': sorted(owners.values(), key=lambda o: (-o['spent'], o['handle'].lower())),
        'totals': totals,
        'claims': sorted(claims, key=lambda c: (-c['week'], -c['bid'])),
        'lost_bids': sorted(lost_bids, key=lambda b: (-b['week'], -b['bid'])),
        'awards': awards(owners.values(), claims),
    }


def awards(owners, claims):
    """Best and worst spenders. Each one names the owner AND the number behind
    it, so the page never has to re-derive a ranking and the two can't drift."""
    out = []
    spenders = [o for o in owners if o['spent'] >= MIN_SPEND_FOR_AWARD]
    valued = [o for o in spenders if o['cost_per_point'] is not None]

    def add(slug, label, dek, o, value):
        if o:
            out.append({'slug': slug, 'label': label, 'dek': dek,
                        'handle': o['handle'], 'name': o['name'], 'value': value})

    if valued:
        best = min(valued, key=lambda o: o['cost_per_point'])
        worst = max(valued, key=lambda o: o['cost_per_point'])
        add('best_value', 'Best value', 'Cheapest started point off the wire',
            best, f"${best['cost_per_point']}/pt on ${best['spent']}")
        add('worst_value', 'Worst value', 'Dearest started point off the wire',
            worst, f"${worst['cost_per_point']}/pt on ${worst['spent']}")
    dead = [o for o in spenders if o['cost_per_point'] is None]
    if dead:
        d = max(dead, key=lambda o: o['spent'])
        add('dead_money', 'Pure dead money', 'Spent it, never started it',
            d, f"${d['spent']} for {d['points_started']} pts")
    # The headline award, and the one the owner actually asked for: money handed
    # over above what the claim would have cost at the next-best bid.
    wasters = [o for o in owners if o['waste'] > 0]
    if wasters:
        w = max(wasters, key=lambda o: o['waste'])
        add('most_wasted', 'Most money wasted at auction',
            'Winning bid minus the next-best bid, added up',
            w, f"${w['waste']} thrown away across {w['contested_won']} contested claims")
        # Waste as a RATE, which is the fairer read: $250 thrown away is a
        # different story on $400 of contested bidding than on $4,000. Needs two
        # contested wins to mean anything, and the two ends are only reported
        # when they are actually two different people.
        rated = [o for o in owners if o['contested_won'] >= 2 and o['waste_rate'] is not None]
        if rated:
            sharp = min(rated, key=lambda o: o['waste_rate'])
            loose = max(rated, key=lambda o: o['waste_rate'])
            def rate(o):
                return (f"${o['waste']} wasted on ${o['contested_spend']} of contested bids "
                        f"({round(o['waste_rate'] * 100)}%)")
            add('sharpest', 'Sharpest bidder', 'Least waste per dollar of contested bidding',
                sharp, rate(sharp))
            if loose['handle'] != sharp['handle']:
                add('loosest', 'Loosest bidder', 'Most waste per dollar of contested bidding',
                    loose, rate(loose))
    bidders = [o for o in owners if o['bids'] >= 3]
    if bidders:
        lose = min(bidders, key=lambda o: (o['win_rate'], -o['bids']))
        add('outbid', 'Always the runner-up', 'Lowest claim win rate',
            lose, f"{lose['won']} of {lose['bids']} claims, ${lose['lost_bid_total']} bid and lost")
    streak = [o for o in owners if o['shutout_streak'] >= 2]
    if streak:
        s = max(streak, key=lambda o: o['shutout_streak'])
        add('cold_streak', 'Coldest hand', 'Consecutive weeks bidding and losing',
            s, f"{s['shutout_streak']} straight weeks with a bid and no claim")
    over = [c for c in claims if c['waste'] > 0]
    if over:
        c = max(over, key=lambda x: x['waste'])
        out.append({'slug': 'biggest_overpay', 'label': 'Biggest single overpay',
                    'dek': f"Week {c['week']}", 'handle': c['handle'], 'name': c['handle'],
                    'value': f"${c['bid']} on {c['player']} with the next bid at "
                             f"${c['runner_up']} -- ${c['waste']} wasted"})
    if claims:
        top = max(claims, key=lambda c: c['bid'])
        out.append({'slug': 'biggest_bid', 'label': 'Biggest bid of the season',
                    'dek': f"Week {top['week']}", 'handle': top['handle'], 'name': top['handle'],
                    'value': f"${top['bid']} on {top['player']} ({top['points_started']} pts since)"})
        bust = max(claims, key=lambda c: c['bid'] - c['points_started'])
        if bust['bid'] > 0:
            out.append({'slug': 'biggest_bust', 'label': 'Biggest bust', 'dek': f"Week {bust['week']}",
                        'handle': bust['handle'], 'name': bust['handle'],
                        'value': f"${bust['bid']} on {bust['player']} for {bust['points_started']} started pts"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--season', type=int)
    ap.add_argument('--through', type=int, help='last week to include (default: everything on file)')
    ap.add_argument('--only', help='comma list of league keys')
    ap.add_argument('--refresh', action='store_true', help='ignore every cached response')
    args = ap.parse_args()
    bw.REFRESH = args.refresh

    with open(os.path.join(ROOT, 'data', 'config.json'), encoding='utf-8') as f:
        config = json.load(f)
    season = args.season or config['site']['season']
    only = set(args.only.split(',')) if args.only else None

    out = {'season': season, 'generated': dt.datetime.now(ET).isoformat(timespec='seconds'),
           'leagues': {}}
    for key, cfg in config['leagues'].items():
        # Only the roster leagues have a waiver wire; a pick'em or survivor pool
        # has no players to claim.
        if cfg['kind'] not in ('chopped', 'h2h'):
            continue
        if only and key not in only:
            continue
        if str(season) not in (cfg.get('ids') or {}):
            print(f'  {key}: no league id for {season}, skipped')
            continue
        print(f'  {key} ...')
        try:
            out['leagues'][key] = build_league(key, cfg, season, args.through)
            L = out['leagues'][key]
            print(f"    ${L['totals']['spent']} across {L['totals']['claims']} claims, "
                  f"{L['totals']['failed']} failed, through week {L['through_week']}")
        except Exception as e:
            print(f'    FAILED: {e}', file=sys.stderr)
            out['leagues'][key] = {'error': str(e), 'name': cfg['name']}
    out['through_week'] = max([L.get('through_week') or 0 for L in out['leagues'].values()] or [0])

    d = os.path.join(ROOT, 'data', str(season))
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, 'waivers.json')
    with open(path + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    os.replace(path + '.tmp', path)
    print(f'wrote {os.path.relpath(path, ROOT)}')


if __name__ == '__main__':
    main()
