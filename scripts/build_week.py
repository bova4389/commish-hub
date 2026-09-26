#!/usr/bin/env python3
"""
build_week.py -- pull one NFL week for every league in data/config.json and
write the fact sheet the hub page renders: data/<season>/week-NN.json.

    python scripts/build_week.py --week 3
    python scripts/build_week.py --week 3 --season 2025 --only kings_justice
    python scripts/build_week.py --week 3 --refresh          # ignore the cache

What it does NOT do: write any prose. The recap paragraphs are hand-written
into recaps/<season>.json from the numbers in this file. Every number in a
recap must be traceable to this output.

Data sources (all keyless):
  Sleeper REST     league / users / rosters / matchups / transactions
  Sleeper GraphQL  get_pickem_picks_for_league   (undocumented; pick'em pools)
  Sleeper          /projections/nfl/<season>/<week>?season_type=regular&position[]=..
                   -> per-player projected stat line PLUS the team, game_id and
                      injury status for that exact week. This is how a player is
                      tied to a kickoff slot without guessing from a roster.
  Sleeper          /schedule/nfl/regular/<season>  game_id -> home/away (date only,
                   no kickoff time -- that comes from ESPN)
  ESPN scoreboard  kickoff times, final scores, game status
  Bova's Picks     ../bovas-picks/data/odds/history/*.json -- pre-kickoff win
                   probabilities, used to call an upset an upset. Optional; if the
                   folder is missing every game is simply unrated.

Quirks that each cost time, kept here so nobody rediscovers them:
  * Pick'em pools live under sport "pickem:nfl", not "nfl". Their leg id is
    "v1:regular:<week>" -- a bare week number returns {} with a 200.
  * include_tiebreaker:true changes the picks payload SHAPE (wraps in .picks).
    picks_of() reads either shape.
  * Sleeper picks carry outcome:"win" on EVERY pick, played or not -- it is the
    pick type, not a result. Picks are graded here against ESPN finals.
  * A chopped league's /rosters carries settings.eliminated = the week that
    roster was chopped (2025+ leagues). That is the alive signal. Chopped
    rosters still appear in every later week's matchups with 0.0 points.
  * ESPN spells Washington WSH; Sleeper spells it WAS. Sleeper's team codes
    are the canonical ones in this file.
  * Sleeper projections run optimistic by a different amount each week, so
    every proj-vs-actual figure is also reported net of the league median delta.
"""

import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import statistics
import sys
from zoneinfo import ZoneInfo

import requests

import build_season

REST = 'https://api.sleeper.app/v1'
BASE = 'https://api.sleeper.app'
GQL = 'https://api.sleeper.app/graphql'
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard'

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, '_cache')
# The Tuesday Action checks Bova's Picks out beside this repo's workspace and
# points ODDS_DIR at it, since a runner has no sibling folder.
ODDS_DIR = os.environ.get('ODDS_DIR') or os.path.join(os.path.dirname(ROOT), 'bovas-picks', 'data', 'odds', 'history')
ET = ZoneInfo('America/New_York')

# ESPN -> Sleeper team codes. Only the ones that differ.
ESPN_FIX = {'WSH': 'WAS'}
# Full names (as the odds feed spells them) -> Sleeper codes.
TEAM_NAMES = {
    'Arizona Cardinals': 'ARI', 'Atlanta Falcons': 'ATL', 'Baltimore Ravens': 'BAL',
    'Buffalo Bills': 'BUF', 'Carolina Panthers': 'CAR', 'Chicago Bears': 'CHI',
    'Cincinnati Bengals': 'CIN', 'Cleveland Browns': 'CLE', 'Dallas Cowboys': 'DAL',
    'Denver Broncos': 'DEN', 'Detroit Lions': 'DET', 'Green Bay Packers': 'GB',
    'Houston Texans': 'HOU', 'Indianapolis Colts': 'IND', 'Jacksonville Jaguars': 'JAX',
    'Kansas City Chiefs': 'KC', 'Las Vegas Raiders': 'LV', 'Los Angeles Chargers': 'LAC',
    'Los Angeles Rams': 'LAR', 'Miami Dolphins': 'MIA', 'Minnesota Vikings': 'MIN',
    'New England Patriots': 'NE', 'New Orleans Saints': 'NO', 'New York Giants': 'NYG',
    'New York Jets': 'NYJ', 'Philadelphia Eagles': 'PHI', 'Pittsburgh Steelers': 'PIT',
    'San Francisco 49ers': 'SF', 'Seattle Seahawks': 'SEA', 'Tampa Bay Buccaneers': 'TB',
    'Tennessee Titans': 'TEN', 'Washington Commanders': 'WAS',
}

SLOT_ELIGIBILITY = {
    'QB': ['QB'], 'RB': ['RB'], 'WR': ['WR'], 'TE': ['TE'], 'K': ['K'], 'DEF': ['DEF'],
    'FLEX': ['RB', 'WR', 'TE'], 'WRRB_FLEX': ['RB', 'WR'], 'REC_FLEX': ['WR', 'TE'],
    'SUPER_FLEX': ['QB', 'RB', 'WR', 'TE'],
}

REFRESH = False


# ---------------------------------------------------------------- transport
def _cache_path(key):
    os.makedirs(CACHE, exist_ok=True)
    return os.path.join(CACHE, hashlib.md5(key.encode()).hexdigest() + '.json')


def get(url, cacheable=True):
    """GET JSON. Cached on disk unless --refresh; live data for the current
    week should always be pulled with --refresh."""
    path = _cache_path('GET ' + url)
    if cacheable and not REFRESH and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    r = requests.get(url, timeout=60, headers={'Accept': 'application/json'})
    r.raise_for_status()
    data = r.json()
    if cacheable:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    return data


TOKEN_FILE = os.path.join(HERE, '.sleeper_token')


def sleeper_token():
    """Sleeper's pick'em GraphQL needs a logged-in user's token (since 2026-09).
    Read from SLEEPER_TOKEN or scripts/.sleeper_token (gitignored). Never print it."""
    token = os.environ.get('SLEEPER_TOKEN', '').strip()
    if not token and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, encoding='utf-8') as f:
            token = f.read().strip()
    if token.lower().startswith('bearer '):
        token = token[7:].strip()
    return token


def gql(query, variables):
    key = 'GQL ' + query + json.dumps(variables, sort_keys=True)
    path = _cache_path(key)
    if not REFRESH and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    headers = {}
    token = sleeper_token()
    if token:
        headers['Authorization'] = token
    r = requests.post(GQL, json={'query': query, 'variables': variables},
                      headers=headers, timeout=60)
    r.raise_for_status()
    body = r.json()
    if body.get('errors'):
        msg = body['errors'][0].get('message', '?')
        if msg == 'Unauthorized':
            msg += (' (no Sleeper token found)' if not token else
                    ' (Sleeper token rejected; it has probably expired, copy a fresh one)')
        raise RuntimeError('Sleeper GraphQL: ' + msg)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(body['data'], f)
    return body['data']


PICKS_QUERY = '''
  query Picks($league_id: Snowflake!, $leg_id: String!) {
    get_pickem_picks_for_league(
      league_id: $league_id, leg_id: $leg_id, include_tiebreaker: true
    )
  }'''


def picks_of(payload):
    if not isinstance(payload, dict):
        return {}
    inner = payload.get('picks')
    return inner if isinstance(inner, dict) else payload


# ---------------------------------------------------------------- NFL week
def espn_games(season, week):
    """Every game of the week with kickoff (UTC ISO), scores, status."""
    raw = get(f'{ESPN}?dates={season}&seasontype=2&week={week}')
    out = []
    for e in raw.get('events', []):
        comp = e['competitions'][0]
        home = away = None
        for c in comp['competitors']:
            side = {
                'team': ESPN_FIX.get(c['team']['abbreviation'], c['team']['abbreviation']),
                'score': int(c.get('score') or 0),
                'winner': bool(c.get('winner')),
            }
            if c.get('homeAway') == 'home':
                home = side
            else:
                away = side
        st = e['status']['type']
        kickoff = dt.datetime.strptime(e['date'], '%Y-%m-%dT%H:%MZ').replace(tzinfo=dt.timezone.utc)
        final = st.get('name') == 'STATUS_FINAL' or st.get('completed') is True
        winner = None
        if final:
            if home['score'] > away['score']:
                winner = home['team']
            elif away['score'] > home['score']:
                winner = away['team']
            else:
                winner = 'TIE'
        out.append({
            'home': home['team'], 'away': away['team'],
            'home_score': home['score'], 'away_score': away['score'],
            'kickoff': kickoff.isoformat(), 'final': final,
            'state': st.get('state'), 'winner': winner,
        })
    return out


def sleeper_schedule(season, week):
    raw = get(f'{BASE}/schedule/nfl/regular/{season}')
    return [g for g in raw if g.get('week') == week]


def slot_label(kick_utc):
    t = dt.datetime.fromisoformat(kick_utc).astimezone(ET)
    hour = t.strftime('%I:%M %p').lstrip('0')
    return f"{t.strftime('%a')} {hour}"


def build_slots(games):
    """Distinct kickoff times, in order. Each game and each team gets a slot
    index; the running-total timeline is built on these."""
    times = sorted({g['kickoff'] for g in games})
    idx = {t: i for i, t in enumerate(times)}
    slots = [{'i': i, 'kickoff': t, 'label': slot_label(t),
              'games': [f"{g['away']}@{g['home']}" for g in games if g['kickoff'] == t]}
             for i, t in enumerate(times)]
    team_slot = {}
    for g in games:
        g['slot'] = idx[g['kickoff']]
        team_slot[g['home']] = g['slot']
        team_slot[g['away']] = g['slot']
    return slots, team_slot


def load_odds():
    """game key 'AWAY@HOME|YYYY-MM-DD' -> last pre-kickoff snapshot."""
    if not os.path.isdir(ODDS_DIR):
        return {}
    out = {}
    for path in glob.glob(os.path.join(ODDS_DIR, '*.json')):
        try:
            with open(path, encoding='utf-8') as f:
                snaps = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(snaps, list) or not snaps:
            continue
        pre = [s for s in snaps if s.get('fetchedAt', '') < s.get('commenceTime', '')]
        s = (pre or snaps)[-1]
        home = TEAM_NAMES.get(s.get('home'))
        away = TEAM_NAMES.get(s.get('away'))
        if not (home and away):
            continue
        day = dt.datetime.fromisoformat(s['commenceTime'].replace('Z', '+00:00')).astimezone(ET).date().isoformat()
        out[f'{away}@{home}|{day}'] = {
            'home_prob': s.get('homeWinProb'), 'away_prob': s.get('awayWinProb'),
            'books': s.get('bookmakerCount'), 'as_of': s.get('fetchedAt'),
        }
    return out


def nfl_week(season, week):
    games = espn_games(season, week)
    sched = sleeper_schedule(season, week)
    slots, team_slot = build_slots(games)
    odds = load_odds()
    by_pair = {(g['away'], g['home']): g for g in games}
    for sg in sched:
        g = by_pair.get((sg['away'], sg['home']))
        if g:
            g['game_id'] = sg['game_id']
    for g in games:
        day = dt.datetime.fromisoformat(g['kickoff']).astimezone(ET).date().isoformat()
        o = odds.get(f"{g['away']}@{g['home']}|{day}")
        g['fav'] = g['fav_prob'] = None
        g['upset'] = None
        if o and o['home_prob'] is not None and o['away_prob'] is not None:
            hp, ap = o['home_prob'], o['away_prob']
            g['fav'], g['fav_prob'] = (g['home'], hp) if hp >= ap else (g['away'], ap)
            g['fav_prob'] = round(g['fav_prob'], 3)
            if g['winner'] and g['winner'] != 'TIE':
                g['upset'] = g['winner'] != g['fav']
        g['label'] = f"{g['away']} @ {g['home']}"
        g['slot_label'] = slots[g['slot']]['label']
    by_id = {g['game_id']: g for g in games if g.get('game_id')}
    return {
        'games': sorted(games, key=lambda g: (g['kickoff'], g['label'])),
        'slots': slots, 'team_slot': team_slot, 'by_id': by_id,
        'all_final': all(g['final'] for g in games) if games else False,
        'started': any(g['state'] != 'pre' for g in games) if games else False,
    }


# ---------------------------------------------------------------- players
def load_projections(season, week):
    """player_id -> {name, pos, team, game_id, opp, injury, stats}"""
    pos = '&'.join(f'position[]={p}' for p in ('QB', 'RB', 'WR', 'TE', 'K', 'DEF'))
    raw = get(f'{BASE}/projections/nfl/{season}/{week}?season_type=regular&{pos}')
    out = {}
    for row in raw:
        p = row.get('player') or {}
        pid = row.get('player_id')
        if not pid:
            continue
        name = ' '.join(x for x in [p.get('first_name'), p.get('last_name')] if x) or pid
        if p.get('position') == 'DEF':
            name = f"{row.get('team') or pid} D/ST"
        out[pid] = {
            'name': name, 'pos': p.get('position') or '', 'team': row.get('team'),
            'game_id': row.get('game_id'), 'opp': row.get('opponent'),
            'injury': p.get('injury_status'), 'stats': row.get('stats') or {},
        }
    return out


_PLAYERS = None


def players_nfl():
    """Fallback name/pos/team for anyone not in the week's projections.
    ~5 MB, fetched once and cached in scripts/_cache."""
    global _PLAYERS
    if _PLAYERS is not None:
        return _PLAYERS
    path = os.path.join(CACHE, 'players_nfl_slim.json')
    if os.path.exists(path) and not REFRESH:
        with open(path, encoding='utf-8') as f:
            _PLAYERS = json.load(f)
            return _PLAYERS
    print('  fetching /players/nfl (5 MB, once) ...')
    raw = get(f'{REST}/players/nfl', cacheable=False)
    _PLAYERS = {}
    for pid, p in raw.items():
        name = p.get('full_name') or ' '.join(x for x in [p.get('first_name'), p.get('last_name')] if x)
        if p.get('position') == 'DEF':
            name = f'{pid} D/ST'
        _PLAYERS[pid] = {'name': name or pid, 'pos': p.get('position') or '', 'team': p.get('team')}
    os.makedirs(CACHE, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(_PLAYERS, f, separators=(',', ':'))
    return _PLAYERS


def player_info(pid, proj):
    p = proj.get(pid)
    if p:
        return p
    q = players_nfl().get(pid) or {'name': pid, 'pos': '', 'team': None}
    return {'name': q['name'], 'pos': q['pos'], 'team': q['team'],
            'game_id': None, 'opp': None, 'injury': None, 'stats': {}}


def make_calc_pts(scoring):
    """Score a projected stat line through the league's own scoring settings.
    Every numeric scoring key is applied to the matching stat; that covers
    yardage, TDs, receptions, distance buckets, bonuses, kicking and defense
    without a hand-kept list."""
    weights = {k: v for k, v in scoring.items() if isinstance(v, (int, float)) and v}
    te_bonus = weights.pop('bonus_rec_te', 0)
    # pts_* are Sleeper's own generic totals, never league scoring.
    for k in list(weights):
        if k.startswith('pts_'):
            weights.pop(k)

    def calc(stats, pos):
        if not stats:
            return 0.0
        pts = 0.0
        for k, w in weights.items():
            v = stats.get(k)
            if isinstance(v, (int, float)):
                pts += v * w
        if pos == 'TE' and te_bonus:
            v = stats.get('rec')
            if isinstance(v, (int, float)):
                pts += v * te_bonus
        return round(pts, 2)
    return calc


# ---------------------------------------------------------------- leagues
def league_bundle(lid, names):
    league = get(f'{REST}/league/{lid}')
    users = get(f'{REST}/league/{lid}/users')
    rosters = get(f'{REST}/league/{lid}/rosters')
    by_user = {u['user_id']: u for u in users}
    teams = {}
    for r in rosters:
        u = by_user.get(r.get('owner_id')) or {}
        handle = u.get('display_name') or f"roster {r['roster_id']}"
        team_name = (u.get('metadata') or {}).get('team_name') or handle
        teams[r['roster_id']] = {
            'roster_id': r['roster_id'], 'handle': handle,
            'name': names.get(handle, handle), 'team_name': team_name,
            'user_id': r.get('owner_id'), 'settings': r.get('settings') or {},
            'metadata': r.get('metadata') or {},
        }
    return league, teams


def starter_rows(entry, proj, calc, team_slot, slots_n):
    """One row per starter: points, projection, kickoff slot, injury flag."""
    starters = [str(x) for x in (entry.get('starters') or []) if x and x != '0']
    spts = entry.get('starters_points') or []
    ppts = entry.get('players_points') or {}
    rows = []
    for i, pid in enumerate(starters):
        info = player_info(pid, proj)
        pts = ppts.get(pid)
        if pts is None and i < len(spts):
            pts = spts[i]
        team = info.get('team')
        slot = team_slot.get(team) if team else None
        rows.append({
            'pid': pid, 'name': info['name'], 'pos': info['pos'], 'team': team,
            'pts': round(pts or 0.0, 2),
            'proj': calc(info.get('stats'), info['pos']) if calc else None,
            'slot': slot, 'injury': info.get('injury'),
        })
    return rows


def bench_rows(entry, proj, calc):
    starters = set(str(x) for x in (entry.get('starters') or []))
    ppts = entry.get('players_points') or {}
    rows = []
    for pid in (entry.get('players') or []):
        pid = str(pid)
        if pid in starters:
            continue
        info = player_info(pid, proj)
        rows.append({'pid': pid, 'name': info['name'], 'pos': info['pos'], 'team': info.get('team'),
                     'pts': round(ppts.get(pid, 0.0) or 0.0, 2),
                     'proj': calc(info.get('stats'), info['pos']) if calc else None,
                     'injury': info.get('injury')})
    return rows


def best_swap(starters, bench, slot_list):
    best = None
    for idx, s in enumerate(starters):
        if idx >= len(slot_list):
            break
        elig = SLOT_ELIGIBILITY.get(slot_list[idx])
        if not elig:
            continue
        for b in bench:
            if b['pos'] not in elig:
                continue
            gain = round(b['pts'] - s['pts'], 2)
            if gain > 0 and (best is None or gain > best['gain']):
                best = {'gain': gain, 'in': b['name'], 'in_pts': b['pts'],
                        'out': s['name'], 'out_pts': s['pts'], 'slot': slot_list[idx]}
    return best


def optimal_total(starters, bench, slot_list):
    pool = starters + bench
    order = sorted([s for s in slot_list if s in SLOT_ELIGIBILITY], key=lambda s: len(SLOT_ELIGIBILITY[s]))
    used, total = set(), 0.0
    for sl in order:
        best = None
        for p in pool:
            if p['pid'] in used or p['pos'] not in SLOT_ELIGIBILITY[sl]:
                continue
            if best is None or p['pts'] > best['pts']:
                best = p
        if best:
            used.add(best['pid'])
            total += best['pts']
    return round(total, 2)


def week_transactions(lid, week, teams, proj):
    """Waiver / FAAB / trade activity for the week, names resolved."""
    raw = get(f'{REST}/league/{lid}/transactions/{week}')
    claims = {}
    trades, adds = [], []
    for t in raw or []:
        typ = t.get('type')
        rids = t.get('roster_ids') or []
        who = teams.get(rids[0], {}).get('handle', '?') if rids else '?'
        if typ == 'waiver':
            for pid in (t.get('adds') or {}):
                c = claims.setdefault(pid, {'player': player_info(pid, proj)['name'],
                                            'pos': player_info(pid, proj)['pos'], 'bids': []})
                c['bids'].append({'rid': rids[0] if rids else None, 'handle': who,
                                  'bid': (t.get('settings') or {}).get('waiver_bid', 0),
                                  'won': t.get('status') == 'complete'})
        elif typ == 'free_agent' and t.get('status') == 'complete':
            for pid in (t.get('adds') or {}):
                adds.append({'handle': who, 'player': player_info(pid, proj)['name'],
                             'drops': [player_info(d, proj)['name'] for d in (t.get('drops') or {})]})
        elif typ == 'trade' and t.get('status') == 'complete':
            sides = {}
            for pid, rid in (t.get('adds') or {}).items():
                sides.setdefault(teams.get(rid, {}).get('handle', str(rid)), []).append(player_info(pid, proj)['name'])
            trades.append({'sides': sides})
    out, lost = [], []
    for pid, c in claims.items():
        # ONE BID PER ROSTER. Sleeper returns more than one transaction for the
        # same roster and player -- a completed claim plus a superseded record
        # of the same bid -- so treating every transaction as its own bidder
        # counts the winner as its own runner-up and reports $0 wasted on a
        # claim that walked the field. Measured 2026-09-16: avobttam's $169 Joe
        # Burrow claim came back with a $169 "losing" bid from avobttam, hiding
        # a $158 overpay over the real runner-up at $11.
        per = {}
        for b in c['bids']:
            cur = per.get(b['rid'])
            if cur is None:
                per[b['rid']] = dict(b)
            elif b['won']:
                # The record that actually processed is the price paid, even if
                # a superseded record for the same roster bid more.
                per[b['rid']] = dict(b)
            elif not cur['won']:
                cur['bid'] = max(cur['bid'], b['bid'])
        bids = sorted(per.values(), key=lambda b: -b['bid'])
        win = next((b for b in bids if b['won']), None)
        others = [b for b in bids if not win or b['rid'] != win['rid']]
        # Every losing bid is kept, bidder and all. Sleeper returns failed claims
        # alongside the winning one, and they are the only record of who keeps
        # getting outbid -- scripts/build_waivers.py is built on this.
        for b in others:
            lost.append({'player_id': pid, 'player': c['player'], 'pos': c['pos'], 'handle': b['handle'],
                         'bid': b['bid'], 'won_by': win['handle'] if win else None,
                         'won_at': win['bid'] if win else None})
        if not win:
            continue
        out.append({'player_id': pid, 'player': c['player'], 'pos': c['pos'], 'handle': win['handle'],
                    'bid': win['bid'], 'bidders': len(bids),
                    'runner_up': max(b['bid'] for b in others) if others else None,
                    'losers': [{'handle': b['handle'], 'bid': b['bid']} for b in others]})
    out.sort(key=lambda x: -x['bid'])
    lost.sort(key=lambda x: -x['bid'])
    return {'waivers': out, 'lost_bids': lost, 'faab_spent': sum(x['bid'] for x in out),
            'free_agents': adds, 'trades': trades}


# ---------------------------------------------------------------- Kings Justice
def build_chopped(cfg, season, week, nfl, proj):
    lid = cfg['ids'][str(season)]
    league, teams = league_bundle(lid, cfg.get('names') or {})
    calc = make_calc_pts(league.get('scoring_settings') or {})
    slot_list = [s for s in (league.get('roster_positions') or []) if s != 'BN']
    matchups = get(f'{REST}/league/{lid}/matchups/{week}', cacheable=nfl['all_final'])
    txns = get(f'{REST}/league/{lid}/transactions/{week}', cacheable=nfl['all_final'])
    chopped_now = set()
    for t in txns or []:
        if t.get('type') == 'chopped':
            chopped_now.update(t.get('roster_ids') or [])

    def alive_before(t):
        e = t['settings'].get('eliminated') or 0
        return e == 0 or e >= week

    n_slots = len(nfl['slots'])
    rows = []
    for e in matchups:
        t = teams.get(e['roster_id'])
        if not t or not alive_before(t):
            continue
        starters = starter_rows(e, proj, calc, nfl['team_slot'], n_slots)
        pts = round(e.get('points') or 0.0, 2)
        running = []
        for i in range(n_slots):
            running.append(round(sum(s['pts'] for s in starters if s['slot'] is not None and s['slot'] <= i), 2))
        left = [sum(1 for s in starters if s['slot'] is not None and s['slot'] > i) for i in range(n_slots)]
        rows.append({
            'roster_id': t['roster_id'], 'handle': t['handle'], 'name': t['name'], 'team_name': t['team_name'],
            'points': pts, 'proj': round(sum(s['proj'] or 0 for s in starters), 2),
            'running': running, 'left_after': left,
            'starters': starters,
            'last_slot_players': [s for s in starters if s['slot'] is not None and s['slot'] == n_slots - 1],
            'no_game': [s['name'] for s in starters if s['slot'] is None],
            'chopped': t['roster_id'] in chopped_now or (t['settings'].get('eliminated') == week),
        })
    rows.sort(key=lambda r: -r['points'])
    for i, r in enumerate(rows):
        r['rank'] = i + 1
    provisional = not nfl['all_final']
    low = rows[-1] if rows else None
    high = rows[0] if rows else None
    survivor = rows[-2] if len(rows) > 1 else None
    # Who sat in the chop seat after each kickoff slot, and by how much.
    seat = []
    for i in range(n_slots):
        order = sorted(rows, key=lambda r: r['running'][i])
        if len(order) >= 2:
            seat.append({'slot': i, 'label': nfl['slots'][i]['label'], 'handle': order[0]['handle'],
                         'points': order[0]['running'][i], 'left': order[0]['left_after'][i],
                         'next_handle': order[1]['handle'], 'margin': round(order[1]['running'][i] - order[0]['running'][i], 2)})
    all_starters = [(r['handle'], s) for r in rows for s in r['starters']]
    top = sorted(all_starters, key=lambda x: -x[1]['pts'])[:8]
    duds = sorted([x for x in all_starters if x[1]['slot'] is not None], key=lambda x: x[1]['pts'])[:8]
    return {
        'league_id': lid, 'league_name': league.get('name'), 'provisional': provisional,
        'alive_before': len(rows), 'alive_after': max(0, len(rows) - 1) if not provisional else len(rows),
        'payouts': cfg.get('payouts', {}),
        'chopped': None if not low else {'handle': low['handle'], 'team_name': low['team_name'], 'points': low['points'],
                                         'confirmed': bool(low['chopped'])},
        'high': None if not high else {'handle': high['handle'], 'team_name': high['team_name'], 'points': high['points']},
        'survivor': None if not survivor else {'handle': survivor['handle'], 'points': survivor['points'],
                                               'margin': round(survivor['points'] - low['points'], 2)},
        'median': round(statistics.median([r['points'] for r in rows]), 2) if rows else 0,
        'spread': round(high['points'] - low['points'], 2) if high and low else 0,
        'chop_seat': seat,
        'scoreboard': [{k: r[k] for k in ('rank', 'roster_id', 'handle', 'name', 'team_name', 'points', 'proj',
                                          'running', 'left_after', 'last_slot_players', 'no_game', 'chopped')} for r in rows],
        'top_starters': [{'handle': h, **{k: s[k] for k in ('name', 'pos', 'team', 'pts', 'slot')}} for h, s in top],
        'dud_starters': [{'handle': h, **{k: s[k] for k in ('name', 'pos', 'team', 'pts', 'slot')}} for h, s in duds],
        'transactions': week_transactions(lid, week, teams, proj),
    }


# ---------------------------------------------------------------- 2 Mitchs (head to head)
def build_h2h(cfg, season, week, nfl, proj):
    lid = cfg['ids'][str(season)]
    league, teams = league_bundle(lid, cfg.get('names') or {})
    calc = make_calc_pts(league.get('scoring_settings') or {})
    slot_list = [s for s in (league.get('roster_positions') or []) if s != 'BN']
    matchups = get(f'{REST}/league/{lid}/matchups/{week}', cacheable=nfl['all_final'])
    n_slots = len(nfl['slots'])
    sides = {}
    for e in matchups:
        t = teams.get(e['roster_id'])
        if not t:
            continue
        starters = starter_rows(e, proj, calc, nfl['team_slot'], n_slots)
        bench = bench_rows(e, proj, calc)
        pts = round(e.get('points') or 0.0, 2)
        proj_total = round(sum(s['proj'] or 0 for s in starters), 2)
        optimal = optimal_total(starters, bench, slot_list)
        sides[e['roster_id']] = {
            'roster_id': t['roster_id'], 'handle': t['handle'], 'name': t['name'], 'team_name': t['team_name'],
            'matchup_id': e.get('matchup_id'), 'points': pts, 'proj': proj_total,
            'delta': round(pts - proj_total, 2),
            'starters': starters, 'bench': sorted(bench, key=lambda b: -b['pts']),
            'bench_points': round(sum(b['pts'] for b in bench), 2),
            'left_on_bench': round(optimal - pts, 2),
            'best_swap': best_swap(starters, bench, slot_list),
            'zeros': [s['name'] for s in starters if s['pts'] == 0 and s['slot'] is not None],
            'injured_starters': [s['name'] + f" ({s['injury']})" for s in starters if s['injury'] in ('Out', 'IR', 'Doubtful', 'Sus', 'PUP')],
            'record': f"{t['settings'].get('wins', 0)}-{t['settings'].get('losses', 0)}",
        }
    deltas = [s['delta'] for s in sides.values()]
    bias = round(statistics.median(deltas), 2) if deltas else 0.0
    for s in sides.values():
        s['delta_net'] = round(s['delta'] - bias, 2)
    pairs = {}
    for s in sides.values():
        pairs.setdefault(s['matchup_id'], []).append(s)
    games = []
    for mid, pair in sorted(pairs.items(), key=lambda kv: kv[0] or 0):
        if len(pair) != 2:
            continue
        a, b = sorted(pair, key=lambda s: -s['points'])
        margin = round(a['points'] - b['points'], 2)
        tags = []
        if margin < 5:
            tags.append('NAILBITER')
        if margin > 40:
            tags.append('BLOWOUT')
        if b['proj'] > a['proj'] and nfl['all_final']:
            tags.append('UPSET')
        if b['best_swap'] and b['best_swap']['gain'] > margin:
            tags.append('BENCHED THE WIN')
        games.append({'matchup_id': mid, 'winner': a, 'loser': b, 'margin': margin, 'tags': tags})
    all_starters = [(s['handle'], st) for s in sides.values() for st in s['starters']]
    over = sorted([x for x in all_starters if x[1]['proj'] is not None], key=lambda x: -(x[1]['pts'] - x[1]['proj']))[:8]
    under = sorted([x for x in all_starters if x[1]['proj'] is not None and x[1]['slot'] is not None],
                   key=lambda x: (x[1]['pts'] - x[1]['proj']))[:8]
    standings = sorted(sides.values(), key=lambda s: (-teams[s['roster_id']]['settings'].get('wins', 0),
                                                       -teams[s['roster_id']]['settings'].get('fpts', 0)))
    return {
        'league_id': lid, 'league_name': league.get('name'), 'provisional': not nfl['all_final'],
        'proj_bias': bias, 'roster_positions': slot_list,
        'matchups': games,
        'high': max(sides.values(), key=lambda s: s['points'])['handle'] if sides else None,
        'low': min(sides.values(), key=lambda s: s['points'])['handle'] if sides else None,
        'bench_kings': sorted([{'handle': s['handle'], 'name': s['name'], 'left': s['left_on_bench'],
                                'swap': s['best_swap']} for s in sides.values()], key=lambda x: -x['left'])[:5],
        'over': [{'handle': h, 'name': s['name'], 'pos': s['pos'], 'pts': s['pts'], 'proj': s['proj']} for h, s in over],
        'under': [{'handle': h, 'name': s['name'], 'pos': s['pos'], 'pts': s['pts'], 'proj': s['proj']} for h, s in under],
        'standings': [{'handle': s['handle'], 'name': s['name'], 'record': s['record'],
                       'pf': round(teams[s['roster_id']]['settings'].get('fpts', 0)
                                   + teams[s['roster_id']]['settings'].get('fpts_decimal', 0) / 100, 2)} for s in standings],
        'transactions': week_transactions(lid, week, teams, proj),
    }


# ---------------------------------------------------------------- pick'em + survivor
def build_pickem(cfg, season, week, nfl):
    lid = cfg['ids'][str(season)]
    league, teams = league_bundle(lid, cfg.get('names') or {})
    settings = league.get('settings') or {}
    survivor = settings.get('pickem_type') == 1 or cfg.get('kind') == 'survivor'
    payload = gql(PICKS_QUERY, {'league_id': str(lid), 'leg_id': f'v1:regular:{week}'})
    picks_all = payload.get('get_pickem_picks_for_league') or {}
    leg = f'v1:regular:{week}'
    by_id = nfl['by_id']
    field = {}
    entries = []
    for rid, t in teams.items():
        raw = picks_of(picks_all.get(str(rid)))
        tb_raw = (picks_all.get(str(rid)) or {}).get('tiebreaker') if isinstance(picks_all.get(str(rid)), dict) else None
        tiebreaker = None
        if isinstance(tb_raw, dict) and tb_raw.get('value') is not None:
            tg = by_id.get(str(tb_raw.get('game_id')), {})
            # Same kickoff gate as the picks: the guess is public only once its game starts.
            pre = tg.get('state') == 'pre'
            tiebreaker = {'type': tb_raw.get('type'), 'game_id': str(tb_raw.get('game_id')),
                          'game': tg.get('label'), 'guess': None if pre else tb_raw.get('value'), 'hidden': pre}
        picks = []
        for gid, p in raw.items():
            if not isinstance(p, dict):
                continue
            g = by_id.get(str(gid), {})
            team = p.get('team')
            if g.get('state') == 'pre':
                # THE KICKOFF GATE. Sleeper's app hides a pick until its game
                # kicks off; Sleeper's API hands it over days early. This file
                # is committed to a public repo, so a pre-kickoff pick is
                # recorded only as "made", never which team.
                picks.append({'game_id': str(gid), 'team': None, 'opp': None, 'game': g.get('label'),
                              'outcome': None, 'prob': None, 'score': None, 'hidden': True,
                              'slot_label': g.get('slot_label')})
                continue
            opp = g.get('home') if g.get('away') == team else g.get('away')
            prob = None
            if g.get('fav_prob') is not None:
                prob = g['fav_prob'] if g['fav'] == team else round(1 - g['fav_prob'], 3)
            # Sleeper's own `outcome` field is ALWAYS "win" -- it is the kind of
            # pick, not a result -- so every pick is graded here from the final.
            if not g.get('final'):
                outcome = None
            elif g.get('winner') == 'TIE':
                outcome = 'push'
            else:
                outcome = 'win' if g.get('winner') == team else 'loss'
            picks.append({'game_id': str(gid), 'team': team, 'opp': opp, 'game': g.get('label'),
                          'outcome': outcome, 'prob': prob, 'hidden': False,
                          'score': f"{g.get('away')} {g.get('away_score')}-{g.get('home_score')} {g.get('home')}" if g.get('final') else None,
                          'slot_label': g.get('slot_label')})
            field.setdefault(str(gid), {}).setdefault(team, 0)
            field[str(gid)][team] += 1
        picks.sort(key=lambda p: (by_id.get(p['game_id'], {}).get('kickoff', ''), p['team'] or ''))
        md = t['metadata'] or {}
        lost = md.get('lost_leg_ids') or []
        lost_weeks = sorted(int(str(x).split(':')[-1]) for x in lost if str(x).split(':')[-1].isdigit())
        pbl = md.get('points_by_leg') or {}
        season_pts = sum(v for k, v in pbl.items() if int(k.split(':')[-1]) <= week)
        entries.append({
            'roster_id': rid, 'handle': t['handle'], 'name': t['name'],
            'picks': picks, 'no_pick': len(picks) == 0,
            'correct': sum(1 for p in picks if p['outcome'] == 'win'),
            'wrong': sum(1 for p in picks if p['outcome'] == 'loss'),
            'pending': sum(1 for p in picks if p['outcome'] not in ('win', 'loss')),
            'week_points': pbl.get(leg),
            'season_points': season_pts,
            'lost_this_week': week in lost_weeks,
            'strikes_before': sum(1 for w in lost_weeks if w < week),
            'strikes_after': sum(1 for w in lost_weeks if w <= week),
            'eliminated_now': str(md.get('is_eliminated')).lower() == 'true',
            'tiebreaker': tiebreaker,
        })
    for e in entries:
        # A pick nobody else made that landed. The weekly money is won by
        # being different AND right, so this is the stat that matters.
        e['hidden'] = sum(1 for p in e['picks'] if p.get('hidden'))
        e['lonely_wins'] = [p['team'] for p in e['picks'] if p['outcome'] == 'win' and field.get(p['game_id'], {}).get(p['team']) == 1]
        e['upset_wins'] = [p['team'] for p in e['picks'] if p['outcome'] == 'win' and p['prob'] is not None and p['prob'] < 0.5]
        e['chalk_losses'] = [p['team'] for p in e['picks'] if p['outcome'] == 'loss' and p['prob'] is not None and p['prob'] >= 0.65]
    out = {
        'league_id': lid, 'league_name': league.get('name'), 'provisional': not nfl['all_final'],
        'kind': 'survivor' if survivor else 'pickem', 'entries_total': len(entries),
        'weekly_pick_limit': settings.get('weekly_pick_limit'), 'revives_allowed': settings.get('num_revives_allowed'),
        'payouts': cfg.get('payouts', {}),
        'field': [{'game_id': gid, 'game': by_id.get(gid, {}).get('label'), 'winner': by_id.get(gid, {}).get('winner'),
                   'upset': by_id.get(gid, {}).get('upset'), 'fav': by_id.get(gid, {}).get('fav'),
                   'fav_prob': by_id.get(gid, {}).get('fav_prob'), 'picks': counts}
                  for gid, counts in sorted(field.items(), key=lambda kv: by_id.get(kv[0], {}).get('kickoff', ''))],
    }
    if survivor:
        alive_before = [e for e in entries if not e['eliminated_now'] or e['strikes_before'] <= (settings.get('num_revives_allowed') or 0)]
        # Sleeper keeps writing a loss for a dead entry every week it makes no
        # pick, so "lost this week" alone would resurrect every corpse. A death
        # is a real pick that lost; a no-pick only matters for a live entry.
        died = [e for e in entries if e['picks'] and e['picks'][0]['outcome'] == 'loss']
        no_pick = [e for e in entries if e['no_pick'] and not e['eliminated_now']]
        consensus = {}
        for e in entries:
            for p in e['picks']:
                if p['team']:
                    consensus[p['team']] = consensus.get(p['team'], 0) + 1
        out.update({
            'entries': sorted([e for e in entries if e['picks'] or not e['eliminated_now']],
                              key=lambda e: (e['eliminated_now'], e['strikes_after'], e['handle'].lower())),
            'died': [{'handle': e['handle'], 'pick': e['picks'][0] if e['picks'] else None,
                      'strikes_after': e['strikes_after'], 'eliminated_now': e['eliminated_now']} for e in died],
            'no_pick': [e['handle'] for e in no_pick],
            'alive_after': sum(1 for e in entries if not e['eliminated_now']),
            'consensus': sorted([{'team': t, 'count': c} for t, c in consensus.items()], key=lambda x: -x['count']),
            'killer_games': [g for g in out['field'] if any(t != g['winner'] and g['winner'] for t in g['picks'])],
        })
    else:
        scored = sorted(entries, key=lambda e: (-e['correct'], e['handle'].lower()))
        best = scored[0]['correct'] if scored else 0
        final = nfl['all_final']
        # THE WEEKLY MONEY IS NEVER SPLIT. A tie on correct picks goes to the
        # tiebreaker guess closest to the Monday night game's total points; if
        # the closest guesses are equally close, nobody wins and the pot rolls
        # into next week.
        tied = [e for e in scored if e['correct'] == best and best > 0] if final else []
        pot_carried = 0
        prev_path = os.path.join(ROOT, 'data', str(season), f'week-{week - 1:02d}.json')
        if week > 1 and os.path.exists(prev_path):
            with open(prev_path, encoding='utf-8') as f:
                prev = (json.load(f).get('leagues') or {}).get(cfg['key']) or {}
            if prev.get('rollover'):
                pot_carried = prev.get('pot') or 0
        pot = (cfg.get('payouts') or {}).get('weekly', 0) + pot_carried
        winners, rollover, tiebreak = [], False, None
        if len(tied) == 1:
            winners = tied
        elif len(tied) > 1:
            tb_game = next((e['tiebreaker']['game_id'] for e in tied if e.get('tiebreaker')), None)
            g = by_id.get(tb_game or '', {})
            actual = (g.get('away_score') or 0) + (g.get('home_score') or 0) if g.get('final') else None
            guesses = []
            for e in tied:
                guess = (e.get('tiebreaker') or {}).get('guess')
                off = abs(guess - actual) if (guess is not None and actual is not None) else None
                guesses.append({'handle': e['handle'], 'guess': guess, 'off': off})
            guesses.sort(key=lambda x: (x['off'] is None, x['off'] if x['off'] is not None else 0, x['handle'].lower()))
            closest = [x for x in guesses if x['off'] is not None and x['off'] == guesses[0]['off']]
            if len(closest) == 1:
                winners = [e for e in tied if e['handle'] == closest[0]['handle']]
            elif actual is not None:
                rollover = True
            tiebreak = {'game': g.get('label'), 'actual': actual, 'guesses': guesses}
        board = sorted(entries, key=lambda e: (-e['season_points'], e['handle'].lower()))
        out.update({
            'entries': scored,
            'winners': [e['handle'] for e in winners], 'best': best,
            'tied': [e['handle'] for e in tied], 'tiebreak': tiebreak,
            'pot': pot, 'pot_carried': pot_carried, 'rollover': rollover,
            'worst': [e['handle'] for e in scored if not e['no_pick'] and e['correct'] == min(x['correct'] for x in scored if not x['no_pick'])] if (final and any(not e['no_pick'] for e in scored)) else [],
            'no_pick': [e['handle'] for e in scored if e['no_pick']],
            'leaderboard': [{'handle': e['handle'], 'points': e['season_points']} for e in board],
            'upsets': [g for g in out['field'] if g['upset']],
        })
    return out


# ---------------------------------------------------------------- main
def latest_week(season):
    """The week the Tuesday Action should build: Sleeper's current week, or the
    one before it if the current week has not kicked off yet. Sleeper rolls its
    week over midweek, and this way the answer is the same either side of that."""
    state = requests.get(f'{REST}/state/nfl', timeout=30).json()
    week = int(state['week'])
    if str(state.get('season')) != str(season) or state.get('season_type') != 'regular':
        sys.exit(f"Sleeper says {state.get('season')} {state.get('season_type')}; "
                 f'not building a {season} regular-season week')
    nfl = nfl_week(season, week)
    if not nfl['started'] and week > 1:
        week -= 1
        nfl = nfl_week(season, week)
    return week, nfl


def main():
    global REFRESH
    ap = argparse.ArgumentParser()
    ap.add_argument('--week', required=True,
                    help="a week number, or 'latest' for the last week that has kicked off")
    ap.add_argument('--season', type=int)
    ap.add_argument('--only', help='comma list of league keys')
    ap.add_argument('--refresh', action='store_true', help='ignore every cached response')
    ap.add_argument('--strict', action='store_true',
                    help='write nothing and exit 1 if any league fails (the Action uses this)')
    ap.add_argument('--override', action='append', default=[],
                    help='key=league_id, to point a league at a different Sleeper id (testing)')
    args = ap.parse_args()
    REFRESH = args.refresh

    with open(os.path.join(ROOT, 'data', 'config.json'), encoding='utf-8') as f:
        config = json.load(f)
    season = args.season or config['site']['season']
    if args.week == 'latest':
        week, nfl = latest_week(season)
    else:
        week, nfl = int(args.week), None
    only = set(args.only.split(',')) if args.only else None
    for ov in args.override:
        k, v = ov.split('=', 1)
        config['leagues'][k].setdefault('ids', {})[str(season)] = v

    print(f'NFL {season} week {week}')
    nfl = nfl or nfl_week(season, week)
    print(f"  {len(nfl['games'])} games, {len(nfl['slots'])} kickoff slots, "
          f"{'all final' if nfl['all_final'] else 'NOT final'}")

    proj = None
    out = {
        'season': season, 'week': week,
        'generated': dt.datetime.now(ET).isoformat(timespec='seconds'),
        'all_final': nfl['all_final'],
        'nfl': {'games': [{k: g[k] for k in ('game_id', 'label', 'away', 'home', 'away_score', 'home_score',
                                              'winner', 'final', 'kickoff', 'slot', 'slot_label', 'fav', 'fav_prob', 'upset')
                           if k in g} for g in nfl['games']],
                'slots': nfl['slots']},
        'leagues': {},
    }
    season_dir = os.path.join(ROOT, 'data', str(season))
    path = os.path.join(season_dir, f'week-{week:02d}.json')
    # --only rebuilds some leagues and keeps the rest of an existing week file,
    # so adding a league to a finished week does not wipe the other four.
    if only and os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            out['leagues'] = {k: v for k, v in json.load(f).get('leagues', {}).items() if k not in only}
    builders = {'chopped': build_chopped, 'h2h': build_h2h, 'pickem': build_pickem, 'survivor': build_pickem}
    for key, cfg in config['leagues'].items():
        if only and key not in only:
            continue
        if str(season) not in (cfg.get('ids') or {}):
            print(f'  {key}: no league id for {season}, skipped')
            continue
        kind = cfg['kind']
        cfg = dict(cfg, key=key)
        print(f'  {key} ({kind}) ...')
        try:
            if kind in ('chopped', 'h2h'):
                if proj is None:
                    proj = load_projections(season, week)
                out['leagues'][key] = builders[kind](cfg, season, week, nfl, proj)
            else:
                out['leagues'][key] = builders[kind](cfg, season, week, nfl)
        except Exception as e:  # keep the other leagues if one source is down
            print(f'    FAILED: {e}', file=sys.stderr)
            out['leagues'][key] = {'error': str(e)}

    failed = sorted(k for k, v in out['leagues'].items() if 'error' in v)
    if failed and args.strict:
        # A rerun must never overwrite a good week with an error, so write nothing.
        sys.exit(f"failed: {', '.join(failed)}; nothing written")
    os.makedirs(season_dir, exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1)
    os.replace(tmp, path)
    # The page can't list a directory on GitHub Pages, so keep an index.
    idx_path = os.path.join(season_dir, 'index.json')
    idx = {'season': season, 'weeks': {}}
    if os.path.exists(idx_path):
        with open(idx_path, encoding='utf-8') as f:
            idx = json.load(f)
    idx['weeks'][str(week)] = {'generated': out['generated'], 'final': nfl['all_final'],
                               'leagues': sorted(k for k, v in out['leagues'].items() if 'error' not in v)}
    idx['weeks'] = dict(sorted(idx['weeks'].items(), key=lambda kv: int(kv[0])))
    with open(idx_path + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(idx, f, indent=1)
    os.replace(idx_path + '.tmp', idx_path)
    print(f'wrote {os.path.relpath(path, ROOT)}')
    # The cumulative tables read one rollup, not eighteen week files. Rebuilt
    # here so it can never be stale relative to the weeks on disk.
    build_season.main_for(season)


if __name__ == '__main__':
    main()
