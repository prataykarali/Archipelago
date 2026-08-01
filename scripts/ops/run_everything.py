import subprocess
import time
import sys
import os

# Stop any running processes first
print("Stopping any existing services...")
subprocess.run(["./scripts/ops/serve.sh", "stop"])

# Python interpreter from venv
venv_python = os.path.abspath(".venv/bin/python")
lt_path = '/home/pratay-karali/.nvm/versions/node/v22.23.1/bin/lt'

processes = []

try:
    # 1. Start Inference Server (port 5051)
    print("Starting Inference Server on port 5051...")
    proc_inference = subprocess.Popen(
        [venv_python, "-m", "archipelago.apps.inference_app"],
        stdout=open("logs/inference_run.log", "w"),
        stderr=subprocess.STDOUT
    )
    processes.append(proc_inference)

    # 2. Start Graph Server (port 5050)
    print("Starting Graph Server on port 5050...")
    proc_graph = subprocess.Popen(
        [venv_python, "graph_server.py"],
        stdout=open("logs/graph_run.log", "w"),
        stderr=subprocess.STDOUT
    )
    processes.append(proc_graph)

    # 3. Start Chat Server (port 5052)
    print("Starting Chat Server on port 5052...")
    proc_chat = subprocess.Popen(
        [venv_python, "chat_server.py"],
        stdout=open("logs/chat_run.log", "w"),
        stderr=subprocess.STDOUT
    )
    processes.append(proc_chat)

    # Wait for the servers to bind (let's wait 12s to load embedding models)
    print("Waiting 12 seconds for servers to initialize...")
    time.sleep(12)

    # 4. Start Chat UI LocalTunnel (port 5052)
    print("Starting Chat UI LocalTunnel...")
    proc_lt_chat = subprocess.Popen(
        [lt_path, '--port', '5052'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append(proc_lt_chat)

    # 5. Start Graph UI LocalTunnel (port 5050)
    print("Starting Graph UI LocalTunnel...")
    proc_lt_graph = subprocess.Popen(
        [lt_path, '--port', '5050'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append(proc_lt_graph)

    # Read Chat UI URL
    chat_url_line = proc_lt_chat.stdout.readline()
    print(f"Chat UI Public URL: {chat_url_line.strip()}")
    with open('logs/lt_chat.log', 'w') as f:
        f.write(chat_url_line)

    # Read Graph UI URL
    graph_url_line = proc_lt_graph.stdout.readline()
    print(f"Graph UI Public URL: {graph_url_line.strip()}")
    with open('logs/lt_graph.log', 'w') as f:
        f.write(graph_url_line)

    print("All services and tunnels started successfully! Keeping alive...")

    # Keep running
    while True:
        # Check if any process has exited
        for name, p in [("inference", proc_inference), ("graph", proc_graph), ("chat", proc_chat)]:
            if p.poll() is not None:
                print(f"Server {name} has exited unexpectedly!")
                sys.exit(1)
        for name, p in [("lt_chat", proc_lt_chat), ("lt_graph", proc_lt_graph)]:
            if p.poll() is not None:
                print(f"Tunnel {name} has exited unexpectedly!")
                sys.exit(1)
        time.sleep(1)

except Exception as e:
    print(f"Error occurred: {e}")
finally:
    print("Terminating all child processes...")
    for p in processes:
        try:
            p.terminate()
        except (ProcessLookupError, OSError) as exc:
            print(f"terminate failed for pid {getattr(p, 'pid', '?')}: {exc}")
    print("Clean up complete.")
