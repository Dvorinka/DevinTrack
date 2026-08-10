#!/usr/bin/env python3
"""
Sync usage data from a remote DevinTrack wrapper to the local dashboard.

SSHes into the remote host, queries its usage.db for entries newer than the
last sync, and POSTs them to the local dashboard's /api/ingest endpoint.

State (last sync timestamp) is stored in ~/.local/share/devin_track/sync_state.json.

Usage:
    python3 sync_remote.py              # sync once
    python3 sync_remote.py --loop       # run continuously (60s interval)
    python3 sync_remote.py --dry        # show what would be synced

Configuration via environment variables:
    REMOTE_HOST     - remote host (no default, required)
    REMOTE_USER     - SSH user (default: root)
    REMOTE_KEY      - SSH key path (default: ~/.ssh/id_rsa)
    REMOTE_DB_PATH  - path to usage.db on remote (default: ~/.local/share/devin_track/usage.db)
    DEVIN_TRACK_SOURCE - source tag for synced entries (default: remote)
    DEVIN_TRACK_PORT - local dashboard port (default: 7841)

jarvis: ceiling stdlib sync; if SSH fails, just log and move on.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def data_dir() -> Path:
    base = os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')
    d = Path(base) / 'devin_track'
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path() -> Path:
    return data_dir() / 'sync_state.json'


def load_state() -> dict:
    p = state_path()
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(state_path(), 'w') as f:
        json.dump(state, f, indent=2)


def ssh_cmd() -> list:
    host = os.environ.get('REMOTE_HOST', '')
    if not host:
        print('ERROR: REMOTE_HOST environment variable is required')
        sys.exit(1)
    user = os.environ.get('REMOTE_USER', 'root')
    key = os.environ.get('REMOTE_KEY', os.path.expanduser('~/.ssh/id_rsa'))
    return ['ssh', '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=accept-new',
            '-i', key, f'{user}@{host}']


def remote_query(sql: str) -> list:
    """Run a SQL query on the remote usage.db and return rows as JSON.

    Pipes the Python script via stdin to avoid shell quoting issues.
    """
    remote_db = os.environ.get('REMOTE_DB_PATH', os.path.expanduser('~/.local/share/devin_track/usage.db'))
    script = (
        f"import json,sqlite3\n"
        f"conn=sqlite3.connect({remote_db!r})\n"
        f"conn.row_factory=sqlite3.Row\n"
        f"rows=conn.execute({sql!r}).fetchall()\n"
        f"print(json.dumps([dict(r) for r in rows]))\n"
    )
    cmd = ssh_cmd() + ['python3 -']
    result = subprocess.run(cmd, input=script, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f'SSH query failed: {result.stderr.strip()}')
    return json.loads(result.stdout.strip())


def fetch_remote_data(since_ts: str = None) -> dict:
    """Fetch usage and session entries from the remote since the given timestamp."""
    where = f"WHERE timestamp > '{since_ts}'" if since_ts else ''
    usage_sql = (
        f"SELECT timestamp, session_id, request_id, model, "
        f"input_tokens, output_tokens, total_tokens, "
        f"cached_read_tokens, cached_write_tokens, "
        f"duration_ms, stop_reason, error_message, "
        f"model_display_name, reasoning_effort "
        f"FROM usage {where} ORDER BY timestamp ASC"
    )
    usage_rows = remote_query(usage_sql)

    # Fetch sessions that were updated since the given timestamp.
    swhere = f"WHERE updated_at > '{since_ts}'" if since_ts else ''
    sessions_sql = (
        f"SELECT session_id, created_at, updated_at, model, "
        f"model_display_name, reasoning_effort, cwd, first_prompt, description "
        f"FROM sessions {swhere} ORDER BY updated_at ASC"
    )
    session_rows = remote_query(sessions_sql)

    return {'usage': usage_rows, 'sessions': session_rows}


def post_to_local(payload: dict) -> dict:
    """POST entries to the local dashboard /api/ingest endpoint."""
    port = os.environ.get('DEVIN_TRACK_PORT', '7841')
    url = f'http://127.0.0.1:{port}/api/ingest'
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=body, method='POST',
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def sync_once(dry: bool = False) -> dict:
    """Perform one sync cycle. Returns summary dict."""
    state = load_state()
    since_ts = state.get('last_sync_ts')

    if since_ts:
        print(f'Syncing remote entries since {since_ts}...')
    else:
        print('Syncing all remote entries (first sync)...')

    try:
        data = fetch_remote_data(since_ts)
    except Exception as e:
        print(f'ERROR: {e}')
        return {'ok': False, 'error': str(e)}

    usage_count = len(data['usage'])
    session_count = len(data['sessions'])
    print(f'  Remote has {usage_count} new usage entries, {session_count} session updates')

    if dry:
        if usage_count:
            latest = data['usage'][-1]
            print(f'  Latest entry: {latest.get("timestamp")} session={latest.get("session_id")}')
        return {'ok': True, 'dry': True, 'usage': usage_count, 'sessions': session_count}

    if usage_count == 0 and session_count == 0:
        print('  Nothing to sync.')
        return {'ok': True, 'inserted': 0, 'skipped': 0}

    payload = {
        'source': os.environ.get('DEVIN_TRACK_SOURCE', 'remote'),
        'usage': data['usage'],
        'sessions': data['sessions'],
    }

    try:
        result = post_to_local(payload)
    except Exception as e:
        print(f'ERROR posting to local: {e}')
        return {'ok': False, 'error': str(e)}

    print(f'  Inserted: {result["inserted_usage"]} usage, {result["inserted_sessions"]} sessions, '
          f'skipped: {result["skipped"]}')

    # Update last sync timestamp to the latest entry we saw.
    if data['usage']:
        latest_ts = data['usage'][-1].get('timestamp')
        if latest_ts:
            state['last_sync_ts'] = latest_ts
            save_state(state)

    return result


def main():
    dry = '--dry' in sys.argv
    loop = '--loop' in sys.argv

    if loop:
        print('Starting continuous sync (60s interval). Ctrl+C to stop.')
        while True:
            try:
                sync_once(dry=False)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f'Unexpected error: {e}')
            time.sleep(60)
    else:
        result = sync_once(dry=dry)
        if not result.get('ok'):
            sys.exit(1)


if __name__ == '__main__':
    main()
