# DevinTrack

Track token usage and costs for [Devin](https://devin.ai) sessions. A transparent wrapper sits in front of the `devin` CLI, logs every request's token counts to a local SQLite database, and serves a web dashboard with per-model breakdowns, session details, and cost estimates.

[![CI](https://github.com/Dvorinka/DevinTrack/actions/workflows/ci.yml/badge.svg)](https://github.com/Dvorinka/DevinTrack/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## How it works

```
Devin Desktop  →  devin (wrapper)  →  devin.real (original binary)
                      │
                      ▼
                 usage.db (SQLite)
                      │
                      ▼
              Dashboard server (Python)
                      │
                      ▼
              Web UI (React + Vite)
```

The wrapper intercepts `devin acp` calls, passes them through to the real binary, and parses the JSON-RPC responses for token usage data. It captures:

- Input, output, cached read, and cached write token counts
- Model name and reasoning effort level
- Session prompts and working directory
- Request duration and stop reason

All data is stored locally. No data leaves your machine.

## Platform support

| Platform | Status | Wrapper | Dashboard | Remote sync |
|---|---|---|---|---|
| Linux | Full | Yes | Yes | Yes |
| macOS | Full | Yes | Yes | Yes |
| Windows | Partial | Experimental | Yes | N/A (no SSH) |

The dashboard server and frontend work on all platforms. The wrapper works on Linux and macOS. Windows support is experimental — see [Windows notes](#windows-notes) below.

## Quick start

### 1. Build the dashboard frontend

```bash
cd dashboard/web
npm install
npm run build
```

This produces `dashboard/web/dist/` which the Python server serves statically.

### 2. Install the wrapper

**Linux / macOS:**

```bash
sudo python3 deploy.py
```

Or use the bash convenience script:

```bash
sudo ./deploy.sh
```

This backs up the original `devin` binary to `devin.real` and installs the wrapper in its place. Restart Devin Desktop after deploying.

To remove the wrapper and restore the original binary:

```bash
sudo python3 deploy.py --undeploy
# or
sudo ./undeploy.sh
```

**Windows:**

```powershell
python deploy.py
```

See [Windows notes](#windows-notes) for details.

### 3. Start the dashboard

```bash
python3 dashboard/server.py
```

Open `http://127.0.0.1:7841` in your browser.

The server auto-reprocesses `wrapper.log` at startup to pick up any events that were missed while it wasn't running.

## Configuration

All configuration is via environment variables. No config files needed.

| Variable | Default | Description |
|---|---|---|
| `DEVIN_TRACK_PORT` | `7841` | Dashboard server port |
| `DEVIN_TRACK_HOST` | `127.0.0.1` | Dashboard bind address. Set to `0.0.0.0` to expose to the local network |
| `DEVIN_TRACK_REAL` | *(auto-detected)* | Path to the real `devin` binary |
| `DEVIN_TRACK_SOURCE` | `local` | Source tag for locally captured entries |
| `DEVIN_BIN_DIR` | *(auto-detected)* | Directory containing the Devin binary (deploy script) |
| `XDG_DATA_HOME` | `~/.local/share` | Base directory for data storage (Linux/macOS) |
| `LOCALAPPDATA` | *(system default)* | Base directory for data storage (Windows) |

### Remote sync (optional)

If you run Devin on a remote server, `sync_remote.py` pulls usage data from the remote to your local dashboard via SSH.

```bash
REMOTE_HOST=my-server.com \
REMOTE_USER=root \
REMOTE_KEY=~/.ssh/id_rsa \
python3 dashboard/sync_remote.py
```

| Variable | Default | Description |
|---|---|---|
| `REMOTE_HOST` | *(required)* | Remote host to SSH into |
| `REMOTE_USER` | `root` | SSH user |
| `REMOTE_KEY` | `~/.ssh/id_rsa` | SSH private key path |
| `REMOTE_DB_PATH` | `~/.local/share/devin_track/usage.db` | Path to usage.db on remote |
| `DEVIN_TRACK_SOURCE` | `remote` | Source tag for synced entries |
| `DEVIN_TRACK_PORT` | `7841` | Local dashboard port |

Run continuously with `--loop` (60s interval) or once with no flags. Use `--dry` to preview without inserting.

Custom source tags get unique colors in the dashboard automatically — no code changes needed.

## Data storage

All data is stored in `~/.local/share/devin_track/` (or `%LOCALAPPDATA%\devin_track` on Windows):

| File | Purpose |
|---|---|
| `usage.db` | SQLite database with `usage` and `sessions` tables |
| `wrapper.log` | Raw log of intercepted ACP events |
| `reprocess_state.json` | Byte offset for incremental log processing |

## Dashboard features

- **Overview cards**: Total tokens, estimated cost, request count, session count
- **Usage timeseries**: Token trends over time (7d / 30d / all-time)
- **Model breakdown**: Per-model token usage with reasoning effort badges
- **Session list**: Browsable sessions with model, duration, and cost
- **Session detail**: Per-request breakdown with prompts, tokens, and timing
- **Recent requests**: Latest individual requests across all sessions
- **Filters**: By model, working directory, and time period
- **Cost estimates**: Based on pricing scraped from `docs.devin.ai` (see `pricing.json`)
- **Dynamic source badges**: Custom source tags automatically get unique colors

## Pricing

Cost estimates use per-token rates in `dashboard/pricing.json`. To update pricing:

```bash
python3 dashboard/scrape_pricing.py
```

This scrapes current pricing from `docs.devin.ai` and writes updated rates to `pricing.json`.

## Requirements

- Python 3.10+ (stdlib only, no pip packages)
- Node.js 18+ and npm (for building the frontend)
- Devin Desktop

## Windows notes

Windows support is experimental. The wrapper is a Python script, and Windows doesn't use shebang lines. The `deploy.py` script handles this by:

1. Backing up `devin.exe` to `devin.exe.bak`
2. Installing `devin_wrapper.py` alongside the original
3. Creating a `devin.cmd` shim that calls Python on the wrapper

You may need to set `DEVIN_TRACK_REAL` to point to the backup binary:

```powershell
$env:DEVIN_TRACK_REAL = "C:\path\to\devin.exe.bak"
```

## Project structure

```
devin                    # Wrapper script (Python, replaces the real devin binary)
deploy.py                # Cross-platform installer (Linux, macOS, Windows)
deploy.sh                # Unix convenience wrapper for deploy.py
undeploy.sh              # Unix convenience wrapper for deploy.py --undeploy
dashboard/
  server.py              # HTTP server + SQLite database + API
  sync_remote.py         # SSH-based remote data sync
  pricing.json           # Per-token pricing rates
  scrape_pricing.py      # Pricing scraper
  web/                   # React + Vite + Tailwind frontend
    src/
      App.tsx            # Main dashboard component
      api.ts             # API client
      components/        # UI components
      ui/                # Reusable UI primitives
.github/
  workflows/ci.yml       # CI: typecheck, build, cross-platform compile
  ISSUE_TEMPLATE/        # Bug report and feature request templates
  PULL_REQUEST_TEMPLATE.md
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/overview` | Summary statistics |
| GET | `/api/timeseries` | Token usage over time |
| GET | `/api/models` | Per-model breakdown |
| GET | `/api/sessions` | Session list |
| GET | `/api/sessions/{id}` | Session detail with requests |
| GET | `/api/recent` | Recent requests |
| GET | `/api/performance` | Performance metrics |
| GET | `/api/cwd_list` | Distinct working directories |
| POST | `/api/ingest` | Receive remote sync data |
| POST | `/api/reprocess` | Re-process wrapper.log |
| DELETE | `/api/reset` | Clear all data |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

[MIT](LICENSE)
