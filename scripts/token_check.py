#!/usr/bin/env python3
"""
token_check.py -- how long the Sleeper login token has left. Never prints it.

    python scripts/token_check.py          # reads SLEEPER_TOKEN or scripts/.sleeper_token

Prints the expiry date and days left. Exits 1 if the token is missing, is not a
JWT, or has already expired. In GitHub Actions it also writes `days_left` and
`expires` to $GITHUB_OUTPUT, which the Tuesday workflow uses to open an issue
30 days ahead. Sleeper's tokens last about a year.
"""

import base64
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_week import sleeper_token  # noqa: E402


def main():
    token = sleeper_token()
    if not token:
        sys.exit('no Sleeper token found (SLEEPER_TOKEN or scripts/.sleeper_token)')
    parts = token.split('.')
    if len(parts) != 3:
        sys.exit('the Sleeper token is not a JWT; it was probably pasted with something extra')
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + '==='))
    expires = dt.datetime.fromtimestamp(payload['exp'], dt.timezone.utc)
    days = (expires - dt.datetime.now(dt.timezone.utc)).days
    print(f'Sleeper token expires {expires:%B} {expires.day}, {expires.year} ({days} days left)')
    out = os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out, 'a', encoding='utf-8') as f:
            f.write(f'days_left={days}\nexpires={expires:%Y-%m-%d}\n')
    if days < 0:
        sys.exit('the Sleeper token has expired; copy a fresh one')


if __name__ == '__main__':
    main()
