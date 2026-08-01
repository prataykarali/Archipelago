import subprocess
import sys
import time
import os

if len(sys.argv) < 3:
    print("Usage: python launch_tunnels.py <port> <log_file>")
    sys.exit(1)

port = sys.argv[1]
log_path = sys.argv[2]

# Use absolute path to lt to avoid NVM/PATH issues in background shells
lt_path = '/home/pratay-karali/.nvm/versions/node/v22.23.1/bin/lt'

# Start the localtunnel process
proc = subprocess.Popen(
    [lt_path, '--port', port],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

# Read the first line of output (contains the URL)
line = proc.stdout.readline()
print(f"Port {port} tunnel started: {line.strip()}")

# Write to log file
with open(log_path, 'w') as f:
    f.write(line)
    f.flush()

# Loop to keep the process alive and forward any output
try:
    while True:
        next_line = proc.stdout.readline()
        if not next_line:
            break
        with open(log_path, 'a') as f:
            f.write(next_line)
            f.flush()
except KeyboardInterrupt:
    pass
finally:
    proc.terminate()
