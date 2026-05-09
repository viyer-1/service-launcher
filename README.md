# Service Launcher

A web-based dashboard for running and monitoring local scripts from any device on your network. No command line needed after setup.

---

## Quick Start

### 1. Clone and install

```bash
git clone <this-repo>
cd service-launcher
bash install.sh
```

The installer will:
- Check for Python 3.8+
- Create a virtual environment
- Install dependencies
- Install and start a systemd service (runs on boot)
- Print the URL to visit

### 2. Open the dashboard

After installation, open your browser and go to:

```
http://<your-server-ip>:5000
```

The installer prints the exact URL. You can also find your server's IP with:

```bash
hostname -I | awk '{print $1}'
```

### 3. Add your scripts

Click the **"Manage Scripts"** gear button (top-right of the dashboard) to add, edit, or remove scripts — no YAML editing required.

---

## Managing the Service

```bash
sudo systemctl start script-runner
sudo systemctl stop script-runner
sudo systemctl restart script-runner
sudo systemctl status script-runner
journalctl -u script-runner -f       # live logs
```

To uninstall:

```bash
bash install.sh --uninstall
```

---

## Running Manually (Development)

```bash
cd v3
./start.sh        # activates venv and starts on port 5000
```

---

## Configuration

Scripts are defined in `v3/scripts_config.yaml`. The web UI's **Manage Scripts** panel writes to this file automatically.

If you prefer to edit YAML directly, a commented example is in `v3/scripts_config.yaml.example`. The config is hot-reloaded on every page load — no server restart needed.

### Custom Port

```bash
bash install.sh --port=8080
```

Or set `SERVICE_LAUNCHER_PORT=8080` in the environment when running manually.

---

## Features

- **Live Output** — real-time streaming of script output via WebSockets
- **Parameter Forms** — dynamic input forms for scripts that need arguments
- **File/Folder Browser** — server-side file picker for path parameters
- **Web App Integration** — "Open" button for scripts that start web servers
- **Multi-device** — multiple users can connect simultaneously; web apps are only killed when the last user clicks Stop
- **Responsive** — works on desktop, tablet, and mobile

---

## Script Configuration Reference

Scripts are defined in `scripts_config.yaml`:

```yaml
scripts:
  - id: my-script               # unique slug (URL-safe)
    name: My Script             # display name in the UI
    description: What it does  # optional
    category: Tools             # System | Development | Database | Web | Multimedia | AI | Tools
    command: "python3 my_script.py"
    working_directory: "~/scripts"  # optional
    url: "http://localhost:8080"    # optional — enables "Open" button
    parameters:
      - name: "--input"         # flag, or "" for positional
        label: Input File       # shown in the form
        type: file-browser      # text | number | file-browser | folder-browser
        required: true
        placeholder: "/path/to/file.mp4"
        description: The file to process
```

### Parameter Types

| Type | Description |
|------|-------------|
| `text` | Free-text input |
| `number` | Numeric input |
| `file-browser` | Server-side file picker modal |
| `folder-browser` | Server-side folder picker modal |

### Category Colors

| Category | Color |
|----------|-------|
| System | Purple |
| Development | Blue |
| Database | Green |
| Web | Orange |
| Multimedia | Pink |
| AI | Indigo |
| Tools / other | Gray |

---

## Security

- **No authentication by default** — intended for use on a trusted local network (home, office LAN)
- For exposure beyond your local network, add a reverse proxy with authentication (nginx + basic auth, Authelia, Tailscale, etc.)
- Input sanitization is applied to all script parameters to prevent command injection
- File browsing is restricted to configured allowed paths

---

## Architecture

Built with:
- **FastAPI + Uvicorn** — async Python backend with native WebSocket support
- **Tailwind CSS** — single-page frontend, no build step
- **systemd** — production process management

See `CLAUDE.md` for developer architecture notes.

---

## Dependencies

```
fastapi>=0.109.0
uvicorn>=0.27.0
pyyaml>=6.0.1
gunicorn>=21.2.0   # optional, for multi-worker production setups
```
