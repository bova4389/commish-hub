#!/usr/bin/env python3
"""
build_season.py -- fold every built week into one compact season rollup:
data/<season>/season.json.

    python scripts/build_season.py                # current season from config
    python scripts/build_season.py --season 2025

Why this file exists: the hub's cumulative tables (Infinity War money and picks
correct, King's Justice weekly-high money) need every week at once, and a
week-NN.json is ~250 KB. Eighteen of them is 4.5 MB on a phone, so the page
would be unusable by December. This rollup carries only the fields those tables
read -- a few KB for a whole season -- and is rebuilt from the week files, which
stay the source of truth.

It is pure aggregation: it calls no API and invents nothing. A week that has not
been built simply is not in it. build_week.py runs this at the end of every run,
so it is never stale relative to the weeks on disk.
"""

import argparse
import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ET = ZoneInfo('America/New_York')

LAST_WEEK = 18


def load_weeks(season):
    """(week number, parsed file) for every week-NN.json on disk, in order."""
    d = os.path.join(ROOT, 'data', str(season))
    out = []
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not (fn.startswith('week-') and fn.endswith('.json')):
            continue
        try:
            w = int(fn[5:-5])
        except ValueError:
            continue
        with open(os.path.join(d, fn), encoding='utf-8') as f:
            out.append((w, json.load(f)))
    return sorted(out, key=lambda x: x[0])


def roll_pickem(weeks, cfg_payouts):
    """Infinity War: per week, who took the pot and how many everyone got right.

    The weekly $20 is never split -- a tie goes to the Monday-night tiebreaker
    and a tie on that rolls the pot forward -- so `pot` on a week already
    includes anything carried in, and a rollover week pays nobody. Summing
    `pot` over the weeks a handle appears in `winners` is therefore the whole
    money calculation; do not also add `pot_carried` anywhere.
    """
    entries, rows = {}, {}
    for w, L in weeks:
        if not L:
            continue
        for e in L.get('entries') or []:
            entries.setdefault(e['handle'], e.get('name') or e['handle'])
        rows[str(w)] = {
            'final': not L.get('provisional'),
            'pot': L.get('pot') or 0,
            'pot_carried': L.get('pot_carried') or 0,
            'rollover': bool(L.get('rollover')),
            'best': L.get('best'),
            'winners': L.get('winners') or [],
            'correct': {e['handle']: (None if e.get('no_pick') else e.get('correct'))
                        for e in (L.get('entries') or [])},
            'pending': {e['handle']: e.get('pending') or 0 for e in (L.get('entries') or [])},
        }
    # Sleeper's own running total, kept only as a cross-check against the sum of
    # our ESPN-graded weekly `correct`. The page shows ours and flags a gap.
    last = weeks[-1][1] if weeks else None
    sleeper = {e['handle']: e['points'] for e in ((last or {}).get('leaderboard') or [])}
    return {'entries': [{'handle': h, 'name': n} for h, n in sorted(entries.items(), key=lambda kv: kv[0].lower())],
            'weeks': rows, 'payouts': cfg_payouts, 'sleeper_points': sleeper}


def roll_chopped(weeks, cfg_payouts):
    """King's Justice: who took the weekly high, and what they scored.

    Entries are a union across weeks on purpose -- a chopped roster stops
    appearing in later scoreboards, and dropping it would erase the $25 it may
    already have won.
    """
    entries, rows = {}, {}
    for w, L in weeks:
        if not L:
            continue
        for r in L.get('scoreboard') or []:
            entries.setdefault(r['handle'], r.get('name') or r['handle'])
        hi = L.get('high')
        rows[str(w)] = {
            'final': not L.get('provisional'),
            'high': {'handle': hi['handle'], 'points': hi['points']} if hi else None,
            'chopped': (L.get('chopped') or {}).get('handle') if L.get('chopped') else None,
            'prize': (L.get('payouts') or {}).get('weekly_high') or cfg_payouts.get('weekly_high') or 0,
        }
    return {'entries': [{'handle': h, 'name': n} for h, n in sorted(entries.items(), key=lambda kv: kv[0].lower())],
            'weeks': rows, 'payouts': cfg_payouts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--season', type=int)
    args = ap.parse_args()
    main_for(args.season)


def main_for(season=None):
    """The whole job, importable -- build_week.py calls this at the end of a run."""
    with open(os.path.join(ROOT, 'data', 'config.json'), encoding='utf-8') as f:
        config = json.load(f)
    season = season or config['site']['season']

    weeks = load_weeks(season)
    if not weeks:
        print(f'no week files for {season}; nothing to roll up')
        return

    out = {
        'season': season,
        'generated': dt.datetime.now(ET).isoformat(timespec='seconds'),
        'last_week': LAST_WEEK,
        'weeks': [w for w, _ in weeks],
        'final_weeks': [w for w, d in weeks if d.get('all_final')],
        'leagues': {},
    }
    for key, cfg in config['leagues'].items():
        per = [(w, (d.get('leagues') or {}).get(key)) for w, d in weeks]
        per = [(w, L) for w, L in per if L and 'error' not in L]
        if not per:
            continue
        payouts = cfg.get('payouts') or {}
        if cfg['kind'] == 'pickem':
            out['leagues'][key] = roll_pickem(per, payouts)
        elif cfg['kind'] == 'chopped':
            out['leagues'][key] = roll_chopped(per, payouts)
        else:
            continue
        out['leagues'][key]['name'] = cfg['name']
        out['leagues'][key]['kind'] = cfg['kind']

    path = os.path.join(ROOT, 'data', str(season), 'season.json')
    with open(path + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    os.replace(path + '.tmp', path)
    print(f"wrote {os.path.relpath(path, ROOT)} "
          f"({len(out['leagues'])} leagues, weeks {out['weeks'][0]}-{out['weeks'][-1]})")


if __name__ == '__main__':
    main()
