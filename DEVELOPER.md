# Service Launcher — Developer Notes

This file documents architecture, deployment configurations, security hardening options, advanced usage patterns, and planned future enhancements.

---

## Advanced Script Configuration

### Environment Variables

```yaml
scripts:
  - id: env-script
    name: Script with Env
    command: "bash -c 'export MY_VAR=value && ./script.sh'"
```

### Chaining Commands

```yaml
scripts:
  - id: chain
    name: Build & Deploy
    command: "cd /path && npm install && npm run build && npm start"
```

### Conditional Execution

```yaml
scripts:
  - id: conditional
    name: Conditional Script
    command: "[ -f /tmp/ready ] && ./script.sh || echo 'Not ready'"
```

---

## Production Deployment

### Uvicorn (standalone)

```bash
uvicorn app:app --host 0.0.0.0 --port 5000 --workers 1
```

### Gunicorn + Uvicorn workers

```bash
gunicorn app:app --worker-class uvicorn.workers.UvicornWorker --workers 1 --bind 0.0.0.0:5000
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## Security

### Authentication Options

By default there is no authentication. For production exposure, choose one:

**Option A: Nginx basic auth**

```bash
sudo apt install apache2-utils
htpasswd -c /etc/nginx/.htpasswd admin
```

```nginx
location / {
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://localhost:5000;
    ...
}
```

**Option B: FastAPI HTTP Basic Auth middleware**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

security = HTTPBasic()

def verify(credentials: HTTPBasicCredentials = Depends(security)):
    ok = secrets.compare_digest(credentials.username, "admin") and \
         secrets.compare_digest(credentials.password, "your-password")
    if not ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            headers={"WWW-Authenticate": "Basic"})

# Add Depends(verify) to each route, or use a middleware approach
```

**Option C: Tailscale / VPN access only**

Bind to `127.0.0.1` instead of `0.0.0.0` and access only through Tailscale or SSH tunnel:

```bash
ssh -L 5000:localhost:5000 user@server
```

### HTTPS / TLS

```bash
# Self-signed cert (testing only)
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Run with TLS
uvicorn app:app --host 0.0.0.0 --port 5000 \
  --ssl-keyfile=key.pem --ssl-certfile=cert.pem
```

### File Browser Restrictions

Edit `ALLOWED_BROWSE_PATHS` in `app.py` to control which directories the file browser can access:

```python
ALLOWED_BROWSE_PATHS = [
    os.path.expanduser('~'),
    '/mnt',
    '/data',
    '/var/log',
]
```

### Input Sanitization

`sanitize_command()` in `app.py` blocks:
- Shell injection chars: `;`, `|`, `&`, `$`, `` ` ``, `\n`
- Uses `subprocess` with list arguments (never `shell=True` for non-shell commands)
- Shell commands (`&&`, `|`, etc.) are wrapped in `stdbuf + bash -c` for correct execution

---

## Troubleshooting

### Can't connect from other devices

```bash
sudo ufw allow 5000           # allow port
netstat -tlnp | grep 5000    # verify binding
hostname -I                   # find server IP
```

### Scripts fail to execute

1. Check paths in `scripts_config.yaml`
2. Check script permissions: `chmod +x /path/to/script.sh`
3. Check logs: `journalctl -u service-launcher -f` or `service_launcher.log`

### WebSocket / live output not working

1. Check browser console (F12)
2. If behind nginx, ensure WebSocket headers are proxied (see nginx config above)
3. Try a different browser or clear cache

### Permission errors

For commands that need elevated privileges:

```bash
sudo visudo
# Add:
username ALL=(ALL) NOPASSWD: /path/to/specific/command
```

---

## Potential Future Enhancements

These are planned or considered features, not yet implemented:

- **User authentication** — built-in login page with session management
- **Client-side file upload** — upload files from browser for one-off processing
- **Script scheduling / cron** — run scripts on a schedule from the UI
- **Run history and logs** — persistent log of past executions with timestamps and exit codes
- **Environment variable management** — per-script env vars configurable in the UI
- **Script templates** — pre-built templates for common use cases (backup, media conversion, etc.)
- **Script ordering / drag-and-drop** — reorder cards in the UI
- **Dark mode** — theme toggle
- **Multi-user support** — per-user script visibility and permissions
- **Script tags / search** — filter scripts by category or search by name

---

## Why FastAPI?

The application was rewritten from Flask + Flask-SocketIO to FastAPI in December 2024 to fix critical deadlock issues:

| | Flask version | FastAPI version |
|---|---|---|
| Concurrency | eventlet green threads | asyncio native |
| Locks | `threading.Lock()` | `asyncio.Lock()` |
| WebSockets | Flask-SocketIO | Native FastAPI WS |
| Stability | Deadlocks under load | Stable |

Using `threading.Lock()` inside an eventlet-patched runtime caused deadlocks whenever multiple scripts ran simultaneously. The async rewrite eliminated this entirely.
