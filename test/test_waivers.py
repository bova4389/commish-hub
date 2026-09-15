#!/usr/bin/env python3
"""
Fixture test for scripts/build_waivers.py -- no network.

    python test/test_waivers.py

Sleeper is not reachable from every environment this repo gets worked in (a
Claude Code web session has a GitHub-only egress allowlist), and the waiver
metrics are arithmetic on a shape that is easy to get subtly wrong -- excess vs
spend, a dropped player's points, a shut-out streak. So the shape is canned here
and the numbers are asserted. If a metric's definition changes, change it here
too; the docstring in build_waivers.py is the contract.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import build_week as bw          # noqa: E402
import build_waivers as bwv      # noqa: E402

LID = '999'

# Three owners. Ann wins big and plays them; Bob wins and benches; Cal never wins.
USERS = [
    {'user_id': 'u1', 'display_name': 'Ann', 'metadata': {'team_name': 'Ann FC'}},
    {'user_id': 'u2', 'display_name': 'Bob', 'metadata': {'team_name': 'Bob FC'}},
    {'user_id': 'u3', 'display_name': 'Cal', 'metadata': {'team_name': 'Cal FC'}},
]
ROSTERS = [
    {'roster_id': 1, 'owner_id': 'u1', 'settings': {'waiver_budget_used': 40}, 'metadata': {}},
    {'roster_id': 2, 'owner_id': 'u2', 'settings': {'waiver_budget_used': 30}, 'metadata': {}},
    {'roster_id': 3, 'owner_id': 'u3', 'settings': {'waiver_budget_used': 0}, 'metadata': {}},
]
LEAGUE = {'name': 'Fixture League', 'settings': {'waiver_budget': 100},
          'scoring_settings': {}, 'roster_positions': ['QB', 'RB', 'WR', 'BN']}

# p10 went in round 1, p11 in round 9, p12 was never drafted.
DRAFTS = [{'draft_id': 'd1', 'season': '2026'}]
DRAFT_PICKS = [
    {'draft_id': 'd1', 'player_id': 'p10', 'round': 1, 'pick_no': 3},
    {'draft_id': 'd1', 'player_id': 'p11', 'round': 9, 'pick_no': 100},
]

# Week 1: Ann wins p10 at $40 with Cal bidding $12 -> excess $28, contested.
# Week 2: Bob wins p11 at $30 uncontested -> excess $30 (nobody bid against it).
#         Cal loses a $9 bid on p11 too, so it IS contested. Keep it simple:
#         Cal bids $9 and loses, so runner-up is $9 and excess is $21.
# Week 3: Cal bids $5 on p12 and loses to nobody winning (all claims failed).
TX = {
    1: [
        {'type': 'waiver', 'status': 'complete', 'roster_ids': [1], 'adds': {'p10': 1},
         'settings': {'waiver_bid': 40}},
        {'type': 'waiver', 'status': 'failed', 'roster_ids': [3], 'adds': {'p10': 3},
         'settings': {'waiver_bid': 12}},
    ],
    2: [
        {'type': 'waiver', 'status': 'complete', 'roster_ids': [2], 'adds': {'p11': 2},
         'settings': {'waiver_bid': 30}},
        {'type': 'waiver', 'status': 'failed', 'roster_ids': [3], 'adds': {'p11': 3},
         'settings': {'waiver_bid': 9}},
    ],
    3: [
        {'type': 'waiver', 'status': 'failed', 'roster_ids': [3], 'adds': {'p12': 3},
         'settings': {'waiver_bid': 5}},
        # Uncontested: Ann pays $7 with nobody bidding against her. No runner-up
        # exists, so this is solo_spend and contributes NOTHING to waste.
        {'type': 'waiver', 'status': 'complete', 'roster_ids': [1], 'adds': {'p14': 1},
         'settings': {'waiver_bid': 7}},
        {'type': 'free_agent', 'status': 'complete', 'roster_ids': [1], 'adds': {'p13': 1},
         'drops': {}},
    ],
}

# Ann starts p10 in weeks 1-2 (12.0, 8.0) then drops him (absent in week 3).
# Bob rosters p11 from week 2 but never starts him (5.0, 7.0 on the bench).
MATCHUPS = {
    1: [{'roster_id': 1, 'players_points': {'p10': 12.0}, 'starters': ['p10']},
        {'roster_id': 2, 'players_points': {}, 'starters': []},
        {'roster_id': 3, 'players_points': {}, 'starters': []}],
    2: [{'roster_id': 1, 'players_points': {'p10': 8.0}, 'starters': ['p10']},
        {'roster_id': 2, 'players_points': {'p11': 5.0}, 'starters': []},
        {'roster_id': 3, 'players_points': {}, 'starters': []}],
    3: [{'roster_id': 1, 'players_points': {}, 'starters': []},
        {'roster_id': 2, 'players_points': {'p11': 7.0}, 'starters': []},
        {'roster_id': 3, 'players_points': {}, 'starters': []}],
}

PLAYERS = {'p10': ('Ace Back', 'RB'), 'p11': ('Bud Wideout', 'WR'),
           'p12': ('Cam Tightend', 'TE'), 'p13': ('Dee Kicker', 'K'),
           'p14': ('Eli Solo', 'RB')}


def fake_get(url, cacheable=True):
    if url.endswith(f'/league/{LID}'):
        return LEAGUE
    if url.endswith('/users'):
        return USERS
    if url.endswith('/rosters'):
        return ROSTERS
    if url.endswith('/drafts'):
        return DRAFTS
    if '/draft/d1/picks' in url:
        return DRAFT_PICKS
    if '/transactions/' in url:
        return TX.get(int(url.rsplit('/', 1)[1]), [])
    if '/matchups/' in url:
        return MATCHUPS.get(int(url.rsplit('/', 1)[1]), [])
    raise AssertionError('unexpected URL ' + url)


bw.get = fake_get
bw.players_nfl = lambda: {pid: {'name': n, 'pos': p, 'team': 'XX'} for pid, (n, p) in PLAYERS.items()}

CFG = {'name': 'Fixture League', 'kind': 'h2h', 'ids': {'2026': LID}, 'names': {}}

fails = []


def ok(cond, label):
    if cond:
        print('  ok   ' + label)
    else:
        print('  FAIL ' + label)
        fails.append(label)


def eq(got, want, label):
    ok(got == want, f'{label}: {got!r} == {want!r}' if got == want else f'{label}: got {got!r}, want {want!r}')


L = bwv.build_league('fixture', CFG, 2026, 3)
own = {o['handle']: o for o in L['owners']}
claims = {(c['week'], c['player']): c for c in L['claims']}

print('claims')
eq(len(L['claims']), 3, 'three winning claims')
eq(claims[(1, 'Ace Back')]['bid'], 40, 'Ann paid 40')
eq(claims[(1, 'Ace Back')]['runner_up'], 12, "Cal's 12 is the runner-up")
eq(claims[(1, 'Ace Back')]['round'], 1, 'p10 was a 1st-rounder')
eq(claims[(2, 'Bud Wideout')]['round'], 9, 'p11 was a 9th-rounder')

print('waste -- bid minus the next-best bid, contested claims only')
eq(claims[(1, 'Ace Back')]['contested'], True, 'week 1 claim was contested')
eq(claims[(1, 'Ace Back')]['waste'], 28, '40 paid where 12 would have won it')
eq(claims[(1, 'Ace Back')]['solo'], 0, 'a contested claim has no solo spend')
eq(claims[(2, 'Bud Wideout')]['waste'], 21, '30 paid where 9 would have won it')
eq(claims[(3, 'Eli Solo')]['contested'], False, 'week 3 claim was uncontested')
eq(claims[(3, 'Eli Solo')]['waste'], 0,
   'an uncontested claim wastes NOTHING: there is no runner-up to have paid instead')
eq(claims[(3, 'Eli Solo')]['solo'], 7, 'the whole uncontested bid is solo spend')

print('return on a claim')
eq(claims[(1, 'Ace Back')]['points_started'], 20.0, 'Ann started p10 for 12+8')
eq(claims[(1, 'Ace Back')]['starts'], 2, 'two starts before the drop')
eq(claims[(1, 'Ace Back')]['points_rostered'], 20.0, 'week 3 is not counted: off the roster')
eq(claims[(2, 'Bud Wideout')]['points_started'], 0.0, 'Bob never started p11')
eq(claims[(2, 'Bud Wideout')]['points_rostered'], 12.0, 'but rostered him for 5+7')

print('owners')
eq(own['Ann']['spent'], 47, 'Ann spent 40 + 7')
eq(own['Ann']['waste'], 28, 'only the contested claim wastes anything')
eq(own['Ann']['solo_spend'], 7, 'the uncontested 7 is tracked apart from waste')
eq(own['Ann']['contested_spend'], 40, 'contested spend excludes the solo claim')
eq(own['Ann']['contested_won'], 1, 'one contested win')
eq(own['Ann']['waste_rate'], 0.7, '28 wasted of 40 contested')
eq(own['Ann']['by_week']['1']['waste'], 28, 'waste is bucketed per week')
eq(own['Ann']['by_week']['3']['waste'], 0, 'the solo week wastes nothing')
eq(own['Bob']['waste'], 21, "Bob's contested win wasted 21")
eq(own['Cal']['waste'], 0, 'you cannot waste money on a claim you lost')
eq(own['Ann']['won'], 2, 'Ann won two claims')
eq(own['Ann']['lost'], 0, 'Ann lost none')
eq(own['Ann']['cost_per_point'], 2.35, 'Ann at $2.35 a started point on 47 spent')
eq(own['Ann']['free_agents'], 1, 'Ann made one free-agent add')
eq(own['Ann']['budget_left'], 53, 'budget left is 100 minus spend')
eq(own['Bob']['cost_per_point'], None, 'Bob started nothing, so cost per point is null not zero')
eq(own['Bob']['points_rostered'], 12.0, 'Bob rostered 12 points he never started')
eq(own['Cal']['spent'], 0, 'Cal never won a claim')
eq(own['Cal']['lost'], 3, 'Cal lost three bids')
eq(own['Cal']['lost_bid_total'], 26, 'Cal bid and lost 12+9+5')
eq(own['Cal']['win_rate'], 0.0, 'Cal wins nothing')
eq(own['Cal']['shutout_weeks'], [1, 2, 3], 'Cal was shut out every week he bid')
eq(own['Cal']['shutout_streak'], 3, 'three straight')
eq(own['Ann']['shutout_streak'], 0, 'Ann is not on a cold streak')

print('buckets')
eq(own['Ann']['by_round']['1']['spent'], 40, 'Ann spent 40 on a 1st-rounder')
eq(own['Ann']['by_round']['1']['waste'], 28, 'waste is bucketed by round too')
eq(own['Bob']['by_round']['9']['spent'], 30, 'Bob spent 30 on a 9th-rounder')
eq(own['Cal']['by_round']['undrafted']['lost_bid'], 5, 'the undrafted bucket exists and holds lost bids')
eq(L['totals']['by_round']['1']['spent'], 40, 'league spend by round')
eq(L['totals']['by_pos']['RB']['spent'], 47, 'league spend by position covers both RBs')
eq(L['totals']['spent'], 77, 'league spent 77 in total')
eq(L['totals']['waste'], 49, 'league wasted 28 + 21')
eq(L['totals']['solo_spend'], 7, 'and spent 7 uncontested')
eq(L['totals']['contested_spend'], 70, 'contested spend is the other 70')
eq(L['totals']['contested'], 2, 'two of the three winning claims were contested')
eq(L['totals']['failed'], 3, 'three failed claims')
eq(L['budget'], 100, 'FAAB budget read off league settings')
eq(L['weeks'], [1, 2, 3], 'three weeks of activity')

print('awards')
aw = {a['slug']: a for a in L['awards']}
eq(aw['most_wasted']['handle'], 'Ann', 'Ann wasted the most money')
eq(aw['biggest_overpay']['handle'], 'Ann', 'and made the biggest single overpay')
ok('$28 wasted' in aw['biggest_overpay']['value'], 'the overpay award names the amount wasted')
eq(aw['best_value']['handle'], 'Ann', 'Ann is the best value')
eq(aw['dead_money']['handle'], 'Bob', 'Bob is pure dead money')
eq(aw['outbid']['handle'], 'Cal', 'Cal is always the runner-up')
eq(aw['cold_streak']['handle'], 'Cal', 'Cal has the coldest hand')
eq(aw['biggest_bid']['handle'], 'Ann', 'Ann made the biggest bid')
eq(aw['biggest_bust']['handle'], 'Bob', 'Bob made the biggest bust')
ok('worst_value' not in aw or aw['worst_value']['handle'] == 'Ann',
   'worst value falls to the only priced owner')

print()
if fails:
    print(f'{len(fails)} FAILED')
    sys.exit(1)
print('all assertions passed')
