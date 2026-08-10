#!/usr/bin/env python3
"""
DevinTrack Dashboard server.
Stdlib-only HTTP server serving JSON API from the usage SQLite DB
plus the built React frontend from web/dist.

jarvis: ceiling Python stdlib server; replace with Go Gin in Phase 5.
"""

import json
import os
import sqlite3
import statistics
import sys
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs


# ---------------------------------------------------------------------------
# Model pricing — loaded from pricing.json (scraped from docs.devin.ai)
# ---------------------------------------------------------------------------

_PRICING = None

def load_pricing():
    global _PRICING
    if _PRICING is None:
        path = Path(__file__).parent / 'pricing.json'
        if path.exists():
            with open(path) as f:
                _PRICING = json.load(f)
        else:
            _PRICING = {}
    return _PRICING


def estimate_cost(model, input_tokens, output_tokens, cached_read_tokens, cached_write_tokens=0):
    """Estimate USD cost for a request based on model pricing.
    Returns None if model is unknown.
    Input tokens here are the full input_tokens (includes cached_read).
    Cost = new_input * in_rate + output * out_rate + cached_read * cr_rate + cached_write * cw_rate
    """
    pricing = load_pricing()
    if not model:
        return None
    # Normalize: try exact match, then dots-to-dashes, then prefix match.
    if model in pricing:
        rates = pricing[model]
    else:
        normalized = model.replace('.', '-')
        if normalized in pricing:
            rates = pricing[normalized]
        else:
            # Try prefix match (e.g. "glm-5.2-high" matches "glm-5-2").
            for key in pricing:
                if normalized.startswith(key):
                    rates = pricing[key]
                    break
            else:
                return None
    new_input = max(input_tokens - cached_read_tokens, 0)
    cost = (
        new_input * rates['in'] / 1_000_000 +
        output_tokens * rates['out'] / 1_000_000 +
        cached_read_tokens * rates['cr'] / 1_000_000 +
        cached_write_tokens * rates['cw'] / 1_000_000
    )
    return round(cost, 6)


def data_dir() -> Path:
    base = os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')
    return Path(base) / 'devin_track'


def db_path() -> Path:
    return data_dir() / 'usage.db'


def web_dist() -> Path:
    return Path(__file__).parent / 'web' / 'dist'


def ensure_db_columns():
    """Add columns introduced after the initial schema to existing DBs."""
    with sqlite3.connect(db_path()) as conn:
        # Usage table additions.
        for col in ('cached_read_tokens', 'cached_write_tokens', 'error_message',
                    'model_display_name', 'reasoning_effort', 'source', 'prompt_text'):
            try:
                if 'tokens' in col:
                    conn.execute(f'ALTER TABLE usage ADD COLUMN {col} INTEGER DEFAULT 0')
                else:
                    conn.execute(f'ALTER TABLE usage ADD COLUMN {col} TEXT')
            except sqlite3.OperationalError:
                pass
        # Sessions table additions.
        for col in ('cwd', 'first_prompt', 'description',
                    'model_display_name', 'reasoning_effort', 'source'):
            try:
                conn.execute(f'ALTER TABLE sessions ADD COLUMN {col} TEXT')
            except sqlite3.OperationalError:
                pass


# ---------------------------------------------------------------------------
# Fallback model display name + reasoning effort for rows captured before
# the wrapper stored model_display_name / reasoning_effort.
# ---------------------------------------------------------------------------

MODEL_DISPLAY_FALLBACK = {
    'glm-5-2': 'GLM-5.2',
    'swe-1-7': 'SWE-1.7',
    'claude-opus-5-medium': 'Claude Opus 5 Medium',
    'claude-opus-5-low': 'Claude Opus 5 Low',
    'claude-opus-5-high': 'Claude Opus 5 High',
    'claude-opus-5-xhigh': 'Claude Opus 5 XHigh',
    'claude-opus-5-max': 'Claude Opus 5 Max',
    'claude-sonnet-4-6': 'Claude Sonnet 4.6',
    'claude-sonnet-4-6-thinking': 'Claude Sonnet 4.6 Thinking',
}

_EFFORT_SUFFIXES = ('xhigh', 'medium', 'high', 'low', 'max', 'none')


def fallback_display_name(model):
    if not model:
        return None
    return MODEL_DISPLAY_FALLBACK.get(model)


def fallback_reasoning_effort(model):
    if not model:
        return None
    val = model.lower().removesuffix('-fast')
    for suffix in _EFFORT_SUFFIXES:
        if val.endswith('-' + suffix):
            return suffix
    return None


def resolve_display_name(raw_display, model):
    """Prefer stored display_name, then fallback map, then raw model."""
    if raw_display:
        return raw_display
    return fallback_display_name(model) or model or 'unknown'


def resolve_effort(raw_effort, model):
    if raw_effort:
        return raw_effort
    return fallback_reasoning_effort(model)


# ---------------------------------------------------------------------------
# Period resolution
# ---------------------------------------------------------------------------

PERIODS = ('today', 'yesterday', '7d', '30d', 'month', 'year', 'all')


def period_bounds(period: str):
    """Return (start_dt, end_dt) as timezone-aware datetimes, or (None, None) for all."""
    now = datetime.now(timezone.utc)
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if period == 'yesterday':
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, end
    if period == '7d':
        return now - timedelta(days=7), now
    if period == '30d':
        return now - timedelta(days=30), now
    if period == 'month':
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if period == 'year':
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    return None, None  # all


def where_clause(period: str, model_filter: str = None):
    """Return (sql_fragment, params) for filtering usage by period and optional model."""
    start, end = period_bounds(period)
    conditions = []
    params = []
    col = "datetime(timestamp)"
    if start is not None:
        conditions.append(f'{col} >= datetime(?)')
        params.append(start.isoformat())
        if end is not None:
            conditions.append(f'{col} < datetime(?)')
            params.append(end.isoformat())
    if model_filter and model_filter != 'all':
        # Prefix match: base model key "swe-1-7" matches "swe-1-7-max" too.
        conditions.append("REPLACE(LOWER(model), '.', '-') LIKE ?")
        params.append(model_filter.replace('.', '-').lower() + '%')
    if conditions:
        return 'WHERE ' + ' AND '.join(conditions), params
    return '', []


# ---------------------------------------------------------------------------
# API handlers
# ---------------------------------------------------------------------------

def api_overview(period: str, model_filter: str = None):
    where, params = where_clause(period, model_filter)
    sql = f"""
        SELECT
            model, session_id,
            input_tokens, output_tokens,
            cached_read_tokens, cached_write_tokens
        FROM usage {where}
    """
    with sqlite3.connect(db_path()) as conn:
        rows = conn.execute(sql, params).fetchall()
    input_tokens = sum(r[2] for r in rows)
    output_tokens = sum(r[3] for r in rows)
    total_tokens = input_tokens + output_tokens
    cached_read = sum(r[4] for r in rows)
    cached_write = sum(r[5] for r in rows)
    total_cost = 0.0
    for r in rows:
        c = estimate_cost(r[0], r[2], r[3], r[4], r[5])
        if c is not None:
            total_cost += c
    return {
        'input_tokens': input_tokens,
        'new_input_tokens': max(input_tokens - cached_read, 0),
        'output_tokens': output_tokens,
        'total_tokens': total_tokens,
        'cached_read_tokens': cached_read,
        'cached_write_tokens': cached_write,
        'prompt_count': len(rows),
        'session_count': len(set(r[1] for r in rows)),
        'estimated_cost': round(total_cost, 4),
    }


def api_timeseries(period: str, model_filter: str = None):
    where, params = where_clause(period, model_filter)
    # Use hourly granularity for today/yesterday, daily for longer periods.
    # Convert UTC timestamps to local time for bucketing so the chart
    # shows hours/days in the user's timezone.
    if period in ('today', 'yesterday'):
        bucket = "strftime('%Y-%m-%d %H:00', datetime(timestamp, 'localtime'))"
    else:
        bucket = "date(datetime(timestamp, 'localtime'))"
    sql = f"""
        SELECT
            {bucket} as bucket,
            COALESCE(SUM(input_tokens), 0),
            COALESCE(SUM(output_tokens), 0),
            COALESCE(SUM(total_tokens), 0),
            COALESCE(SUM(cached_read_tokens), 0),
            COALESCE(source, 'local') as source
        FROM usage {where}
        GROUP BY bucket, source
        ORDER BY bucket
    """
    with sqlite3.connect(db_path()) as conn:
        rows = conn.execute(sql, params).fetchall()

    # Merge rows into one dict per bucket, with per-source token fields.
    buckets = {}
    for r in rows:
        date = r[0]
        source = r[5] or 'local'
        if date not in buckets:
            buckets[date] = {'date': date}
        b = buckets[date]
        prefix = 'remote_' if source != 'local' else 'local_'
        b[f'{prefix}input_tokens'] = b.get(f'{prefix}input_tokens', 0) + r[1]
        b[f'{prefix}output_tokens'] = b.get(f'{prefix}output_tokens', 0) + r[2]
        b[f'{prefix}total_tokens'] = b.get(f'{prefix}total_tokens', 0) + r[3]
        b[f'{prefix}cached_read_tokens'] = b.get(f'{prefix}cached_read_tokens', 0) + r[4]

    result = []
    for date in sorted(buckets):
        b = buckets[date]
        # Compute new_input (input - cached) per source.
        li = b.get('local_input_tokens', 0)
        lc = b.get('local_cached_read_tokens', 0)
        ri = b.get('remote_input_tokens', 0)
        rc = b.get('remote_cached_read_tokens', 0)
        b['local_new_input_tokens'] = max(li - lc, 0) if li else 0
        b['remote_new_input_tokens'] = max(ri - rc, 0) if ri else 0
        # Keep legacy fields for backward compat (sum of both sources).
        b['input_tokens'] = li + ri
        b['output_tokens'] = b.get('local_output_tokens', 0) + b.get('remote_output_tokens', 0)
        b['total_tokens'] = b.get('local_total_tokens', 0) + b.get('remote_total_tokens', 0)
        b['cached_read_tokens'] = lc + rc
        b['new_input_tokens'] = b['local_new_input_tokens'] + b['remote_new_input_tokens']
        result.append(b)
    return result


def normalize_model_key(model: str) -> str:
    """Normalize model name for grouping: dots to dashes, lowercase."""
    if not model:
        return 'unknown'
    return model.replace('.', '-').lower()


def base_model_key(model: str) -> str:
    """Normalize and strip reasoning effort suffix to get the base model key.

    'swe-1-7-max' -> 'swe-1-7', 'glm-5-2-high' -> 'glm-5-2', 'summarizer' -> 'summarizer'.
    """
    key = normalize_model_key(model)
    for suffix in _EFFORT_SUFFIXES:
        if key.endswith('-' + suffix):
            return key[: -(len(suffix) + 1)]
    return key


def base_model_display_name(raw_display, model):
    """Get the base model display name without reasoning effort suffix.

    'SWE-1.7 Max' -> 'SWE-1.7', 'GLM-5.2 High' -> 'GLM-5.2'.
    """
    if raw_display:
        for suffix in ('XHigh', 'Medium', 'High', 'Low', 'Max', 'None'):
            if raw_display.endswith(' ' + suffix):
                return raw_display[: -(len(suffix) + 1)]
        return raw_display
    name = fallback_display_name(model)
    if name:
        return name
    base = base_model_key(model)
    return base.replace('-', '.').upper() if base != 'unknown' else 'unknown'


def api_models(period: str):
    where, params = where_clause(period)
    sql = f"""
        SELECT
            COALESCE(model, 'unknown') as model,
            model_display_name,
            reasoning_effort,
            COALESCE(SUM(input_tokens), 0),
            COALESCE(SUM(output_tokens), 0),
            COALESCE(SUM(total_tokens), 0),
            COALESCE(SUM(cached_read_tokens), 0),
            COUNT(*)
        FROM usage {where}
        GROUP BY REPLACE(LOWER(COALESCE(model, 'unknown')), '.', '-'),
                 COALESCE(reasoning_effort, '')
        ORDER BY SUM(total_tokens) DESC
    """
    with sqlite3.connect(db_path()) as conn:
        rows = conn.execute(sql, params).fetchall()
    # Merge rows by base model key (strip reasoning suffix).
    # Track reasoning effort counts to pick the most common one.
    merged = {}
    for r in rows:
        model, display, effort = r[0], r[1], r[2]
        key = base_model_key(model)
        # Resolve reasoning effort: stored > fallback from model name.
        resolved_effort = resolve_effort(effort, model)
        if key in merged:
            m = merged[key]
            m['input_tokens'] += r[3]
            m['output_tokens'] += r[4]
            m['total_tokens'] += r[5]
            m['cached_read_tokens'] += r[6]
            m['prompt_count'] += r[7]
            # Track effort counts to pick the dominant one.
            ek = resolved_effort or 'none'
            m['_effort_counts'][ek] = m['_effort_counts'].get(ek, 0) + r[7]
        else:
            m = {
                'model': key,
                'display_name': base_model_display_name(display, model),
                'input_tokens': r[3],
                'output_tokens': r[4],
                'total_tokens': r[5],
                'cached_read_tokens': r[6],
                'prompt_count': r[7],
                '_effort_counts': {resolved_effort or 'none': r[7]},
            }
            merged[key] = m
    result = []
    for m in merged.values():
        m['new_input_tokens'] = max(m['input_tokens'] - m['cached_read_tokens'], 0) if m['input_tokens'] else 0
        m['estimated_cost'] = estimate_cost(m['model'], m['input_tokens'], m['output_tokens'], m['cached_read_tokens']) or 0
        # Pick the most common reasoning effort.
        effort_counts = m.pop('_effort_counts', {})
        best_effort = max(effort_counts, key=effort_counts.get) if effort_counts else None
        m['reasoning_effort'] = best_effort if best_effort != 'none' else None
        result.append(m)
    result.sort(key=lambda x: x['total_tokens'], reverse=True)
    return result


def api_recent(limit: int = 20, model_filter: str = None):
    where = ''
    params = []
    if model_filter and model_filter != 'all':
        # Prefix match: base model key "swe-1-7" matches "swe-1-7-max" too.
        where = "WHERE REPLACE(LOWER(model), '.', '-') LIKE ?"
        params = [model_filter.replace('.', '-').lower() + '%']
    sql = f"""
        SELECT id, timestamp, session_id, request_id, model, model_display_name,
               input_tokens, output_tokens, total_tokens,
               cached_read_tokens, cached_write_tokens,
               duration_ms, stop_reason, error_message, source,
               reasoning_effort, prompt_text
        FROM usage {where}
        ORDER BY id DESC
        LIMIT ?
    """
    params.append(limit)
    with sqlite3.connect(db_path()) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {
            'id': r[0],
            'timestamp': r[1],
            'session_id': r[2],
            'request_id': r[3],
            'model': r[4],
            'model_display_name': resolve_display_name(r[5], r[4]),
            'input_tokens': r[6],
            'new_input_tokens': max(r[6] - r[9], 0) if r[6] else 0,
            'output_tokens': r[7],
            'total_tokens': r[8],
            'cached_read_tokens': r[9],
            'cached_write_tokens': r[10],
            'duration_ms': r[11],
            'stop_reason': r[12],
            'error_message': r[13],
            'estimated_cost': estimate_cost(r[4], r[6], r[7], r[9], r[10]) or 0,
            'source': r[14] or 'local',
            'reasoning_effort': resolve_effort(r[15], r[4]),
            'prompt_text': r[16],
        }
        for r in rows
    ]


def api_sessions(cwd_filter: str = None):
    where = ''
    params = []
    if cwd_filter and cwd_filter != 'all':
        where = 'WHERE s.cwd = ?'
        params = [cwd_filter]
    sql = f"""
        SELECT
            s.session_id,
            s.created_at,
            s.updated_at,
            s.model,
            s.model_display_name,
            s.cwd,
            s.first_prompt,
            s.description,
            s.reasoning_effort,
            COUNT(u.id) as prompt_count,
            COALESCE(SUM(u.input_tokens), 0),
            COALESCE(SUM(u.output_tokens), 0),
            COALESCE(SUM(u.total_tokens), 0),
            COALESCE(SUM(u.cached_read_tokens), 0),
            COALESCE(SUM(u.duration_ms), 0),
            s.source
        FROM sessions s
        LEFT JOIN usage u ON u.session_id = s.session_id
        {where}
        GROUP BY s.session_id
        HAVING COUNT(u.id) > 0
        ORDER BY s.updated_at DESC
    """
    with sqlite3.connect(db_path()) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {
            'session_id': r[0],
            'created_at': r[1],
            'updated_at': r[2],
            'model': r[3],
            'model_display_name': resolve_display_name(r[4], r[3]),
            'cwd': r[5],
            'first_prompt': r[6],
            'description': r[7],
            'reasoning_effort': resolve_effort(r[8], r[3]),
            'prompt_count': r[9],
            'input_tokens': r[10],
            'new_input_tokens': max(r[10] - r[13], 0) if r[10] else 0,
            'output_tokens': r[11],
            'total_tokens': r[12],
            'cached_read_tokens': r[13],
            'total_duration_ms': r[14],
            'estimated_cost': estimate_cost(r[3], r[10], r[11], r[13]) or 0,
            'source': r[15] or 'local',
        }
        for r in rows
    ]


def api_cwd_list():
    """Return distinct cwd values with session and prompt counts for filtering."""
    with sqlite3.connect(db_path()) as conn:
        rows = conn.execute(
            """SELECT s.cwd, COUNT(DISTINCT s.session_id), COALESCE(SUM(u.id), 0)
               FROM sessions s
               LEFT JOIN usage u ON u.session_id = s.session_id
               WHERE s.cwd IS NOT NULL AND s.cwd != ''
               GROUP BY s.cwd
               ORDER BY s.cwd"""
        ).fetchall()
    return [
        {'cwd': r[0], 'session_count': r[1], 'prompt_count': r[2]}
        for r in rows
    ]


def api_session_detail(session_id: str):
    with sqlite3.connect(db_path()) as conn:
        srow = conn.execute(
            'SELECT session_id, created_at, updated_at, model, model_display_name, cwd, first_prompt, description, reasoning_effort, source FROM sessions WHERE session_id = ?',
            (session_id,),
        ).fetchone()
        if not srow:
            return None
        urows = conn.execute(
            """
            SELECT id, timestamp, request_id, model, model_display_name,
                   input_tokens, output_tokens, total_tokens,
                   cached_read_tokens, cached_write_tokens,
                   duration_ms, stop_reason, error_message, source,
                   reasoning_effort, prompt_text
            FROM usage
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()
    requests = [
        {
            'id': r[0],
            'timestamp': r[1],
            'request_id': r[2],
            'model': r[3],
            'model_display_name': resolve_display_name(r[4], r[3]),
            'input_tokens': r[5],
            'new_input_tokens': max(r[5] - r[8], 0) if r[5] else 0,
            'output_tokens': r[6],
            'total_tokens': r[7],
            'cached_read_tokens': r[8],
            'cached_write_tokens': r[9],
            'duration_ms': r[10],
            'stop_reason': r[11],
            'error_message': r[12],
            'estimated_cost': estimate_cost(r[3], r[5], r[6], r[8], r[9]) or 0,
            'source': r[13] or 'local',
            'reasoning_effort': resolve_effort(r[14], r[3]),
            'prompt_text': r[15],
        }
        for r in urows
    ]
    totals = {
        'input_tokens': sum(r['input_tokens'] for r in requests),
        'new_input_tokens': sum(r['new_input_tokens'] for r in requests),
        'output_tokens': sum(r['output_tokens'] for r in requests),
        'total_tokens': sum(r['total_tokens'] for r in requests),
        'cached_read_tokens': sum(r['cached_read_tokens'] for r in requests),
        'cached_write_tokens': sum(r['cached_write_tokens'] for r in requests),
        'duration_ms': sum(r['duration_ms'] or 0 for r in requests),
        'estimated_cost': round(sum(r['estimated_cost'] for r in requests), 4),
    }
    return {
        'session_id': srow[0],
        'created_at': srow[1],
        'updated_at': srow[2],
        'model': srow[3],
        'model_display_name': resolve_display_name(srow[4], srow[3]),
        'cwd': srow[5],
        'first_prompt': srow[6],
        'description': srow[7],
        'reasoning_effort': resolve_effort(srow[8], srow[3]),
        'source': srow[9] or 'local',
        'requests': requests,
        'totals': totals,
    }


# ---------------------------------------------------------------------------
# Reprocessor: re-read wrapper.log for agent_stopped events and fix usage rows.
# Handles mid-session upgrades, missed events, and duplicate numeric rows.
# ---------------------------------------------------------------------------

def _extract_model_from_config(config_options):
    """Extract model value from configOptions list (same logic as wrapper)."""
    if not isinstance(config_options, list):
        return None
    for opt in config_options:
        if isinstance(opt, dict) and opt.get('id') == 'model':
            return opt.get('currentValue')
    return None


def _parse_session_metadata(log_path):
    """Parse wrapper.log for session/new, session/load requests and responses.

    Returns {session_id: {cwd, model, model_display_name, reasoning_effort, description, created_at}}.
    """
    sessions = {}
    # Map request id -> cwd for session/new (sessionId not known until response).
    pending_cwd = {}

    with open(log_path) as f:
        for line in f:
            # Parse request lines: "INFO request method=session/new params={...}"
            if 'INFO request method=session/new' in line or 'INFO request method=session/load' in line:
                idx = line.find('params=')
                if idx < 0:
                    continue
                try:
                    params = json.loads(line[idx + 7:])
                except json.JSONDecodeError:
                    continue
                sid = params.get('sessionId')
                cwd = params.get('cwd')
                if sid:
                    if sid not in sessions:
                        sessions[sid] = {}
                    if cwd:
                        sessions[sid]['cwd'] = cwd
                # session/new may not have sessionId in the request; stash cwd.
                # The response will have sessionId.
                # We can't link request to response by id from this log format,
                # but session/load has sessionId in the request.

            # Parse response lines: "INFO session response: {...}"
            if 'INFO session response:' in line:
                idx = line.find('{')
                if idx < 0:
                    continue
                # Response may be truncated at 3000 chars; try parsing what we have.
                raw = line[idx:]
                # Find the sessionId field
                sid = None
                for key in ('"sessionId"', '"session_id"'):
                    pos = raw.find(key)
                    if pos >= 0:
                        try:
                            # Extract the value after the key
                            rest = raw[pos + len(key):]
                            # Find the colon and the quoted string
                            colon = rest.find(':')
                            if colon >= 0:
                                rest2 = rest[colon + 1:].strip()
                                if rest2.startswith('"'):
                                    end = rest2.find('"', 1)
                                    if end > 0:
                                        sid = rest2[1:end]
                                        break
                        except Exception:
                            pass
                if not sid:
                    continue
                if sid not in sessions:
                    sessions[sid] = {}

                # Try to extract model from configOptions (may be truncated).
                # Look for "currentValue":"glm-5-2" pattern near "id":"model".
                model = None
                model_pos = raw.find('"id": "model"')
                if model_pos < 0:
                    model_pos = raw.find('"id":"model"')
                if model_pos >= 0:
                    cv_pos = raw.find('"currentValue"', model_pos)
                    if cv_pos >= 0:
                        rest = raw[cv_pos:]
                        colon = rest.find(':')
                        if colon >= 0:
                            rest2 = rest[colon + 1:].strip()
                            if rest2.startswith('"'):
                                end = rest2.find('"', 1)
                                if end > 0:
                                    model = rest2[1:end]

                if model:
                    sessions[sid]['model'] = model
                    display = extract_model_display_name_from_config(raw, model)
                    if display:
                        sessions[sid]['model_display_name'] = display
                    effort = fallback_reasoning_effort(model)
                    if effort:
                        sessions[sid]['reasoning_effort'] = effort

                # Try to extract description/title (top-level, not from configOptions).
                # The session response JSON starts with {"modes":..., "configOptions":..., "sessionId":...}
                # The description/title fields are at the top level, after sessionId.
                for key in ('"description"', '"title"'):
                    # Search after the sessionId position to avoid configOptions descriptions.
                    sid_pos = raw.find(f'"sessionId": "{sid}"')
                    if sid_pos < 0:
                        sid_pos = raw.find(f'"sessionId":"{sid}"')
                    search_start = sid_pos if sid_pos >= 0 else 0
                    pos = raw.find(key, search_start)
                    if pos >= 0:
                        rest = raw[pos + len(key):]
                        colon = rest.find(':')
                        if colon >= 0:
                            rest2 = rest[colon + 1:].strip()
                            if rest2.startswith('"'):
                                end = rest2.find('"', 1)
                                if end > 0:
                                    val = rest2[1:end]
                                    if val and val != 'Write and edit code':
                                        if 'description' not in sessions[sid]:
                                            sessions[sid]['description'] = val
                                        break

                # Timestamp from log line.
                try:
                    raw_ts = line[:23].strip()
                    dt = datetime.strptime(raw_ts, '%Y-%m-%d %H:%M:%S,%f')
                    dt_utc = dt.astimezone(timezone.utc)
                    ts = dt_utc.isoformat()
                    if 'created_at' not in sessions[sid]:
                        sessions[sid]['created_at'] = ts
                    sessions[sid]['updated_at'] = ts
                except (ValueError, IndexError):
                    pass

    return sessions


def _parse_prompt_requests(log_path):
    """Parse wrapper.log for session/prompt requests.

    Returns {session_id: [(log_ts, prompt_text), ...]} ordered by timestamp.
    The first entry for a session is the first_prompt.
    """
    prompts = {}
    with open(log_path) as f:
        for line in f:
            if 'request method=session/prompt' not in line:
                continue
            idx = line.find('params=')
            if idx < 0:
                continue
            try:
                params = json.loads(line[idx + 7:])
            except json.JSONDecodeError:
                continue
            sid = params.get('sessionId')
            if not sid:
                continue
            prompt_blocks = params.get('prompt')
            if not isinstance(prompt_blocks, list):
                continue
            parts = []
            for block in prompt_blocks:
                if isinstance(block, dict) and block.get('type') == 'text':
                    t = block.get('text')
                    if t:
                        parts.append(t)
            if not parts:
                continue
            text = ' '.join(parts)[:500]
            # Parse timestamp.
            log_ts = None
            try:
                raw_ts = line[:23].strip()
                dt = datetime.strptime(raw_ts, '%Y-%m-%d %H:%M:%S,%f')
                log_ts = dt.astimezone(timezone.utc).isoformat()
            except (ValueError, IndexError):
                pass
            if sid not in prompts:
                prompts[sid] = []
            prompts[sid].append((log_ts, text))
    return prompts


def extract_model_display_name_from_config(raw_json, model):
    """Extract display name from configOptions by matching model value."""
    if not model:
        return None
    # Look for the model value in the options to find its display name.
    # Pattern: "value":"<model>"..."name":"<display>"
    val_key = f'"value": "{model}"'
    pos = raw_json.find(val_key)
    if pos < 0:
        val_key = f'"value":"{model}"'
        pos = raw_json.find(val_key)
    if pos < 0:
        return None
    # Search forward for "name":"..." within 200 chars.
    rest = raw_json[pos:pos + 300]
    name_pos = rest.find('"name"')
    if name_pos < 0:
        name_pos = rest.find('"name": ')
    if name_pos >= 0:
        rest2 = rest[name_pos:]
        colon = rest2.find(':')
        if colon >= 0:
            rest3 = rest2[colon + 1:].strip()
            if rest3.startswith('"'):
                end = rest3.find('"', 1)
                if end > 0:
                    return rest3[1:end]
    return None

def _parse_agent_stopped_events(log_path):
    """Parse wrapper.log and return {(session_id, request_id): (params, log_ts)} for agent_stopped.

    log_ts is the timestamp from the log line (ISO format), used for time-proximity
    matching against numeric session/prompt rows in the DB.
    """
    events = {}
    with open(log_path) as f:
        for line in f:
            if '"_cognition.ai/agent_stopped"' not in line:
                continue
            idx = line.find('{')
            if idx < 0:
                continue
            try:
                obj = json.loads(line[idx:])
            except json.JSONDecodeError:
                continue
            if obj.get('method') != '_cognition.ai/agent_stopped':
                continue
            params = obj.get('params') or {}
            session_id = params.get('sessionId')
            stats = params.get('stats') or {}
            request_id = stats.get('requestId')
            if not session_id or not request_id:
                continue
            # Parse log line timestamp: "2026-08-10 07:32:51,123 INFO ..."
            # The logging module uses local time; convert to UTC for DB comparison.
            log_ts = None
            try:
                raw_ts = line[:23].strip()
                dt = datetime.strptime(raw_ts, '%Y-%m-%d %H:%M:%S,%f')
                dt = dt.astimezone(timezone.utc)
                log_ts = dt.isoformat()
            except (ValueError, IndexError):
                pass
            # Last occurrence wins (cumulative counts may update).
            events[(session_id, request_id)] = (params, log_ts)
    return events


def _dim_value(dims, uid, default=0):
    dim = dims.get(uid)
    if not isinstance(dim, dict):
        return default
    kind = dim.get('kind') or {}
    val = kind.get('value')
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def reprocess_wrapper_log():
    """Re-read wrapper.log for agent_stopped events and replace corresponding usage rows.

    Also deletes duplicate numeric session/prompt rows that have a UUID counterpart
    with identical token counts for the same session.
    """
    log_path = data_dir() / 'wrapper.log'
    if not log_path.exists():
        return {'ok': False, 'error': 'wrapper.log not found'}

    events = _parse_agent_stopped_events(log_path)
    if not events:
        return {'ok': True, 'processed': 0, 'inserted': 0, 'deleted_duplicates': 0,
                'sessions_affected': [], 'sessions_created': 0}

    # Parse session metadata from the log (cwd, model, description, etc.).
    session_meta = _parse_session_metadata(log_path)
    # Parse session/prompt requests for first_prompt and per-request prompt text.
    prompt_data = _parse_prompt_requests(log_path)

    processed = 0
    inserted = 0
    deleted_duplicates = 0
    sessions_affected = set()
    sessions_created = 0

    with sqlite3.connect(db_path()) as conn:
        # Phase 0: reconstruct sessions table from log metadata + agent_stopped modelLabel.
        all_session_ids = set(sid for (sid, _) in events)
        for sid in all_session_ids:
            meta = session_meta.get(sid, {})
            # Also extract model info from agent_stopped events for this session.
            model_label = None
            for (eid_sid, eid_rid), (params, log_ts) in events.items():
                if eid_sid == sid:
                    stats = params.get('stats') or {}
                    ml = stats.get('modelLabel')
                    if ml:
                        model_label = ml
                        break

            model = meta.get('model')
            model_display_name = meta.get('model_display_name')
            reasoning_effort = meta.get('reasoning_effort')
            cwd = meta.get('cwd')
            description = meta.get('description')
            created_at = meta.get('created_at')
            updated_at = meta.get('updated_at')
            # First prompt from session/prompt requests.
            first_prompt = None
            if sid in prompt_data and prompt_data[sid]:
                first_prompt = prompt_data[sid][0][1]

            # If we got modelLabel from agent_stopped, it reflects the actual model
            # used (even if switched mid-session). Use it to derive model + display + effort.
            if model_label:
                model_display_name = model_label
                label_dashed = model_label.lower().replace(' ', '-')
                for suffix in _EFFORT_SUFFIXES:
                    if label_dashed.endswith('-' + suffix):
                        reasoning_effort = suffix
                        break
                model = label_dashed

            # Upsert session row.
            existing = conn.execute(
                'SELECT 1 FROM sessions WHERE session_id = ?', (sid,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE sessions SET
                       model = COALESCE(model, ?),
                       model_display_name = COALESCE(model_display_name, ?),
                       reasoning_effort = COALESCE(reasoning_effort, ?),
                       cwd = COALESCE(cwd, ?),
                       first_prompt = COALESCE(first_prompt, ?),
                       description = COALESCE(description, ?),
                       created_at = COALESCE(created_at, ?),
                       updated_at = COALESCE(updated_at, ?),
                       source = 'local'
                       WHERE session_id = ?""",
                    (model, model_display_name, reasoning_effort, cwd,
                     first_prompt, description, created_at, updated_at, sid),
                )
            else:
                conn.execute(
                    """INSERT INTO sessions
                       (session_id, created_at, updated_at, model, model_display_name,
                        reasoning_effort, cwd, first_prompt, description, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'local')""",
                    (sid, created_at, updated_at, model, model_display_name,
                     reasoning_effort, cwd, first_prompt, description),
                )
                sessions_created += 1
        # Phase 1: delete stale numeric rows that are duplicates of agent_stopped
        # events. Uses the LOG timestamp (not DB timestamp) for time proximity,
        # because DB UUID rows may have been overwritten by a previous reprocess
        # run. The log timestamp is the original event time.
        # ±120s window catches the race condition where session/prompt (per-call
        # tokens) arrived shortly after agent_stopped (cumulative tokens).
        sessions_with_events = set(sid for (sid, _) in events)
        for sid in sessions_with_events:
            for (eid_sid, eid_rid), (params, log_ts) in events.items():
                if eid_sid != sid or not log_ts:
                    continue
                cur = conn.execute(
                    """DELETE FROM usage
                       WHERE session_id = ?
                         AND request_id NOT GLOB '*-*'
                         AND ABS(strftime('%s', timestamp) - strftime('%s', ?)) <= 120""",
                    (sid, log_ts),
                )
                deleted_duplicates += cur.rowcount

        # Phase 2: re-insert UUID rows from agent_stopped events.
        for (session_id, request_id), (params, log_ts) in events.items():
            stats = params.get('stats') or {}
            dims = {
                d.get('uid'): d
                for d in (stats.get('responseDimensions') or [])
                if isinstance(d, dict)
            }

            input_new = _dim_value(dims, 'input_tokens')
            output = _dim_value(dims, 'output_tokens')
            cached = _dim_value(dims, 'cached_input_tokens')
            input_gross = input_new + cached
            total = input_gross + output

            cause = params.get('cause') or 'complete'
            stop_reason = 'end_turn' if cause == 'complete' else cause
            duration_ms = stats.get('totalTimeMs') or 0

            # Model metadata from sessions table.
            row = conn.execute(
                'SELECT model, model_display_name, reasoning_effort FROM sessions WHERE session_id = ?',
                (session_id,),
            ).fetchone()
            model = row[0] if row else None
            model_display_name = row[1] if row else None
            reasoning_effort = row[2] if row else None

            # Try model from responseDimensions / modelLabel.
            dim_model = None
            dim = dims.get('model')
            if isinstance(dim, dict):
                kind = dim.get('kind') or {}
                dim_model = kind.get('value')
            model_label = stats.get('modelLabel') or dim_model
            if model_label:
                model_display_name = model_label
                label_dashed = model_label.lower().replace(' ', '-')
                for suffix in _EFFORT_SUFFIXES:
                    if label_dashed.endswith('-' + suffix):
                        reasoning_effort = suffix
                        break
                if not model:
                    model = label_dashed

            # Delete existing rows for this (session_id, request_id) and insert corrected.
            conn.execute(
                'DELETE FROM usage WHERE session_id = ? AND request_id = ?',
                (session_id, request_id),
            )
            # Match prompt_text by session_id and time proximity to the agent_stopped event.
            prompt_text = None
            if session_id in prompt_data and log_ts:
                session_prompts = prompt_data[session_id]
                # Find the prompt closest to but before this agent_stopped event.
                best_diff = None
                for p_ts, p_text in session_prompts:
                    if p_ts is None:
                        continue
                    try:
                        diff = abs((datetime.fromisoformat(log_ts) -
                                    datetime.fromisoformat(p_ts)).total_seconds())
                    except (ValueError, TypeError):
                        continue
                    # Prompt should be before or near the agent_stopped event.
                    if best_diff is None or diff < best_diff:
                        best_diff = diff
                        prompt_text = p_text
            conn.execute(
                """INSERT INTO usage
                   (timestamp, session_id, request_id, model,
                    input_tokens, output_tokens, total_tokens,
                    cached_read_tokens, cached_write_tokens,
                    duration_ms, stop_reason, error_message,
                    model_display_name, reasoning_effort, source, prompt_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (datetime.now(timezone.utc).isoformat(), session_id, request_id, model,
                 input_gross, output, total,
                 cached, 0,
                 duration_ms, stop_reason, None,
                 model_display_name, reasoning_effort, 'local', prompt_text),
            )
            inserted += 1
            sessions_affected.add(session_id)
            processed += 1

        conn.commit()

    return {
        'ok': True,
        'processed': processed,
        'inserted': inserted,
        'deleted_duplicates': deleted_duplicates,
        'sessions_created': sessions_created,
        'sessions_affected': sorted(sessions_affected),
    }


def _and(where: str, extra: str) -> str:
    """Append an AND condition to a WHERE clause, handling empty where."""
    if where:
        return f'{where} AND {extra}'
    return f'WHERE {extra}'


def api_performance(period: str):
    where, params = where_clause(period)
    sql = f"""
        SELECT duration_ms, stop_reason
        FROM usage {_and(where, 'duration_ms IS NOT NULL')}
    """
    error_sql = f"""
        SELECT COUNT(*) FROM usage {_and(where, "stop_reason = 'error'")}
    """
    cancel_sql = f"""
        SELECT COUNT(*) FROM usage {_and(where, "stop_reason IN ('cancelled', 'max_tokens')")}
    """
    with sqlite3.connect(db_path()) as conn:
        rows = conn.execute(sql, params).fetchall()
        error_count = conn.execute(error_sql, params).fetchone()[0]
        cancelled_count = conn.execute(cancel_sql, params).fetchone()[0]
    durations = [r[0] for r in rows if r[0] is not None and r[0] > 0]
    if not durations:
        return {
            'avg_latency_ms': 0,
            'median_latency_ms': 0,
            'max_latency_ms': 0,
            'error_count': error_count,
            'cancelled_count': cancelled_count,
        }
    return {
        'avg_latency_ms': int(statistics.mean(durations)),
        'median_latency_ms': int(statistics.median(durations)),
        'max_latency_ms': max(durations),
        'error_count': error_count,
        'cancelled_count': cancelled_count,
    }

def api_ingest(payload: dict):
    """Receive usage + session entries from a remote source (e.g. Proxmox).

    payload = {
        "source": "proxmox",
        "usage": [ {timestamp, session_id, request_id, model, ...}, ... ],
        "sessions": [ {session_id, created_at, model, ...}, ... ],
    }

    Entries are inserted with the given source tag. Duplicate detection is
    based on (session_id, request_id, timestamp) — existing entries are skipped.
    """
    source = payload.get('source', 'remote')
    usage_rows = payload.get('usage', [])
    session_rows = payload.get('sessions', [])
    inserted_usage = 0
    inserted_sessions = 0
    skipped = 0

    with sqlite3.connect(db_path()) as conn:
        for s in session_rows:
            sid = s.get('session_id')
            if not sid:
                continue
            cur = conn.execute('SELECT 1 FROM sessions WHERE session_id = ?', (sid,))
            if cur.fetchone():
                # Update with remote metadata if we don't have it.
                conn.execute(
                    """UPDATE sessions SET
                       model = COALESCE(model, ?),
                       model_display_name = COALESCE(model_display_name, ?),
                       reasoning_effort = COALESCE(reasoning_effort, ?),
                       cwd = COALESCE(cwd, ?),
                       first_prompt = COALESCE(first_prompt, ?),
                       description = COALESCE(description, ?),
                       source = COALESCE(source, ?)
                       WHERE session_id = ?""",
                    (s.get('model'), s.get('model_display_name'), s.get('reasoning_effort'),
                     s.get('cwd'), s.get('first_prompt'), s.get('description'),
                     source, sid),
                )
            else:
                conn.execute(
                    """INSERT INTO sessions
                       (session_id, created_at, updated_at, model, model_display_name,
                        reasoning_effort, cwd, first_prompt, description, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (sid, s.get('created_at'), s.get('updated_at'),
                     s.get('model'), s.get('model_display_name'),
                     s.get('reasoning_effort'), s.get('cwd'),
                     s.get('first_prompt'), s.get('description'), source),
                )
                inserted_sessions += 1

        for u in usage_rows:
            sid = u.get('session_id', '')
            rid = u.get('request_id', '')
            ts = u.get('timestamp', '')
            # Skip if entry with same (session_id, request_id, timestamp) exists.
            cur = conn.execute(
                'SELECT 1 FROM usage WHERE session_id = ? AND request_id = ? AND timestamp = ?',
                (sid, rid, ts),
            )
            if cur.fetchone():
                skipped += 1
                continue
            conn.execute(
                """INSERT INTO usage
                   (timestamp, session_id, request_id, model,
                    input_tokens, output_tokens, total_tokens,
                    cached_read_tokens, cached_write_tokens,
                    duration_ms, stop_reason, error_message,
                    model_display_name, reasoning_effort, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (ts, sid, rid, u.get('model'),
                 u.get('input_tokens', 0), u.get('output_tokens', 0),
                 u.get('total_tokens', 0),
                 u.get('cached_read_tokens', 0), u.get('cached_write_tokens', 0),
                 u.get('duration_ms'), u.get('stop_reason'), u.get('error_message'),
                 u.get('model_display_name'), u.get('reasoning_effort'), source),
            )
            inserted_usage += 1

        conn.commit()

    return {
        'ok': True,
        'source': source,
        'inserted_usage': inserted_usage,
        'inserted_sessions': inserted_sessions,
        'skipped': skipped,
    }


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # quiet

    def _json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def _static(self, path: str):
        dist = web_dist()
        if not dist.exists():
            self._json({'error': 'frontend not built. Run: cd dashboard/web && npm install && npm run build'}, 503)
            return
        # SPA fallback: serve index.html for non-file routes
        fs_path = dist / path.lstrip('/')
        if not fs_path.exists() or fs_path.is_dir():
            fs_path = dist / 'index.html'
        if not fs_path.exists():
            self._json({'error': 'index.html not found'}, 404)
            return
        ext = fs_path.suffix.lower()
        mime = MIME_TYPES.get(ext, 'application/octet-stream')
        body = fs_path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        # API routes
        if path.startswith('/api/'):
            period = qs.get('period', ['7d'])[0]
            if period not in PERIODS:
                period = '7d'
            model_filter = qs.get('model', ['all'])[0]

            if path == '/api/overview':
                return self._json(api_overview(period, model_filter))
            if path == '/api/timeseries':
                return self._json(api_timeseries(period, model_filter))
            if path == '/api/models':
                return self._json(api_models(period))
            if path == '/api/recent':
                limit = min(int(qs.get('limit', ['20'])[0]), 200)
                return self._json(api_recent(limit, model_filter))
            if path == '/api/sessions':
                cwd_filter = qs.get('cwd', ['all'])[0]
                return self._json(api_sessions(cwd_filter))
            if path == '/api/cwd_list':
                return self._json(api_cwd_list())
            if path.startswith('/api/sessions/'):
                sid = path.split('/')[-1]
                detail = api_session_detail(sid)
                if detail is None:
                    return self._json({'error': 'session not found'}, 404)
                return self._json(detail)
            if path == '/api/performance':
                return self._json(api_performance(period))
            return self._json({'error': 'not found'}, 404)

        # Static files / SPA
        return self._static(path)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == '/api/reset':
            with sqlite3.connect(db_path()) as conn:
                conn.execute('DELETE FROM usage')
                conn.execute('DELETE FROM sessions')
                conn.commit()
            # Auto-reprocess so data comes back from wrapper.log immediately.
            try:
                result = reprocess_wrapper_log()
                return self._json({
                    'ok': True,
                    'message': 'all data cleared and reprocessed',
                    'reprocessed': result.get('processed', 0),
                    'sessions_created': result.get('sessions_created', 0),
                })
            except Exception as e:
                return self._json({'ok': True, 'message': 'all data cleared (reprocess failed)', 'error': str(e)})
        return self._json({'error': 'not found'}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == '/api/ingest':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length) if length else b''
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                return self._json({'error': 'invalid JSON'}, 400)
            result = api_ingest(payload)
            return self._json(result)
        if path == '/api/reprocess':
            return self._json(reprocess_wrapper_log())
        return self._json({'error': 'not found'}, 404)


def main():
    ensure_db_columns()
    if '--reprocess' in sys.argv:
        result = reprocess_wrapper_log()
        print(json.dumps(result, indent=2))
        return
    # Auto-reprocess wrapper.log at startup so the dashboard always
    # has the latest agent_stopped data without user intervention.
    try:
        reprocess_wrapper_log()
    except Exception:
        pass  # non-fatal: log may not exist yet
    port = int(os.environ.get('DEVIN_TRACK_PORT', '7841'))
    server = HTTPServer(('127.0.0.1', port), Handler)
    print(f'DevinTrack dashboard on http://127.0.0.1:{port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == '__main__':
    main()
