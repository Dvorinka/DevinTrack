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


def data_dir() -> Path:
    base = os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')
    return Path(base) / 'devin_track'


def db_path() -> Path:
    return data_dir() / 'usage.db'


def web_dist() -> Path:
    return Path(__file__).parent / 'web' / 'dist'


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


def where_clause(period: str):
    """Return (sql_fragment, params) for filtering usage by period."""
    start, end = period_bounds(period)
    if start is None:
        return '', []
    col = "datetime(timestamp)"
    if end is not None:
        return f'WHERE {col} >= ? AND {col} < ?', [start.isoformat(), end.isoformat()]
    return f'WHERE {col} >= ?', [start.isoformat()]


# ---------------------------------------------------------------------------
# API handlers
# ---------------------------------------------------------------------------

def api_overview(period: str):
    where, params = where_clause(period)
    sql = f"""
        SELECT
            COALESCE(SUM(input_tokens), 0),
            COALESCE(SUM(output_tokens), 0),
            COALESCE(SUM(total_tokens), 0),
            COALESCE(SUM(cached_read_tokens), 0),
            COALESCE(SUM(cached_write_tokens), 0),
            COUNT(*),
            COUNT(DISTINCT session_id)
        FROM usage {where}
    """
    with sqlite3.connect(db_path()) as conn:
        row = conn.execute(sql, params).fetchone()
    return {
        'input_tokens': row[0],
        'output_tokens': row[1],
        'total_tokens': row[2],
        'cached_read_tokens': row[3],
        'cached_write_tokens': row[4],
        'prompt_count': row[5],
        'session_count': row[6],
    }


def api_timeseries(period: str):
    where, params = where_clause(period)
    sql = f"""
        SELECT
            date(timestamp) as day,
            COALESCE(SUM(input_tokens), 0),
            COALESCE(SUM(output_tokens), 0),
            COALESCE(SUM(total_tokens), 0),
            COALESCE(SUM(cached_read_tokens), 0)
        FROM usage {where}
        GROUP BY day
        ORDER BY day
    """
    with sqlite3.connect(db_path()) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {
            'date': r[0],
            'input_tokens': r[1],
            'output_tokens': r[2],
            'total_tokens': r[3],
            'cached_read_tokens': r[4],
        }
        for r in rows
    ]


def api_models(period: str):
    where, params = where_clause(period)
    sql = f"""
        SELECT
            COALESCE(model, 'unknown') as model,
            COALESCE(SUM(input_tokens), 0),
            COALESCE(SUM(output_tokens), 0),
            COALESCE(SUM(total_tokens), 0),
            COALESCE(SUM(cached_read_tokens), 0),
            COUNT(*)
        FROM usage {where}
        GROUP BY model
        ORDER BY SUM(total_tokens) DESC
    """
    with sqlite3.connect(db_path()) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [
        {
            'model': r[0],
            'input_tokens': r[1],
            'output_tokens': r[2],
            'total_tokens': r[3],
            'cached_read_tokens': r[4],
            'prompt_count': r[5],
        }
        for r in rows
    ]


def api_recent(limit: int = 20):
    sql = """
        SELECT id, timestamp, session_id, request_id, model,
               input_tokens, output_tokens, total_tokens,
               cached_read_tokens, cached_write_tokens,
               duration_ms, stop_reason, error_message
        FROM usage
        ORDER BY id DESC
        LIMIT ?
    """
    with sqlite3.connect(db_path()) as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return [
        {
            'id': r[0],
            'timestamp': r[1],
            'session_id': r[2],
            'request_id': r[3],
            'model': r[4],
            'input_tokens': r[5],
            'output_tokens': r[6],
            'total_tokens': r[7],
            'cached_read_tokens': r[8],
            'cached_write_tokens': r[9],
            'duration_ms': r[10],
            'stop_reason': r[11],
            'error_message': r[12],
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
            COUNT(u.id) as prompt_count,
            COALESCE(SUM(u.input_tokens), 0),
            COALESCE(SUM(u.output_tokens), 0),
            COALESCE(SUM(u.total_tokens), 0),
            COALESCE(SUM(u.cached_read_tokens), 0),
            COALESCE(SUM(u.duration_ms), 0)
        FROM sessions s
        LEFT JOIN usage u ON u.session_id = s.session_id
        GROUP BY s.session_id
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
            'prompt_count': r[4],
            'input_tokens': r[5],
            'output_tokens': r[6],
            'total_tokens': r[7],
            'cached_read_tokens': r[8],
            'total_duration_ms': r[9],
        }
        for r in rows
    ]


def api_session_detail(session_id: str):
    with sqlite3.connect(db_path()) as conn:
        srow = conn.execute(
            'SELECT session_id, created_at, updated_at, model FROM sessions WHERE session_id = ?',
            (session_id,),
        ).fetchone()
        if not srow:
            return None
        urows = conn.execute(
            """
            SELECT id, timestamp, request_id, model,
                   input_tokens, output_tokens, total_tokens,
                   cached_read_tokens, cached_write_tokens,
                   duration_ms, stop_reason, error_message
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
            'input_tokens': r[4],
            'output_tokens': r[5],
            'total_tokens': r[6],
            'cached_read_tokens': r[7],
            'cached_write_tokens': r[8],
            'duration_ms': r[9],
            'stop_reason': r[10],
            'error_message': r[11],
        }
        for r in urows
    ]
    totals = {
        'input_tokens': sum(r['input_tokens'] for r in requests),
        'output_tokens': sum(r['output_tokens'] for r in requests),
        'total_tokens': sum(r['total_tokens'] for r in requests),
        'cached_read_tokens': sum(r['cached_read_tokens'] for r in requests),
        'cached_write_tokens': sum(r['cached_write_tokens'] for r in requests),
        'duration_ms': sum(r['duration_ms'] for r in requests),
    }
    return {
        'session_id': srow[0],
        'created_at': srow[1],
        'updated_at': srow[2],
        'model': srow[3],
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

            if path == '/api/overview':
                return self._json(api_overview(period))
            if path == '/api/timeseries':
                return self._json(api_timeseries(period))
            if path == '/api/models':
                return self._json(api_models(period))
            if path == '/api/recent':
                limit = min(int(qs.get('limit', ['20'])[0]), 200)
                return self._json(api_recent(limit))
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


def main():
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
