#!/usr/bin/env python3
"""
Scrape model pricing from docs.devin.ai/desktop/models and update pricing.json.

The page embeds a JS array `modelCostData` with per-model token rates.
This script fetches the page, extracts the JSON, and writes a compact
pricing.json keyed by model_uid.

Usage:
    python3 scrape_pricing.py          # fetch + update pricing.json
    python3 scrape_pricing.py --dry    # fetch only, print summary, don't write

jarvis: ceiling stdlib scraper; if the page structure changes, update the regex.
"""

import json
import re
import sys
import urllib.request
from pathlib import Path


URL = 'https://docs.devin.ai/desktop/models'
PRICING_PATH = Path(__file__).parent / 'pricing.json'

# Estimated pricing for free models not in the official table.
# These are guesses based on comparable model tiers.
ESTIMATED_PRICING = {
    'swe-1-7': {
        'label': 'SWE-1.7',
        'in': 1.5,
        'out': 7.0,
        'cr': 0.15,
        'cw': 0,
        'estimated': True,
    },
    'swe-1-6': {
        'label': 'SWE-1.6',
        'in': 1.5,
        'out': 7.0,
        'cr': 0.15,
        'cw': 0,
        'estimated': True,
    },
}


def fetch_page(url: str) -> str:
    req = urllib.request.Request(url, headers={'User-Agent': 'DevinTrack/1.0'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8')


def extract_pricing(html: str) -> dict:
    # The page is a Mintlify build — the JS is escaped and uses backtick-quoted
    # strings. Find the raw array and normalize it.
    marker = 'modelCostData=['
    start = html.find(marker)
    if start == -1:
        raise ValueError('modelCostData not found in page')
    start += len('modelCostData=')
    # Find the matching closing bracket by counting nesting.
    depth = 0
    end = start
    for i in range(start, len(html)):
        c = html[i]
        if c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    raw = html[start:end]
    # Normalize Mintlify build artifacts:
    # 1. Unescape \\" -> "
    # 2. Replace backtick-quoted strings with double-quoted strings
    # 3. Fix bare decimal points like ":.5" -> ":0.5"
    raw = raw.replace('\\"', '"')
    raw = re.sub(r'`([^`]*)`', r'"\1"', raw)
    raw = re.sub(r'":\.', '":0.', raw)
    data = json.loads(raw)
    pricing = {}
    for m in data:
        uid = m.get('model_uid', '')
        if not uid:
            continue
        pricing[uid] = {
            'label': m.get('label', ''),
            'in': m.get('input_cost_per_million_usd', 0),
            'out': m.get('output_cost_per_million_usd', 0),
            'cr': m.get('cache_read_cost_per_million_usd', 0),
            'cw': m.get('cache_write_cost_per_million_usd', 0),
        }
    return pricing


def merge_estimated(pricing: dict) -> dict:
    """Add estimated pricing for free models, preserving any manual overrides."""
    for uid, rates in ESTIMATED_PRICING.items():
        if uid not in pricing or all(
            pricing[uid].get(k) == 0 for k in ('in', 'out', 'cr', 'cw')
        ):
            pricing[uid] = rates
    return pricing


def main():
    dry = '--dry' in sys.argv
    print(f'Fetching {URL}...')
    html = fetch_page(URL)
    print('Extracting pricing data...')
    pricing = extract_pricing(html)
    print(f'Found {len(pricing)} models in official table')
    pricing = merge_estimated(pricing)
    est_count = sum(1 for v in pricing.values() if v.get('estimated'))
    print(f'  + {est_count} estimated (free model) entries')

    if dry:
        print('\nDry run — not writing file. Sample:')
        for uid in ('glm-5-2', 'swe-1-7', 'claude-opus-4-7-high'):
            if uid in pricing:
                p = pricing[uid]
                tag = ' (custom)' if p.get('custom') else (' (estimated)' if p.get('estimated') else '')
                print(f'  {uid:30s} in=${p["in"]:<6} out=${p["out"]:<6} cr=${p["cr"]:<6}{tag}')
        # Show what would be preserved from existing file.
        if PRICING_PATH.exists():
            with open(PRICING_PATH) as f:
                existing = json.load(f)
            preserved = [uid for uid, r in existing.items()
                         if uid not in pricing or r.get('custom') or r.get('estimated')]
            if preserved:
                print(f'\n  Preserved from existing ({len(preserved)}):')
                for uid in preserved[:5]:
                    r = existing[uid]
                    tag = ' (custom)' if r.get('custom') else ' (estimated)'
                    print(f'    {uid:30s} in=${r["in"]:<6} out=${r["out"]:<6}{tag}')
        return

    # Merge with existing pricing.json:
    # - Models in scraped data: replace with fresh scraped values, UNLESS the
    #   existing entry is marked "custom" (user override) — those are preserved.
    # - Models NOT in scraped data: keep existing entry as-is.
    if PRICING_PATH.exists():
        with open(PRICING_PATH) as f:
            existing = json.load(f)
        for uid, rates in existing.items():
            if uid in pricing:
                # Model exists in both — keep user's custom override.
                if rates.get('custom') or rates.get('estimated'):
                    pricing[uid] = rates
            else:
                # Model only in local file — keep it.
                pricing[uid] = rates

    with open(PRICING_PATH, 'w') as f:
        json.dump(pricing, f, indent=2)
    print(f'Wrote {len(pricing)} models to {PRICING_PATH}')


if __name__ == '__main__':
    main()
