# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Script Runner is a FastAPI-based web application that provides a beautiful interface for executing and monitoring local scripts from any device on a network. It features real-time output streaming via native WebSockets, dynamic parameter forms, and reliable async process management.

**Note**: This was rewritten from Flask + Flask-SocketIO to FastAPI in December 2024 to eliminate deadlock issues caused by eventlet/threading incompatibility. The new architecture uses Python's asyncio with native WebSockets for stable, production-ready operation.

## Commands

### Setup and Installation
```bash
# Quick setup (creates venv, installs deps, generates secret key)
./setup.sh

# Manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Development
```bash
# Run the development server (FastAPI)
python3 app.py
# Or with uvicorn directly:
uvicorn app:app --host 0.0.0.0 --port 5000

# Legacy Flask server (deprecated, has deadlock issues)
# python3 script_runner.py

# Run example scripts
python3 example_script.py --name "Test" --count 3 --delay 0.5
python3 example_webapp.py --port 8080
```

### Production Deployment
```bash
# Run with Uvicorn (recommended)
uvicorn app:app --host 0.0.0.0 --port 5000 --workers 1

# Run with Gunicorn + Uvicorn workers (for systemd)
gunicorn app:app --worker-class uvicorn.workers.UvicornWorker --workers 1 --bind 0.0.0.0:5000

# Systemd service management
sudo systemctl start script-runner
sudo systemctl stop script-runner
sudo systemctl status script-runner
```

## Architecture

### Core Components

**app.py** - Main FastAPI application with native WebSocket support
- `/api/scripts` - Returns list of available scripts from YAML config with dynamic IP replacement
- `/api/scripts/<id>/run` - Executes a script with parameters; for web apps, registers the calling client
- `/api/scripts/<id>/stop` - Terminates a running script; for web apps, deregisters the client and only kills the process when the last client stops
- `/api/scripts/<id>/status` - Returns running status and PID
- `/api/scripts/<id>/cleanup-clients` - Clears all client registrations for a script (admin utility)
- `/api/client/registered` - Returns which scripts a given client is registered for (used on page load to restore UI state)
- `/api/client/deregister` - Removes a client from all registered scripts; called via `sendBeacon` on page close
- `/ws` - WebSocket endpoint for real-time communication
- WebSocket message types: `connected`, `output`, `process_complete`, `error`, `output_overflow`

**script_runner.py** - Legacy Flask application (deprecated, has deadlock issues)

**scripts_config.yaml** - Declarative script configuration
- Each script has: `id`, `name`, `description`, `category`, `command`, `working_directory`, `url`, `parameters`
- Parameters support: `name` (flag or "" for positional), `label`, `type` (text/number/file-browser/folder-browser), `required`, `default`, `description`, `placeholder`

**index.html** - Single-page frontend using Tailwind CSS and native WebSockets
- Script cards with category-based color coding
- Parameter input modals with dynamic form generation
- Live output streaming in terminal-style modal
- "Open" button for scripts with URLs
- Automatic reconnection on WebSocket disconnect
- Subscribe/unsubscribe pattern for script output
- `clientSessionId` stored in `sessionStorage` (per-tab, survives refresh but not close)
- `beforeunload` handler calls `navigator.sendBeacon('/api/client/deregister', ...)` to clean up on page close

### Process Management

The application maintains a `running_processes` dictionary (script_id -> {process, output_file, output_size, websockets}) protected by `asyncio.Lock()`. Each script execution:
1. Validates script exists and required parameters are provided
2. Sanitizes command and parameters to prevent injection
3. Spawns subprocess with `stdout=PIPE`, `stderr=STDOUT`
4. Streams output line-by-line via WebSocket using async tasks
5. Sends `process_complete` message to all subscribed WebSockets on termination
6. Removes from `running_processes` on completion
7. Properly cleans up temp files and process resources

**Key improvement over Flask version**: Uses `asyncio.Lock()` instead of `threading.Lock()`, eliminating deadlocks that occurred with eventlet green threads.

### Security Model

- **Input sanitization**: `sanitize_command()` blocks dangerous characters (`;`, `|`, `&`, `$`, `` ` ``, `\n`) and uses subprocess with list arguments (not `shell=True`)
- **No authentication by default**: Production deployments should add authentication middleware, reverse proxy auth, or VPN-only access
- **CORS enabled**: Set to `*` for local network access
- **Dynamic IP replacement**: Automatically replaces localhost in URLs with server's actual IP for network device access

### Architecture History

**December 2024 - FastAPI Rewrite**
The application was completely rewritten from Flask + Flask-SocketIO to FastAPI to eliminate critical stability issues:
- **Problem**: Flask-SocketIO uses eventlet (green threads) while the code used `threading.Lock()` (OS threads), causing deadlocks and server hangs
- **Solution**: FastAPI with native asyncio, using `asyncio.Lock()` for proper async concurrency
- **Benefits**: Stable operation, better performance, modern async/await patterns, native WebSocket support
- All previous bug fixes were preserved in the rewrite

**All critical features maintained**:
1. ✅ Positional arguments work correctly (empty string keys handled properly)
2. ✅ Command parsing uses `shlex.split()` to handle spaces and quotes
3. ✅ Shell commands with operators (&&, ||, |) wrapped in `stdbuf + bash -c`
4. ✅ Frontend required field validation implemented
5. ✅ Async locks eliminate race conditions in process management
6. ✅ Cleanup on exit with signal handlers and lifespan context manager
7. ✅ Memory overflow handling with temp files (5MB server, 2MB client thresholds)
8. ✅ Enhanced command injection protection
9. ✅ Dynamic IP replacement for network device access

**February 2026 - Web App Client Deregistration Fix**
- **Problem**: `clientSessionId` lives in `sessionStorage` (cleared on tab close). When users closed their browser without clicking Stop, their client ID was never removed from `web_app_clients.json`. Stale IDs accumulated and caused `remaining_clients > 0` even when the last real user clicked Stop, preventing the service from being killed.
- **Solution**: Added a `beforeunload` listener that calls `navigator.sendBeacon('/api/client/deregister', ...)` to deregister on page close. Added `/api/client/deregister` endpoint on the server. Also clear `web_app_clients.json` on server startup since all prior sessions are orphaned after a restart.

## Configuration

### Script Definition Pattern
```yaml
scripts:
  - id: unique-id                    # Required, used in API endpoints
    name: Display Name                # Required, shown in UI
    description: What it does         # Optional
    category: System|Development|...  # Optional (affects card color)
    command: "python3 script.py"      # Required, can chain with &&
    working_directory: ~/path         # Optional, expanded with os.path.expanduser()
    url: http://localhost:3000        # Optional, enables "Open" button
    parameters:                       # Optional
      - name: --flag                  # Use "" for positional args
        label: Display Label          # Required
        type: text|number|file-browser|folder-browser  # Required
        required: true|false          # Optional (default: false)
        default: value                # Optional
        description: Help text        # Optional
        placeholder: Example          # Optional
```

### Parameter Types

**text** - Regular text input field
```yaml
- name: "--message"
  label: Message
  type: text
```

**number** - Numeric input (supports integers and decimals)
```yaml
- name: "--count"
  label: Count
  type: number
```

**file-browser** - Server-side file picker
- Shows "Browse" button next to text input
- Opens modal to browse files on the server filesystem
- User can navigate directories and select files
- Selected path populates the text input
- Path is editable manually
- Security: Only allowed to browse configured paths (home, /mnt, /tmp, /var/log by default)
```yaml
- name: ""
  label: Input File
  type: file-browser
  required: true
  placeholder: "/mnt/usb/videos/input.mp4"
```

**folder-browser** - Server-side folder picker
- Same as file-browser but for selecting directories
- Only folders are selectable (files shown for context but not clickable)
```yaml
- name: ""
  label: Source Folder
  type: folder-browser
  required: true
  placeholder: "/mnt/usb/projects/my-data"
```

### Category Colors
- System: Purple
- Development: Blue
- Database: Green
- Web: Orange
- Custom: Gray

## Frontend Integration

The frontend connects to native WebSocket at `/ws` and maintains a `scripts` array. When running a script:
1. If parameters exist, shows modal with dynamically generated form
2. POSTs to `/api/scripts/<id>/run` with `{"parameters": {...}, "client_id": "<uuid>"}`
3. Sends subscribe message via WebSocket: `{type: 'subscribe', script_id: '<id>'}`
4. Receives output via WebSocket messages with `type: 'output'`
5. Displays output in terminal-style modal
6. Shows "Stop" button to POST to `/api/scripts/<id>/stop` with `client_id`
7. Auto-reconnects on disconnect with 3-second retry
8. On page load, calls `/api/client/registered` to restore UI state for already-registered scripts
9. On page close/unload, calls `navigator.sendBeacon('/api/client/deregister', ...)` to clean up registration

### Web App Client Tracking

Web apps (scripts with a `url` field) support multiple concurrent browser clients. The server tracks which clients are "using" a service in `web_app_clients.json`. The process is only killed when the **last registered client** clicks Stop.

**Lifecycle:**
- Client opens the launcher → `restoreRegisteredScripts()` re-registers any previously tracked scripts
- Client clicks Run/Join → registered in `web_app_clients.json`
- Client clicks Stop → deregistered; if last client, process is killed
- Client closes tab/browser → `beforeunload` fires `sendBeacon` to deregister immediately
- Server restarts → `web_app_clients.json` is cleared on startup (all prior sessions are orphaned)

## Dependencies

**Current (FastAPI):**
- FastAPI 0.109.0 - Modern async web framework
- Uvicorn 0.27.0 - ASGI server with WebSocket support
- PyYAML 6.0.1 - Configuration parsing
- Gunicorn 21.2.0 - Production server with Uvicorn workers (optional)

**Legacy (Flask - deprecated):**
- Flask 3.0.0, Flask-SocketIO 5.3.5, eventlet 0.33.3

The app requires Python 3.8+ and uses `subprocess.Popen` for process management with asyncio for output streaming.

## Future Enhancements

### Alternate Design: Client-Side File Upload

**Status**: Designed but not implemented (December 2024)

A comprehensive plan exists for client-side file/folder upload functionality (`file-upload` and `folder-upload` parameter types) that would allow users to upload files from their browser to the server for processing.

**Plan location**: `/home/vinay/.claude/plans/client-side-upload-plan.md`

**Why not implemented**: The current use case primarily involves processing files already on the server (Raspberry Pi). Server-side file browsing (`file-browser` and `folder-browser` types) was chosen as it:
- Avoids uploading large media files over the network
- Provides direct access to server filesystem
- Allows manual path editing for power users
- Matches the existing workflow better

**Future consideration**: The client-side upload plan is fully designed and can be implemented if needed for use cases where users need to upload files from their devices (laptops, phones) for one-off processing tasks.

Both approaches can coexist - the parameter handling infrastructure supports multiple parameter types.
