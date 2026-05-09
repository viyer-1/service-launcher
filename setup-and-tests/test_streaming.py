#!~/.venvs/main/bin/python3
"""
Test if subprocess streaming works
"""
import subprocess
import os

# Test the exact command that script_runner uses
cmd = ['stdbuf', '-oL', '-eL', 'bash', '-c', 'echo "Line 1" && sleep 1 && echo "Line 2" && sleep 1 && echo "Line 3"']

print(f"Running command: {cmd}")
print("="*60)

env = os.environ.copy()
env['PYTHONUNBUFFERED'] = '1'
env['DEBIAN_FRONTEND'] = 'noninteractive'

process = subprocess.Popen(
    cmd,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    bufsize=0,
    universal_newlines=False,
    env=env
)

print(f"Process started, PID: {process.pid}")

# Read output line by line (same as stream_output)
line_count = 0
for line in iter(process.stdout.readline, b''):
    if line:
        line_count += 1
        decoded_line = line.decode('utf-8', errors='replace')
        print(f"[Line {line_count}] {decoded_line.strip()}")

process.wait()
print(f"\nProcess completed with return code: {process.returncode}")
print(f"Total lines: {line_count}")
