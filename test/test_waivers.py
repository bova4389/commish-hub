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
        # Uncontested: Ann pays $7 with nobody bidding against her. The next-best
        # bid is $0, so the WHOLE $7 is waste -- a $0 claim would have won him.
        {'type': 'waiver', 'status': 'complete', 'roster_ids': [1], 'adds': {'p14': 1},
         'settings': {'waiver_bid': 7}},
        # A free $0 pickup. The one case that is excluded, and it falls out of
        # the arithmetic on its own rather than needing a special case.
        {'type': 'waiver', 'status': 'complete', 'roster_ids': [2], 'adds': {'p15': 2},
         'settings': {'waiver_bid': 0}},
        {'type': 'free_agent', 'status': 'complete', 'roster_ids': [1], 'adds': {'p13': 1},
         'drops': {}},
    ],
}

# Ann starts p10 in weeks 1-2 (12.0, 8.0) then drops him (absent in week 3).
# Bob rosters p11 from week 2 but never starts him (5.0, 7.0 on the bench).
#
# A claim's return is measured STRICTLY AFTER its week, because Sleeper files a
# Wednesday waiver run under the week whose games just finished. So Ann's week-1
# claim on p10 is judged on weeks 2-3 only -- the 12.0 he scored in week 1 was
# before she owned him and must not be credited. Weeks 1-3 have scores here, so
# played_through is 3 and a week-3 claim has no measurable window at all.
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
           'p14': ('Eli Solo', 'RB'), 'p15': ('Fred Free', 'WR')}


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
eq(len(L['claims']), 4, 'four winning claims')
eq(claims[(1, 'Ace Back')]['bid'], 40, 'Ann paid 40')
eq(claims[(1, 'Ace Back')]['runner_up'], 12, "Cal's 12 is the runner-up")
eq(claims[(1, 'Ace Back')]['round'], 1, 'p10 was a 1st-rounder')
eq(claims[(2, 'Bud Wideout')]['round'], 9, 'p11 was a 9th-rounder')

print('waste -- bid minus the next-best bid, on EVERY claim')
eq(claims[(1, 'Ace Back')]['contested'], True, 'week 1 claim was contested')
eq(claims[(1, 'Ace Back')]['waste'], 28, '40 paid where 12 would have won it')
eq(claims[(1, 'Ace Back')]['waste_solo'], 0, 'contested waste is not solo waste')
eq(claims[(2, 'Bud Wideout')]['waste'], 21, '30 paid where 9 would have won it')
eq(claims[(3, 'Eli Solo')]['contested'], False, 'week 3 claim was uncontested')
eq(claims[(3, 'Eli Solo')]['waste'], 7,
   'an UNCONTESTED bid is wasted in full: a $0 claim would have won him')
eq(claims[(3, 'Eli Solo')]['waste_solo'], 7, 'and all of it is solo waste')
eq(claims[(3, 'Eli Solo')]['free'], False, 'a $7 bid is not a free pickup')
eq(claims[(3, 'Fred Free')]['waste'], 0,
   'THE ONE EXCLUSION: a $0 pickup wastes nothing, straight out of the arithmetic')
eq(claims[(3, 'Fred Free')]['free'], True, 'and it is flagged as a free pickup')

print('return on a claim -- measured STRICTLY AFTER the claim week')
eq(claims[(1, 'Ace Back')]['points_started'], 8.0,
   "only week 2 counts: week 1 was before Ann owned him, week 3 he's gone")
eq(claims[(1, 'Ace Back')]['starts'], 1, 'one start inside the window')
eq(claims[(1, 'Ace Back')]['points_rostered'], 8.0, 'week 3 is not counted: off the roster')
eq(claims[(1, 'Ace Back')]['measured_weeks'], 2, 'weeks 2 and 3 were available to measure')
eq(claims[(2, 'Bud Wideout')]['points_started'], 0.0, 'Bob never started p11')
eq(claims[(2, 'Bud Wideout')]['points_rostered'], 7.0, 'rostered him in week 3 for 7')

print('a claim too new to judge is None, never 0.0')
eq(claims[(3, 'Eli Solo')]['measured_weeks'], 0, 'nothing has been played after week 3')
eq(claims[(3, 'Eli Solo')]['points_started'], None,
   'NOT 0.0 -- "no week yet" and "bought nothing" are different statements')
eq(claims[(3, 'Eli Solo')]['points_rostered'], None, 'same for rostered points')

print('owners')
eq(own['Ann']['spent'], 47, 'Ann spent 40 + 7')
eq(own['Ann']['waste'], 35, 'Ann wasted 28 contested + the whole uncontested 7')
eq(own['Ann']['waste_solo'], 7, 'of which 7 came from the uncontested claim')
eq(own['Ann']['solo_spend'], 7, 'uncontested spend is still reported on its own')
eq(own['Ann']['contested_spend'], 40, 'contested spend excludes the solo claim')
eq(own['Ann']['contested_won'], 1, 'one contested win')
eq(own['Ann']['free_claims'], 0, 'Ann made no free pickups')
eq(own['Ann']['waste_rate'], 0.745, '35 wasted of 47 spent -- denominator is TOTAL spend')
eq(own['Ann']['by_week']['1']['waste'], 28, 'waste is bucketed per week')
eq(own['Ann']['by_week']['3']['waste'], 7, 'including the uncontested week')
eq(own['Bob']['waste'], 21, "Bob's contested win wasted 21; his $0 pickup wasted nothing")
eq(own['Bob']['free_claims'], 1, 'Bob made one free pickup')
eq(own['Cal']['waste'], 0, 'you cannot waste money on a claim you lost')
eq(own['Ann']['won'], 2, 'Ann won two claims')
eq(own['Ann']['lost'], 0, 'Ann lost none')
eq(own['Ann']['measured_claims'], 1, 'only the week-1 claim has a played week behind it')
eq(own['Ann']['measured_spend'], 40, 'so only that $40 is judged on value')
eq(own['Ann']['points_started'], 8.0, 'Ann has 8 measured started points')
eq(own['Ann']['cost_per_point'], 5.0, '$40 of settled spend over 8 points')
eq(own['Cal']['points_started'], None, 'an owner with no measurable claim reads None')
eq(own['Ann']['free_agents'], 1, 'Ann made one free-agent add')
eq(own['Ann']['budget_left'], 53, 'budget left is 100 minus spend')
eq(own['Bob']['cost_per_point'], None, 'Bob started nothing, so cost per point is null not zero')
eq(own['Bob']['points_started'], 0.0, 'but his claim WAS measured, so 0.0 not None')
eq(own['Bob']['points_rostered'], 7.0, 'Bob rostered 7 points he never started')
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
eq(own['Ann']['by_round']['undrafted']['waste'], 7, 'the uncontested claim lands in undrafted')
eq(own['Bob']['by_round']['9']['spent'], 30, 'Bob spent 30 on a 9th-rounder')
eq(own['Cal']['by_round']['undrafted']['lost_bid'], 5, 'the undrafted bucket exists and holds lost bids')
eq(L['totals']['by_round']['1']['spent'], 40, 'league spend by round')
eq(L['totals']['by_pos']['RB']['spent'], 47, 'league spend by position covers both RBs')
eq(L['totals']['spent'], 77, 'league spent 77 in total')
eq(L['totals']['waste'], 56, 'league wasted 28 + 21 + 7')
eq(L['totals']['waste_solo'], 7, 'of which 7 was on a player nobody else bid on')
eq(L['totals']['solo_spend'], 7, 'uncontested spend, the $0 pickup adding nothing')
eq(L['totals']['contested_spend'], 70, 'contested spend is the other 70')
eq(L['totals']['contested'], 2, 'two of the four winning claims were contested')
eq(L['totals']['free_claims'], 1, 'one free $0 pickup')
eq(L['totals']['played_through'], 3, 'weeks 1-3 have scores')
eq(L['totals']['measured_claims'], 2, 'two of the four claims are old enough to judge')
eq(L['totals']['failed'], 3, 'three failed claims')
eq(L['budget'], 100, 'FAAB budget read off league settings')
eq(L['weeks'], [1, 2, 3], 'three weeks of activity')

print('awards -- a comparative award needs a real field')
aw = {a['slug']: a for a in L['awards']}
eq(aw.get('best_value'), None,
   'only one owner has a cost per point, so Best value is not published at all')
eq(aw.get('worst_value'), None, 'and neither is Worst value -- it would be the same person')
eq(aw.get('sharpest'), None, 'two rated owners is under MIN_FIELD_FOR_AWARD')
eq(aw.get('loosest'), None, 'same')
eq(aw['most_wasted']['handle'], 'Ann', 'Ann wasted the most money')
ok('$7 of it on players nobody else bid on' in aw['most_wasted']['value'],
   'and the award splits out the uncontested part')
eq(aw['biggest_overpay']['handle'], 'Ann', 'and made the biggest single overpay')
ok('$28 wasted' in aw['biggest_overpay']['value'], 'the overpay award names the amount wasted')
eq(aw.get('dead_money'), None, 'ROI awards are end-of-season; week 3 is not the end of the season')
eq(aw['outbid']['handle'], 'Cal', 'Cal is always the runner-up')
eq(aw['cold_streak']['handle'], 'Cal', 'Cal has the coldest hand')
eq(aw['biggest_bid']['handle'], 'Ann', 'Ann made the biggest bid')
eq(aw.get('biggest_bust'), None, 'and neither is a bust handed out mid-season')
ok('pts since' in aw['biggest_bid']['value'], 'a settled biggest bid reports its return')
ok('most_wasted' in aw and 'outbid' in aw and 'biggest_overpay' in aw,
   'the money-in/money-out awards are NOT gated: they are true the day a claim clears')

print('the ROI gate opens at season end')
# Same league, judged as though the season ended at week 3. This is the half
# that matters: a gate nobody proves opens is a gate that silently never opens.
end = {a['slug']: a for a in bwv.awards(L['owners'], L['claims'], played_through=3, roi_week=3)}
eq(end['dead_money']['handle'], 'Bob', 'Bob spent 30 on a settled claim and started none of it')
eq(end['biggest_bust']['handle'], 'Ann', 'the bust is judged only among SETTLED claims')
ok('Biggest bust of the season' == end['biggest_bust']['label'], 'and is labelled as a season award')
eq(end.get('best_value'), None, 'the thin-field rule still applies at season end')
eq(end['most_wasted']['handle'], 'Ann', 'the ungated awards are unchanged by the gate')

print()
if fails:
    print(f'{len(fails)} FAILED')
    sys.exit(1)
print('all assertions passed')
