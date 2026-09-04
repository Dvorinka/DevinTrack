#!/usr/bin/env python3
"""
Backfill Devin CLI usage into DevinTrack's usage.db from the CLI's own
session database (~/.local/share/devin/cli/sessions.db).

The CLI records per-request token metrics in message_nodes.metadata.metrics
even when the DevinTrack wrapper was not installed. This script extracts
those, maps them to the same schema the wrapper writes, and inserts them
into usage.db so the dashboard shows historical CLI usage.

Token semantics match the wrapper: usage.input_tokens is GROSS input
(new input + cache_read), so the server can compute new_input = input - cached.
The CLI metrics.input_tokens is new-only, so we add cache_read_tokens back.

Idempotent: deduplicates on (session_id, request_id). Safe to re-run.
Read-only on sessions.db (opens in immutable mode).

Usage:
    python3 backfill_cli.py                # backfill today
    python3 backfill_cli.py --date 2026-08-22
    python3 backfill_cli.py --from 2026-08-01 --to 2026-08-23
    python3 backfill_cli.py --dry          # report only, no writes

jarvis: ceiling stdlib backfill; no external deps.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


_EFFORT_SUFFIXES = ('xhigh', 'medium', 'high', 'low', 'max', 'none')

MODEL_DISPLAY_FALLBACK = {
    'glm-5-2': 'GLM-5.2',
    'glm-5-1': 'GLM-5.1',
    'swe-1-7': 'SWE-1.7',
    'swe-1-6': 'SWE-1.6',
    'compactor': 'Compactor',
    'summarizer': 'Summarizer',
}


def extract_reasoning_effort(model_value):
    if not model_value:
        return None
    val = model_value.lower().removesuffix('-fast')
    for suffix in _EFFORT_SUFFIXES:
        if val.endswith('-' + suffix):
            return suffix
    return None


def cli_db_path() -> Path:
    base = os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')
    return Path(base) / 'devin' / 'cli' / 'sessions.db'


def track_db_path() -> Path:
    base = os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')
    return Path(base) / 'devin_track' / 'usage.db'


def local_day_bounds(date_str):
    """Return (start_epoch, end_epoch) in local time for a given YYYY-MM-DD."""
    day = datetime.fromisoformat(date_str).astimezone()
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(hour=23, minute=59, second=59)
    return int(start.timestamp()), int(end.timestamp())


def session_model_label(metadata_json):
    """Extract the main model display label from session metadata response_dimensions."""
    if not metadata_json:
        return None
    try:
        md = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
    except (json.JSONDecodeError, TypeError):
        return None
    for d in md.get('response_dimensions', []) or []:
        if d.get('uid') == 'model':
            val = d.get('kind', {})
            # Schema has varied: {"Metric": {"value": ...}} or {"type":"metric","value":...}
            if isinstance(val, dict):
                metric = val.get('Metric') or val
                if isinstance(metric, dict):
                    return metric.get('value')
    return None


def resolve_model(generation_model, main_label):
    """Return (model_key, display_name, reasoning_effort) for a request.

    generation_model: per-request model id from the CLI (e.g. 'glm-5-2', 'compactor').
    main_label: the session's main model display label (e.g. 'GLM-5.2 High') or None.
    """
    gm = (generation_model or 'unknown').lower()
    # If this request used the session's main agent model and we have a label
    # with an effort suffix, use the dashed label form (matches the wrapper).
    if main_label:
        label_dashed = main_label.lower().replace(' ', '-')
        label_base = label_dashed
        for suffix in _EFFORT_SUFFIXES:
            if label_dashed.endswith('-' + suffix):
                label_base = label_dashed[: -(len(suffix) + 1)]
                break
        # Normalize both to dashed form before comparing (label uses dots,
        # generation_model uses dashes: 'glm-5.2' vs 'glm-5-2').
        label_base_norm = label_base.replace('.', '-')
        gm_base = gm
        for suffix in _EFFORT_SUFFIXES:
            if gm_base.endswith('-' + suffix):
                gm_base = gm_base[: -(len(suffix) + 1)]
                break
        if gm_base == label_base_norm or gm == label_base_norm:
            return label_dashed, main_label, extract_reasoning_effort(label_dashed)
    # Background / unknown models: use generation_model directly.
    display = MODEL_DISPLAY_FALLBACK.get(gm) or gm.replace('-', '.').upper()
    return gm, display, extract_reasoning_effort(gm)


def first_user_prompt(cli_conn, session_id, start_epoch):
    """Best-effort first user prompt text for a session (truncated 500 chars)."""
    row = cli_conn.execute(
        """SELECT chat_message FROM message_nodes
           WHERE session_id=? AND json_extract(chat_message,'$.role')='user'
             AND created_at >= ?
           ORDER BY node_id LIMIT 1""",
        (session_id, start_epoch),
    ).fetchone()
    if not row:
        return None
    try:
        m = json.loads(row[0])
    except json.JSONDecodeError:
        return None
    content = m.get('content')
    if isinstance(content, str):
        return content[:500]
    if isinstance(content, list):
        parts = [b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text']
        text = ' '.join(p for p in parts if p)
        return text[:500] or None
    return None


def backfill(date_from, date_to, dry):
    cli_path = cli_db_path()
    track_path = track_db_path()
    if not cli_path.exists():
        print(f'ERROR: CLI sessions.db not found at {cli_path}', file=sys.stderr)
        sys.exit(1)
    if not track_path.exists():
        print(f'ERROR: DevinTrack usage.db not found at {track_path}', file=sys.stderr)
        sys.exit(1)

    start_epoch, _ = local_day_bounds(date_from)
    _, end_epoch = local_day_bounds(date_to)

    # Immutable read-only: the CLI may be writing to it concurrently.
    cli_conn = sqlite3.connect(f'file:{cli_path}?immutable=1', uri=True)
    track_conn = sqlite3.connect(track_path)

    # Preload existing (session_id, request_id) pairs to skip duplicates.
    existing = set()
    for sid, rid in track_conn.execute('SELECT session_id, request_id FROM usage'):
        if sid and rid:
            existing.add((sid, rid))
    print(f'Existing usage rows: {len(existing)} (will skip duplicates)')

    sessions = cli_conn.execute(
        """SELECT id, working_directory, model, created_at, last_activity_at, title, metadata
           FROM sessions
           WHERE last_activity_at >= ? AND last_activity_at <= ?
           ORDER BY last_activity_at""",
        (start_epoch, end_epoch),
    ).fetchall()
    print(f'Sessions active {date_from}..{date_to}: {len(sessions)}')

    inserted = 0
    skipped = 0
    per_model = {}

    for sid, cwd, smodel, ca, la, title, meta in sessions:
        main_label = session_model_label(meta)
        prompt_text = first_user_prompt(cli_conn, sid, start_epoch)
        created_iso = datetime.fromtimestamp(ca, tz=timezone.utc).isoformat()

        # Upsert session row.
        smodel_key, sdisplay, seffort = resolve_model(smodel, main_label)
        if not dry:
            exists = track_conn.execute(
                'SELECT 1 FROM sessions WHERE session_id=?', (sid,)
            ).fetchone()
            now_iso = datetime.now(timezone.utc).isoformat()
            if exists:
                track_conn.execute(
                    """UPDATE sessions SET
                       updated_at=?, model=COALESCE(?,model),
                       cwd=COALESCE(?,cwd),
                       first_prompt=COALESCE(first_prompt,?),
                       description=COALESCE(description,?),
                       model_display_name=COALESCE(?,model_display_name),
                       reasoning_effort=COALESCE(?,reasoning_effort)
                       WHERE session_id=?""",
                    (now_iso, smodel_key, cwd, prompt_text, title, sdisplay, seffort, sid),
                )
            else:
                track_conn.execute(
                    """INSERT INTO sessions
                       (session_id, created_at, updated_at, model, cwd, first_prompt,
                        description, model_display_name, reasoning_effort, source)
                       VALUES (?,?,?,?,?,?,?,?,?,'local')""",
                    (sid, created_iso, now_iso, smodel_key, cwd, prompt_text, title, sdisplay, seffort),
                )

        # Deduped assistant requests with metrics in the date window.
        rows = cli_conn.execute(
            """SELECT
                 json_extract(chat_message,'$.metadata.request_id') AS rid,
                 json_extract(chat_message,'$.metadata.generation_model') AS gm,
                 json_extract(chat_message,'$.metadata.metrics.input_tokens') AS inp,
                 json_extract(chat_message,'$.metadata.metrics.output_tokens') AS outp,
                 json_extract(chat_message,'$.metadata.metrics.cache_read_tokens') AS cr,
                 json_extract(chat_message,'$.metadata.metrics.cache_creation_tokens') AS cw,
                 json_extract(chat_message,'$.metadata.metrics.total_time_ms') AS ttm,
                 json_extract(chat_message,'$.metadata.finish_reason') AS fin,
                 created_at
               FROM message_nodes
               WHERE session_id=?
                 AND json_extract(chat_message,'$.role')='assistant'
                 AND json_extract(chat_message,'$.metadata.metrics') IS NOT NULL
                 AND json_extract(chat_message,'$.metadata.request_id') IS NOT NULL
                 AND created_at >= ? AND created_at <= ?
               GROUP BY rid
               ORDER BY created_at""",
            (sid, start_epoch, end_epoch),
        ).fetchall()

        for rid, gm, inp, outp, cr, cw, ttm, fin, cat in rows:
            key = (sid, rid)
            if key in existing:
                skipped += 1
                continue
            new_input = int(inp or 0)
            cache_read = int(cr or 0)
            cache_write = int(cw or 0)
            output = int(outp or 0)
            gross_input = new_input + cache_read
            total = gross_input + output
            ts_iso = datetime.fromtimestamp(int(cat), tz=timezone.utc).isoformat()
            model_key, display, effort = resolve_model(gm, main_label)

            if not dry:
                track_conn.execute(
                    """INSERT INTO usage
                       (timestamp, session_id, request_id, model,
                        input_tokens, output_tokens, total_tokens,
                        cached_read_tokens, cached_write_tokens,
                        duration_ms, stop_reason, error_message,
                        model_display_name, reasoning_effort, source, prompt_text)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (ts_iso, sid, rid, model_key,
                     gross_input, output, total,
                     cache_read, cache_write,
                     int(ttm or 0), fin, None,
                     display, effort, 'local', prompt_text),
                )
                existing.add(key)
            inserted += 1
            per_model[model_key] = per_model.get(model_key, 0) + 1

    if not dry:
        track_conn.commit()
    cli_conn.close()
    track_conn.close()

    print(f'\nInserted: {inserted}')
    print(f'Skipped (already present): {skipped}')
    print('Per-model request counts:')
    for m, c in sorted(per_model.items(), key=lambda x: -x[1]):
        print(f'  {m:20s} {c}')


def main():
    ap = argparse.ArgumentParser(description='Backfill Devin CLI usage into DevinTrack.')
    today = datetime.now().astimezone().strftime('%Y-%m-%d')
    ap.add_argument('--date', default=today, help='single day YYYY-MM-DD (default: today)')
    ap.add_argument('--from', dest='date_from', help='start date YYYY-MM-DD')
    ap.add_argument('--to', dest='date_to', help='end date YYYY-MM-DD')
    ap.add_argument('--dry', action='store_true', help='report only, no writes')
    args = ap.parse_args()
    date_from = args.date_from or args.date
    date_to = args.date_to or args.date
    backfill(date_from, date_to, args.dry)


if __name__ == '__main__':
    main()
