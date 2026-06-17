#!/usr/bin/env python3
"""Fetch rating events from GoatCounter and compute average ratings per app.

Reads /rate/{app_name}/{stars} events, aggregates them, and writes ratings.json.
Requires GOATCOUNTER_TOKEN environment variable.

Output format:
{
  "app_name": {"average": 4.2, "count": 15},
  ...
}
"""
import json
import os
import sys
from collections import defaultdict
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

GOATCOUNTER_SITE = 'sdk-apps'
API_BASE = f'https://{GOATCOUNTER_SITE}.goatcounter.com/api/v0'
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'ratings.json')


def fetch_rating_pages(token):
    """Fetch all pages matching /rate/ prefix from GoatCounter stats."""
    # Use the paths endpoint filtered to /rate/ prefix
    url = f'{API_BASE}/stats/total?filter=/rate/&limit=500'
    req = Request(url)
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Content-Type', 'application/json')

    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data
    except HTTPError as e:
        print(f'GoatCounter API error: {e.code} {e.reason}')
        if e.code == 401:
            print('Token may be invalid or expired.')
        return None
    except URLError as e:
        print(f'Network error: {e.reason}')
        return None


def fetch_paths_list(token):
    """Fetch all tracked paths from GoatCounter."""
    all_paths = []
    after = 0

    while True:
        url = f'{API_BASE}/paths?limit=200&after={after}'
        req = Request(url)
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('Content-Type', 'application/json')

        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except (HTTPError, URLError) as e:
            print(f'Error fetching paths: {e}')
            break

        paths = data.get('paths', [])
        if not paths:
            break

        all_paths.extend(paths)

        # Check if there are more pages
        if data.get('more', False):
            after = paths[-1].get('id', 0)
        else:
            break

    return all_paths


def fetch_path_count(token, path_id):
    """Fetch total hit count for a specific path by ID."""
    # GoatCounter stats/hits returns daily breakdown for a path
    url = f'{API_BASE}/stats/hits/{path_id}?limit=0'
    req = Request(url)
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Content-Type', 'application/json')

    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            # Sum all daily counts
            total = data.get('total', 0)
            if total:
                return total
            # Fallback: sum the stats array
            stats = data.get('stats', [])
            return sum(day.get('daily', 0) for day in stats)
    except (HTTPError, URLError) as e:
        # Try alternative: use count from path listing
        return 0


def fetch_all_path_counts(token, path_ids):
    """Fetch counts for multiple paths using stats/total endpoint."""
    # Try the stats/total endpoint with path filter
    counts = {}
    for pid in path_ids:
        url = f'{API_BASE}/stats/total?filter={pid}'
        req = Request(url)
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('Content-Type', 'application/json')

        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
                # Try different response formats
                total = 0
                if isinstance(data, dict):
                    total = data.get('total', 0)
                    if isinstance(total, dict):
                        total = total.get('total', 0) or total.get('count', 0)
                counts[pid] = total
        except (HTTPError, URLError):
            counts[pid] = 0
    return counts


def compute_ratings(paths, token):
    """Parse /rate/{app}/{stars} paths and compute averages."""
    # app_name -> list of (stars, count) tuples
    app_votes = defaultdict(list)

    for path_info in paths:
        path = path_info.get('path', '')
        # Normalize: strip leading slash if present
        normalized = path.lstrip('/')
        if not normalized.startswith('rate/'):
            continue

        parts = normalized.split('/')
        # Expected: ['rate', 'app_name', 'stars']
        if len(parts) != 3:
            print(f'  Skipping path with wrong parts count: {path} -> {parts}')
            continue

        app_name = parts[1]
        try:
            stars = int(parts[2])
        except ValueError:
            print(f'  Skipping non-integer stars: {path}')
            continue

        if stars < 1 or stars > 5:
            continue

        # Get hit count - try 'total' field first, then API calls
        count = path_info.get('total', 0)
        if not count:
            count = path_info.get('count', 0)
        if not count:
            count = path_info.get('title_count', 0)
        if not count:
            # Use the path ID to fetch count from stats endpoint
            pid = path_info.get('id', 0)
            if pid:
                count = fetch_path_count(token, pid)
                print(f'  Fetched count for {path} (id={pid}): {count}')

        # If we still can't get a count, assume 1 (path exists = at least 1 hit)
        if not count:
            count = 1
            print(f'  Defaulting to count=1 for {path}')

        if count > 0:
            app_votes[app_name].append((stars, count))

    # Compute weighted averages
    ratings = {}
    for app_name, votes in app_votes.items():
        total_votes = sum(count for _, count in votes)
        if total_votes == 0:
            continue
        weighted_sum = sum(stars * count for stars, count in votes)
        average = round(weighted_sum / total_votes, 1)
        ratings[app_name] = {
            'average': average,
            'count': total_votes
        }

    return ratings


def main():
    token = os.environ.get('GOATCOUNTER_TOKEN', '').strip()
    if not token:
        print('GOATCOUNTER_TOKEN not set, writing empty ratings.json')
        with open(OUTPUT_FILE, 'w') as f:
            json.dump({}, f)
        return

    print('Fetching paths from GoatCounter...')
    paths = fetch_paths_list(token)
    if paths is None:
        print('Failed to fetch paths, writing empty ratings.json')
        with open(OUTPUT_FILE, 'w') as f:
            json.dump({}, f)
        return

    rate_paths = [p for p in paths if '/rate/' in p.get('path', '') or p.get('path', '').startswith('rate/')]
    print(f'Found {len(rate_paths)} rating paths out of {len(paths)} total')
    if rate_paths:
        # Debug: show the first few rating paths with all their fields
        for rp in rate_paths[:3]:
            print(f'  Path data: {json.dumps(rp, indent=None)}')
    if not rate_paths and paths:
        # Debug: show what paths exist so we can diagnose
        sample = [p.get('path', '') for p in paths[:20]]
        print(f'  Sample paths: {sample}')

    ratings = compute_ratings(rate_paths, token)
    print(f'Computed ratings for {len(ratings)} apps')

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(ratings, f, indent=2)

    print(f'Written to {OUTPUT_FILE}')
    for app, data in sorted(ratings.items()):
        print(f'  {app}: {data["average"]}★ ({data["count"]} votes)')


if __name__ == '__main__':
    main()
