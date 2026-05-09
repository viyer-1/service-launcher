#!/usr/bin/env python3
"""
Script Runner Web Interface - FastAPI Version
A web-based interface for executing local scripts with live output streaming.
Uses FastAPI with native WebSockets for reliable async operation.
"""

import os
import re
import signal
import subprocess
import asyncio
import yaml
import shlex
import tempfile
import socket
import json
from pathlib import Path
from typing import Dict, Set, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
import logging
import urllib.request
import urllib.error

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('script_runner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Authentication Configuration
# If APP_API_KEY is set in environment, all requests must include it in 'X-API-Key' header
APP_API_KEY = os.getenv('APP_API_KEY')
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if APP_API_KEY and api_key != APP_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    return api_key

# Store running processes with metadata
running_processes: Dict[str, dict] = {}
process_lock = asyncio.Lock()

# Connected WebSocket clients
connected_clients: Set[WebSocket] = set()

# Memory threshold for switching to file-based output (5MB)
OUTPUT_MEMORY_THRESHOLD = int(os.getenv('OUTPUT_MEMORY_THRESHOLD', 5 * 1024 * 1024))

# Allowed browse paths for file/folder browser (security)
# Defaults to current directory if not set
env_allowed_paths = os.getenv('ALLOWED_BROWSE_PATHS')
if env_allowed_paths:
    ALLOWED_BROWSE_PATHS = [p.strip() for p in env_allowed_paths.split(',')]
else:
    ALLOWED_BROWSE_PATHS = [
        os.getcwd(),
        os.path.expanduser('~'),
    ]

# Default directory for file browser
DEFAULT_BROWSE_PATH = os.getenv('DEFAULT_BROWSE_PATH', os.getcwd())

# File for tracking web app client sessions
WEB_APP_CLIENTS_FILE = os.getenv('WEB_APP_CLIENTS_FILE', 'web_app_clients.json')


def load_web_app_clients() -> Dict[str, List[str]]:
    """Load web app client tracking from file."""
    try:
        if os.path.exists(WEB_APP_CLIENTS_FILE):
            with open(WEB_APP_CLIENTS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading web app clients: {e}")
    return {}


def save_web_app_clients(clients: Dict[str, List[str]]):
    """Save web app client tracking to file."""
    try:
        with open(WEB_APP_CLIENTS_FILE, 'w') as f:
            json.dump(clients, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving web app clients: {e}")


def register_web_app_client(script_id: str, client_id: str):
    """Register a client as using a web app."""
    clients = load_web_app_clients()
    if script_id not in clients:
        clients[script_id] = []
    if client_id not in clients[script_id]:
        clients[script_id].append(client_id)
        save_web_app_clients(clients)
        logger.info(f"Registered client {client_id} for {script_id}. Total clients: {len(clients[script_id])}")
    return len(clients[script_id])


def deregister_web_app_client(script_id: str, client_id: str) -> int:
    """Deregister a client from using a web app. Returns remaining client count."""
    clients = load_web_app_clients()
    if script_id in clients and client_id in clients[script_id]:
        clients[script_id].remove(client_id)
        if not clients[script_id]:
            # No more clients, remove the entry
            del clients[script_id]
        save_web_app_clients(clients)
        remaining = len(clients.get(script_id, []))
        logger.info(f"Deregistered client {client_id} from {script_id}. Remaining clients: {remaining}")
        return remaining
    return len(clients.get(script_id, []))


def get_web_app_client_count(script_id: str) -> int:
    """Get the number of clients using a web app."""
    clients = load_web_app_clients()
    return len(clients.get(script_id, []))


def is_path_allowed(path: str) -> bool:
    """
    Check if a path is within allowed browse directories.
    Prevents access to sensitive system directories.
    """
    abs_path = os.path.abspath(path)

    # Check if path starts with any allowed prefix
    for allowed_root in ALLOWED_BROWSE_PATHS:
        allowed_abs = os.path.abspath(allowed_root)

        # Check if path is within this allowed root
        try:
            common = os.path.commonpath([abs_path, allowed_abs])
            if common == allowed_abs:
                return True
        except ValueError:
            # Different drives on Windows
            continue

    return False


def is_url_accessible(url: str, timeout: int = 2) -> bool:
    """
    Check if a URL is accessible (web app is running).
    Returns True if the URL responds (even with errors like 404), False if connection fails.
    """
    try:
        # Replace localhost with actual IP in URL for testing
        test_url = url.replace('localhost', '127.0.0.1')

        req = urllib.request.Request(test_url, method='GET')
        with urllib.request.urlopen(req, timeout=timeout):
            # Any response (even 404, 500) means the server is running
            return True
    except urllib.error.HTTPError:
        # HTTP errors (404, 500, etc.) mean server is running
        return True
    except (urllib.error.URLError, ConnectionRefusedError, OSError, TimeoutError):
        # Connection refused or timeout means server is NOT running
        return False


def get_local_ip() -> str:
    """Get the local IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        try:
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
        finally:
            s.close()
        return local_ip
    except Exception as e:
        logger.warning(f"Could not determine local IP: {e}, using localhost")
        return "localhost"


def load_config() -> dict:
    """Load script configuration from YAML file."""
    config_path = Path('scripts_config.yaml')
    if not config_path.exists():
        logger.error("scripts_config.yaml not found!")
        return {'scripts': []}

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {'scripts': []}


def save_config(config: dict):
    """Write configuration back to scripts_config.yaml."""
    config_path = Path('scripts_config.yaml')
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def sanitize_command(command, params=None) -> list:
    """
    Sanitize command and parameters to prevent command injection.
    Returns the command as a list suitable for subprocess.
    """
    shell_operators = ['&&', '||', '|', '>', '<', '>>', '2>', '&']
    needs_shell = False

    if isinstance(command, str):
        for op in shell_operators:
            if op in command:
                needs_shell = True
                break

        if needs_shell:
            param_str = ""
            if params:
                # Separate positional (numeric/empty keys) from named parameters
                positional = []
                named = []

                for key, value in params.items():
                    str_value = str(value)
                    if any(char in str_value for char in [';', '`', '\n', '\r', '$(']):
                        raise ValueError("Invalid character in parameter value")

                    # Numeric keys or empty string are positional arguments
                    if key == "" or key.isdigit():
                        index = int(key) if key.isdigit() else 0
                        positional.append((index, str_value))
                    else:
                        named.append((key, str_value))

                # Sort positional by index and add to command
                positional.sort(key=lambda x: x[0])
                for _, value in positional:
                    param_str += f' "{value}"'

                # Add named parameters
                for key, value in named:
                    param_str += f' {key} "{value}"'

            full_command = command + param_str
            cmd_list = ['stdbuf', '-oL', '-eL', 'bash', '-c', full_command]
        else:
            try:
                cmd_list = shlex.split(command)
            except ValueError as e:
                raise ValueError(f"Invalid command syntax: {e}")

            if params:
                # Separate positional (numeric/empty keys) from named parameters
                positional = []
                named = []

                for key, value in params.items():
                    str_value = str(value)
                    if any(char in str_value for char in [';', '|', '&', '$', '`', '\n', '\r', '>', '<', '(', ')']):
                        raise ValueError("Invalid character in parameter value")

                    # Numeric keys or empty string are positional arguments
                    if key == "" or key.isdigit():
                        index = int(key) if key.isdigit() else 0
                        positional.append((index, str_value))
                    else:
                        named.append((key, str_value))

                # Sort positional by index and add to command
                positional.sort(key=lambda x: x[0])
                for _, value in positional:
                    cmd_list.append(value)

                # Add named parameters
                for key, value in named:
                    cmd_list.append(key)
                    cmd_list.append(value)
    else:
        cmd_list = list(command)

    return cmd_list


async def stream_output(process: subprocess.Popen, script_id: str):
    """Stream process output via WebSocket, using temp file for large outputs."""
    output_file = None
    output_size = 0

    logger.info(f"Starting output stream for {script_id}, PID: {process.pid}")

    try:
        line_count = 0
        while True:
            # Read line in a non-blocking way
            line = await asyncio.get_event_loop().run_in_executor(
                None, process.stdout.readline
            )

            if not line:
                break

            line_count += 1
            decoded_line = line.decode('utf-8', errors='replace')
            output_size += len(decoded_line)

            if line_count <= 5:
                logger.info(f"[{script_id}] Line {line_count}: {decoded_line.strip()}")

            # Check if we need to switch to file-based output
            if output_size > OUTPUT_MEMORY_THRESHOLD and output_file is None:
                fd, output_file = tempfile.mkstemp(prefix=f'script_runner_{script_id}_', suffix='.log')
                os.close(fd)

                async with process_lock:
                    if script_id in running_processes:
                        running_processes[script_id]['output_file'] = output_file

                logger.info(f"Output for {script_id} exceeded threshold, writing to {output_file}")

                # Send overflow notification to all connected WebSockets
                async with process_lock:
                    if script_id in running_processes:
                        websockets = running_processes[script_id].get('websockets', set())
                        for ws in list(websockets):
                            try:
                                await ws.send_json({
                                    'type': 'output_overflow',
                                    'script_id': script_id,
                                    'message': '\n--- Output exceeded memory limit, switching to file-based storage ---\n'
                                })
                            except Exception:
                                websockets.discard(ws)

            # Write to file if using file-based output
            if output_file:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: open(output_file, 'a', encoding='utf-8').write(decoded_line)
                )

            # Send to all connected WebSockets for this script, or buffer if none
            async with process_lock:
                if script_id in running_processes:
                    websockets = running_processes[script_id].get('websockets', set())
                    output_buffer = running_processes[script_id].get('output_buffer', [])

                    if websockets:
                        # Send to connected WebSockets
                        for ws in list(websockets):
                            try:
                                await ws.send_json({
                                    'type': 'output',
                                    'script_id': script_id,
                                    'output_type': 'stdout',
                                    'data': decoded_line
                                })
                            except Exception as e:
                                logger.error(f"Error sending to WebSocket: {e}")
                                websockets.discard(ws)
                    else:
                        # Buffer output for later delivery
                        output_buffer.append({
                            'type': 'output',
                            'script_id': script_id,
                            'output_type': 'stdout',
                            'data': decoded_line
                        })

        # Wait for process to complete
        await asyncio.get_event_loop().run_in_executor(None, process.wait)

        logger.info(f"Process for {script_id} completed with return code {process.returncode}, {line_count} lines output")

        # Send completion status
        async with process_lock:
            if script_id in running_processes:
                websockets = running_processes[script_id].get('websockets', set())
                output_buffer = running_processes[script_id].get('output_buffer', [])

                completion_msg = {
                    'type': 'process_complete',
                    'script_id': script_id,
                    'return_code': process.returncode
                }

                if websockets:
                    # Send to connected WebSockets
                    for ws in list(websockets):
                        try:
                            await ws.send_json(completion_msg)
                        except Exception:
                            websockets.discard(ws)

                    # Clean up immediately if we sent to WebSockets
                    temp_file = running_processes[script_id].get('output_file')
                    if temp_file and os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                            logger.info(f"Cleaned up temp file for {script_id}: {temp_file}")
                        except Exception as e:
                            logger.error(f"Failed to delete temp file {temp_file}: {e}")

                    # Remove from running processes
                    del running_processes[script_id]
                else:
                    # Buffer completion message for later delivery
                    output_buffer.append(completion_msg)
                    # Mark as completed but keep in dict for buffered output
                    running_processes[script_id]['completed'] = True
                    logger.info(f"Buffered completion for {script_id}, waiting for WebSocket subscription")

    except Exception as e:
        logger.error(f"Error streaming output for {script_id}: {e}")

        # Send error to WebSockets
        async with process_lock:
            if script_id in running_processes:
                websockets = running_processes[script_id].get('websockets', set())
                for ws in list(websockets):
                    try:
                        await ws.send_json({
                            'type': 'error',
                            'script_id': script_id,
                            'message': str(e)
                        })
                    except Exception:
                        websockets.discard(ws)

                # Clean up
                temp_file = running_processes[script_id].get('output_file')
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception:
                        pass
                del running_processes[script_id]


async def cleanup_all_processes():
    """Clean up all running processes and temp files on shutdown."""
    logger.info("Cleaning up all running processes...")
    async with process_lock:
        for script_id, process_info in list(running_processes.items()):
            try:
                process = process_info['process']
                temp_file = process_info.get('output_file')

                if process.poll() is None:
                    logger.info(f"Terminating process for {script_id} (PID: {process.pid})")
                    try:
                        # Kill entire process group
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    except Exception:
                        process.terminate()

                    try:
                        await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(None, lambda: process.wait(timeout=3)),
                            timeout=3
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"Force killing process for {script_id} (PID: {process.pid})")
                        try:
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        except Exception:
                            process.kill()
                        await asyncio.get_event_loop().run_in_executor(None, process.wait)

                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        logger.info(f"Cleaned up temp file: {temp_file}")
                    except Exception as e:
                        logger.error(f"Failed to delete temp file {temp_file}: {e}")

            except Exception as e:
                logger.error(f"Error cleaning up {script_id}: {e}")

        running_processes.clear()
    logger.info("Cleanup complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle app lifecycle events."""
    logger.info("Starting Script Runner...")
    # Clear stale client registrations from previous server sessions.
    # All previously registered sessions are orphaned after a restart.
    save_web_app_clients({})
    logger.info("Cleared stale web app client registrations from previous session.")
    yield
    logger.info("Shutting down Script Runner...")
    await cleanup_all_processes()


# Create FastAPI app
app = FastAPI(title="Script Runner", lifespan=lifespan)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def index():
    """Serve the main page."""
    return FileResponse("index.html")


@app.get("/api/scripts")
async def get_scripts():
    """Get list of available scripts."""
    config = load_config()
    scripts = config.get('scripts', [])

    # Replace localhost with actual server IP in URLs for network access
    local_ip = get_local_ip()
    for script in scripts:
        if 'url' in script and script['url']:
            script['url'] = script['url'].replace('localhost', local_ip)
            script['url'] = script['url'].replace('127.0.0.1', local_ip)

    return scripts


@app.post("/api/scripts/{script_id}/run")
async def run_script(script_id: str, request_data: dict = None):
    """Execute a script."""
    try:
        # Load config and find script
        config = load_config()
        script = next((s for s in config.get('scripts', []) if s['id'] == script_id), None)

        if not script:
            raise HTTPException(status_code=404, detail="Script not found")

        # Get client ID from request (for web apps)
        client_id = request_data.get('client_id') if request_data else None
        is_web_app = 'url' in script and script['url']

        # For web apps: Check if already running and register client
        if is_web_app:
            url = script['url']

            # Check if the web app is already accessible
            if is_url_accessible(url):
                # Web app is running, just register this client
                if client_id:
                    client_count = register_web_app_client(script_id, client_id)
                    logger.info(f"Web app '{script_id}' already running, registered client. Total: {client_count}")

                return {
                    'success': True,
                    'already_running': True,
                    'registered': True,
                    'message': f"Service is already running at {url}",
                    'url': url
                }

        # For non-web apps or web apps that aren't running yet: Check if we're tracking it
        async with process_lock:
            if script_id in running_processes:
                # Non-web app already running
                if not is_web_app:
                    raise HTTPException(status_code=400, detail="Script is already running")
                # Web app tracked by us but not accessible - shouldn't happen, but handle it
                else:
                    logger.warning(f"Web app {script_id} in running_processes but not accessible")

        # Get parameters from request
        params = request_data.get('parameters', {}) if request_data else {}
        logger.info(f"Received parameters for {script_id}: {params}")

        # Validate required parameters
        if 'parameters' in script:
            logger.info(f"Script has {len(script['parameters'])} parameters defined")
            for i, param in enumerate(script['parameters']):
                logger.info(f"Checking param {i}: name='{param['name']}', required={param.get('required', False)}, label={param.get('label')}")
                if param.get('required', False):
                    param_name = param['name']
                    # For positional arguments (empty name), check for numeric key
                    if param_name == "":
                        if str(i) not in params and param_name not in params:
                            logger.error(f"Missing positional param {i}: looking for key '{i}' or '', got keys: {list(params.keys())}")
                            raise HTTPException(
                                status_code=400,
                                detail=f"Required positional parameter '{param.get('label', 'argument')}' missing"
                            )
                        else:
                            logger.info(f"Found positional param {i}")
                    elif param_name not in params:
                        logger.error(f"Missing named param '{param_name}', got keys: {list(params.keys())}")
                        raise HTTPException(
                            status_code=400,
                            detail=f"Required parameter '{param_name}' missing"
                        )
                    else:
                        logger.info(f"Found named param '{param_name}'")

        # Sanitize and prepare command
        try:
            cmd = sanitize_command(script['command'], params)
            logger.info(f"Executing script '{script_id}' with command: {cmd}")
            logger.info(f"Parameters: {params}")
        except ValueError as e:
            logger.error(f"Command sanitization failed for '{script_id}': {e}")
            raise HTTPException(status_code=400, detail=str(e))

        # Set working directory if specified
        cwd = script.get('working_directory', None)
        if cwd:
            cwd = os.path.expanduser(cwd)
            if not os.path.isdir(cwd):
                raise HTTPException(
                    status_code=400,
                    detail=f"Working directory not found: {cwd}"
                )

        # Start process
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        env['DEBIAN_FRONTEND'] = 'noninteractive'

        # Create new process group so we can kill all child processes
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            bufsize=0,
            universal_newlines=False,
            env=env,
            preexec_fn=os.setsid  # Create new process group
        )

        # Store process with metadata
        async with process_lock:
            running_processes[script_id] = {
                'process': process,
                'output_file': None,
                'output_size': 0,
                'websockets': set(),
                'output_buffer': []  # Buffer output until WebSocket subscribes
            }

        # For web apps: Register this client as the first user
        if is_web_app and client_id:
            client_count = register_web_app_client(script_id, client_id)
            logger.info(f"Started web app '{script_id}', registered first client. Total: {client_count}")

        # Start output streaming in background
        asyncio.create_task(stream_output(process, script_id))

        return {
            'success': True,
            'pid': process.pid,
            'message': 'Script started successfully'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running script {script_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scripts/{script_id}/stop")
async def stop_script(script_id: str, request_data: dict = None):
    """Stop a running script."""
    try:
        # Get client ID from request (for web apps)
        client_id = request_data.get('client_id') if request_data else None

        # Load script config to check if it's a web app
        config = load_config()
        script = next((s for s in config.get('scripts', []) if s['id'] == script_id), None)
        is_web_app = script and 'url' in script and script['url']

        # For web apps: Deregister client and check if we should actually kill the process
        if is_web_app and client_id:
            remaining_clients = deregister_web_app_client(script_id, client_id)

            if remaining_clients > 0:
                # Other clients are still using the web app - don't kill the process
                logger.info(f"Client {client_id} stopped using '{script_id}', but {remaining_clients} clients remain")
                return {
                    'success': True,
                    'message': f'You have been deregistered. {remaining_clients} other client(s) still using this service.',
                    'deregistered_only': True,
                    'remaining_clients': remaining_clients
                }
            else:
                # Last client stopped - proceed to kill the process
                logger.info(f"Last client stopped '{script_id}', terminating process")

        async with process_lock:
            if script_id not in running_processes:
                # Process not in our tracking, but might be running externally (detected via URL check)
                # For web apps, we've already deregistered the client above
                if is_web_app:
                    return {'success': True, 'message': 'You have been deregistered.'}
                else:
                    raise HTTPException(status_code=400, detail="Script is not running")

            process_info = running_processes[script_id]

            # Check if already completed (just buffered output waiting)
            if process_info.get('completed'):
                # Just clean up and remove
                temp_file = process_info.get('output_file')
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception:
                        pass
                del running_processes[script_id]
                return {'success': True, 'message': 'Script already stopped'}

            process = process_info['process']
            temp_file = process_info.get('output_file')

        # Kill entire process group (parent + all children)
        try:
            # Send SIGTERM to the entire process group
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            logger.info(f"Sent SIGTERM to process group {os.getpgid(process.pid)}")
        except ProcessLookupError:
            logger.warning(f"Process group for {script_id} already terminated")
        except Exception as e:
            logger.error(f"Error terminating process group: {e}")

        # Wait briefly for process to terminate
        try:
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, lambda: process.wait(timeout=5)),
                timeout=5
            )
        except asyncio.TimeoutError:
            # Force kill if still running
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                logger.info(f"Sent SIGKILL to process group {os.getpgid(process.pid)}")
            except Exception:
                pass
            await asyncio.get_event_loop().run_in_executor(None, process.wait)

        # Clean up
        async with process_lock:
            if script_id in running_processes:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        logger.info(f"Cleaned up temp file for {script_id}: {temp_file}")
                    except Exception as e:
                        logger.error(f"Failed to delete temp file {temp_file}: {e}")

                del running_processes[script_id]

        return {'success': True, 'message': 'Script stopped'}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping script {script_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scripts/{script_id}/status")
async def get_script_status(script_id: str):
    """Get status of a script."""
    async with process_lock:
        if script_id in running_processes:
            # Check if it's completed but buffered
            if running_processes[script_id].get('completed'):
                is_running = False
                pid = None
            else:
                is_running = True
                pid = running_processes[script_id]['process'].pid
        else:
            is_running = False
            pid = None

    # For web apps: also check if accessible via URL (might be running but not tracked)
    if not is_running:
        config = load_config()
        script = next((s for s in config.get('scripts', []) if s['id'] == script_id), None)
        if script and 'url' in script and script['url']:
            if is_url_accessible(script['url']):
                is_running = True
                pid = None  # We don't know the PID if it's not tracked
                logger.info(f"Script {script_id} detected as running via URL check")

    return {
        'running': is_running,
        'pid': pid
    }


@app.post("/api/client/registered")
async def get_client_registered_scripts(request_data: dict = None):
    """Get list of script IDs that this client is registered for."""
    try:
        client_id = request_data.get('client_id') if request_data else None
        if not client_id:
            return {'registered_scripts': []}

        clients = load_web_app_clients()
        registered_scripts = []

        # Find all scripts this client is registered for
        for script_id, client_list in clients.items():
            if client_id in client_list:
                registered_scripts.append(script_id)

        return {'registered_scripts': registered_scripts}

    except Exception as e:
        logger.error(f"Error getting registered scripts: {e}")
        return {'registered_scripts': []}


@app.post("/api/client/deregister")
async def deregister_client(request: Request):
    """
    Deregister a client from all registered scripts.
    Called by the browser on page close/unload via sendBeacon.
    """
    try:
        body = await request.body()
        if not body:
            return JSONResponse({'success': False, 'message': 'No body'})
        request_data = json.loads(body)
        client_id = request_data.get('client_id')

        if not client_id:
            return JSONResponse({'success': False, 'message': 'No client_id'})

        clients = load_web_app_clients()
        deregistered = []

        for script_id in list(clients.keys()):
            if client_id in clients[script_id]:
                clients[script_id].remove(client_id)
                deregistered.append(script_id)
                if not clients[script_id]:
                    del clients[script_id]

        if deregistered:
            save_web_app_clients(clients)
            logger.info(f"Deregistered client {client_id} from scripts on page close: {deregistered}")

        return JSONResponse({'success': True, 'deregistered': deregistered})

    except Exception as e:
        logger.error(f"Error deregistering client: {e}")
        return JSONResponse({'success': False, 'message': str(e)})


@app.post("/api/scripts/{script_id}/cleanup-clients")
async def cleanup_script_clients(script_id: str):
    """
    Clean up all client registrations for a script.
    Useful for clearing orphaned clients when a service is stuck.
    """
    try:
        clients = load_web_app_clients()
        if script_id in clients:
            count = len(clients[script_id])
            del clients[script_id]
            save_web_app_clients(clients)
            logger.info(f"Cleaned up {count} client registrations for {script_id}")
            return {
                'success': True,
                'message': f'Cleared {count} client registration(s)',
                'cleared_count': count
            }
        else:
            return {
                'success': True,
                'message': 'No clients registered',
                'cleared_count': 0
            }
    except Exception as e:
        logger.error(f"Error cleaning up clients for {script_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/browse")
async def browse_files(path: str = DEFAULT_BROWSE_PATH):
    """
    Browse server filesystem.
    Returns list of files/folders in the specified path.
    """
    try:
        # Expand user home directory
        requested_path = os.path.expanduser(path)
        requested_path = os.path.abspath(requested_path)

        # Security: Validate path is within allowed directories
        if not is_path_allowed(requested_path):
            raise HTTPException(
                status_code=403,
                detail="Access to this directory is not allowed"
            )

        # Check if path exists
        if not os.path.exists(requested_path):
            raise HTTPException(status_code=404, detail="Path not found")

        # Check if it's a directory
        if not os.path.isdir(requested_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")

        # List directory contents
        entries = []
        try:
            for entry_name in sorted(os.listdir(requested_path)):
                entry_path = os.path.join(requested_path, entry_name)

                try:
                    is_dir = os.path.isdir(entry_path)
                    stat_info = os.stat(entry_path)

                    entries.append({
                        'name': entry_name,
                        'path': entry_path,
                        'is_directory': is_dir,
                        'size': stat_info.st_size if not is_dir else None,
                        'modified': stat_info.st_mtime
                    })
                except (PermissionError, OSError):
                    # Skip entries we can't read
                    continue
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")

        # Get parent directory path
        parent_path = os.path.dirname(requested_path) if requested_path != '/' else None

        return {
            'current_path': requested_path,
            'parent_path': parent_path,
            'entries': entries,
            'allowed_roots': ALLOWED_BROWSE_PATHS,
            'default_path': DEFAULT_BROWSE_PATH
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error browsing path {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_config():
    """Return the full scripts config (without IP replacement, for editing)."""
    config = load_config()
    return config.get('scripts', [])


@app.post("/api/config/scripts")
async def create_script(script: dict):
    """Add a new script to the config."""
    try:
        if not script.get('id') or not script.get('id', '').strip():
            raise HTTPException(status_code=400, detail="Script 'id' is required")
        if not script.get('name') or not script.get('name', '').strip():
            raise HTTPException(status_code=400, detail="Script 'name' is required")
        if not script.get('command') or not script.get('command', '').strip():
            raise HTTPException(status_code=400, detail="Script 'command' is required")

        # Validate id format (alphanumeric + hyphens only)
        if not re.match(r'^[a-z0-9-]+$', script['id']):
            raise HTTPException(status_code=400, detail="Script 'id' must contain only lowercase letters, numbers, and hyphens")

        config = load_config()
        scripts = config.get('scripts', [])

        if any(s['id'] == script['id'] for s in scripts):
            raise HTTPException(status_code=409, detail=f"Script with id '{script['id']}' already exists")

        scripts.append(script)
        config['scripts'] = scripts
        save_config(config)
        logger.info(f"Created new script: {script['id']}")
        return {'success': True, 'script': script}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating script: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/config/scripts/{script_id}")
async def update_script(script_id: str, script: dict):
    """Update an existing script in the config."""
    try:
        config = load_config()
        scripts = config.get('scripts', [])

        idx = next((i for i, s in enumerate(scripts) if s['id'] == script_id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"Script '{script_id}' not found")

        # Preserve the original id unless explicitly changed
        script['id'] = script.get('id', script_id)

        # If id is changing, check for conflicts
        if script['id'] != script_id:
            if any(s['id'] == script['id'] for s in scripts):
                raise HTTPException(status_code=409, detail=f"Script with id '{script['id']}' already exists")

        scripts[idx] = script
        config['scripts'] = scripts
        save_config(config)
        logger.info(f"Updated script: {script_id}")
        return {'success': True, 'script': script}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating script {script_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/config/scripts/{script_id}")
async def delete_script(script_id: str):
    """Delete a script from the config."""
    try:
        config = load_config()
        scripts = config.get('scripts', [])

        original_len = len(scripts)
        scripts = [s for s in scripts if s['id'] != script_id]

        if len(scripts) == original_len:
            raise HTTPException(status_code=404, detail=f"Script '{script_id}' not found")

        config['scripts'] = scripts
        save_config(config)
        logger.info(f"Deleted script: {script_id}")
        return {'success': True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting script {script_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info('Client connected via WebSocket')

    try:
        await websocket.send_json({
            'type': 'connected',
            'message': 'Connected to script runner'
        })

        # Listen for messages to subscribe to specific scripts
        while True:
            data = await websocket.receive_json()

            if data.get('type') == 'subscribe':
                script_id = data.get('script_id')
                if script_id:
                    async with process_lock:
                        if script_id in running_processes:
                            # Add WebSocket to subscribers
                            running_processes[script_id]['websockets'].add(websocket)
                            logger.info(f"WebSocket subscribed to {script_id}")

                            # Send any buffered output
                            output_buffer = running_processes[script_id].get('output_buffer', [])
                            if output_buffer:
                                logger.info(f"Sending {len(output_buffer)} buffered messages for {script_id}")
                                for msg in output_buffer:
                                    try:
                                        await websocket.send_json(msg)
                                    except Exception as e:
                                        logger.error(f"Error sending buffered message: {e}")

                                # Clear buffer and clean up if process completed
                                output_buffer.clear()
                                if running_processes[script_id].get('completed'):
                                    # Clean up temp file if it exists
                                    temp_file = running_processes[script_id].get('output_file')
                                    if temp_file and os.path.exists(temp_file):
                                        try:
                                            os.remove(temp_file)
                                            logger.info(f"Cleaned up temp file for {script_id}: {temp_file}")
                                        except Exception as e:
                                            logger.error(f"Failed to delete temp file {temp_file}: {e}")
                                    # Remove from running processes now that output was delivered
                                    del running_processes[script_id]
                                    logger.info(f"Cleaned up completed process {script_id} after delivering buffered output")

            elif data.get('type') == 'unsubscribe':
                script_id = data.get('script_id')
                if script_id:
                    async with process_lock:
                        if script_id in running_processes:
                            running_processes[script_id]['websockets'].discard(websocket)
                            logger.info(f"WebSocket unsubscribed from {script_id}")

    except WebSocketDisconnect:
        logger.info('Client disconnected from WebSocket')
    except Exception as e:
        logger.error(f'WebSocket error: {e}')
    finally:
        connected_clients.discard(websocket)
        # Remove from all script subscriptions
        async with process_lock:
            for process_info in running_processes.values():
                process_info['websockets'].discard(websocket)


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    os._exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("SERVICE_LAUNCHER_PORT", 5000))
    logger.info(f"Starting Script Runner with FastAPI + Uvicorn on port {port}...")
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )
