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
                    'model_display_name', 'reasoning_effort', 'source'):
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
        conditions.append("REPLACE(LOWER(model), '.', '-') = ?")
        params.append(model_filter.replace('.', '-').lower())
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
    if period in ('today', 'yesterday'):
        bucket = "strftime('%Y-%m-%d %H:00', timestamp)"
    else:
        bucket = "date(timestamp)"
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


def api_models(period: str):
    where, params = where_clause(period)
    sql = f"""
        SELECT
            COALESCE(model, 'unknown') as model,
            model_display_name,
            COALESCE(SUM(input_tokens), 0),
            COALESCE(SUM(output_tokens), 0),
            COALESCE(SUM(total_tokens), 0),
            COALESCE(SUM(cached_read_tokens), 0),
            COUNT(*)
        FROM usage {where}
        GROUP BY REPLACE(LOWER(COALESCE(model, 'unknown')), '.', '-')
        ORDER BY SUM(total_tokens) DESC
    """
    with sqlite3.connect(db_path()) as conn:
        rows = conn.execute(sql, params).fetchall()
    # Merge rows with the same normalized key (in case SQLite GROUP BY
    # doesn't fully collapse due to differing display names).
    merged = {}
    for r in rows:
        key = normalize_model_key(r[0])
        if key in merged:
            m = merged[key]
            m['input_tokens'] += r[2]
            m['output_tokens'] += r[3]
            m['total_tokens'] += r[4]
            m['cached_read_tokens'] += r[5]
            m['prompt_count'] += r[6]
        else:
            merged[key] = {
                'model': key,
                'display_name': resolve_display_name(r[1], r[0]),
                'input_tokens': r[2],
                'output_tokens': r[3],
                'total_tokens': r[4],
                'cached_read_tokens': r[5],
                'prompt_count': r[6],
            }
    result = []
    for m in merged.values():
        m['new_input_tokens'] = max(m['input_tokens'] - m['cached_read_tokens'], 0) if m['input_tokens'] else 0
        m['estimated_cost'] = estimate_cost(m['model'], m['input_tokens'], m['output_tokens'], m['cached_read_tokens']) or 0
        result.append(m)
    result.sort(key=lambda x: x['total_tokens'], reverse=True)
    return result


def api_recent(limit: int = 20, model_filter: str = None):
    where = ''
    params = []
    if model_filter and model_filter != 'all':
        # Match both dot and dash variants (e.g. "glm-5-2" matches "glm-5.2").
        where = "WHERE REPLACE(LOWER(model), '.', '-') = ?"
        params = [model_filter.replace('.', '-').lower()]
    sql = f"""
        SELECT id, timestamp, session_id, request_id, model, model_display_name,
               input_tokens, output_tokens, total_tokens,
               cached_read_tokens, cached_write_tokens,
               duration_ms, stop_reason, error_message, source
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
        }
        for r in rows
    ]


def api_sessions():
    sql = """
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
        GROUP BY s.session_id
        HAVING COUNT(u.id) > 0
        ORDER BY s.updated_at DESC
    """
    with sqlite3.connect(db_path()) as conn:
        rows = conn.execute(sql).fetchall()
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
                   duration_ms, stop_reason, error_message, source
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
                return self._json(api_sessions())
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
            return self._json({'ok': True, 'message': 'all data cleared'})
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
        return self._json({'error': 'not found'}, 404)


def main():
    ensure_db_columns()
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
