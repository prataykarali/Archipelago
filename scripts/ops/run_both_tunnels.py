import subprocess
import time
import sys

lt_path = '/home/pratay-karali/.nvm/versions/node/v22.23.1/bin/lt'

print("Starting Chat UI tunnel on port 5052...")
proc_chat = subprocess.Popen(
    [lt_path, '--port', '5052'],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

print("Starting Graph UI tunnel on port 5050...")
proc_graph = subprocess.Popen(
    [lt_path, '--port', '5050'],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

# Read Chat UI URL
chat_url_line = proc_chat.stdout.readline()
print(f"Chat UI: {chat_url_line.strip()}")
with open('logs/lt_chat.log', 'w') as f:
    f.write(chat_url_line)

# Read Graph UI URL
graph_url_line = proc_graph.stdout.readline()
print(f"Graph UI: {graph_url_line.strip()}")
with open('logs/lt_graph.log', 'w') as f:
    f.write(graph_url_line)

print("Tunnels started successfully! Keeping alive...")

try:
    while True:
        # Check if processes are still alive
        if proc_chat.poll() is not None:
            print("Chat tunnel exited!")
            break
        if proc_graph.poll() is not None:
            print("Graph tunnel exited!")
            break
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    proc_chat.terminate()
    proc_graph.terminate()
