#!/usr/bin/env python3
"""
PRISM — Single Entry-Point Launcher
Usage: python run.py

Starts:
  - FastAPI backend  on http://localhost:8000
  - React patient UI on http://localhost:5173 (npm run dev)
  - React admin  UI  on http://localhost:5174 (npm run admin)
"""
import subprocess, sys, os, time, signal, threading
from pathlib import Path

ROOT    = Path(__file__).parent
BACKEND = ROOT / "backend"
FRONTEND= ROOT / "frontend"

processes = []

def print_banner():
    print("""
+----------------------------------------------------------+
|   PRISM -- Patient-centric Retrieval Intelligence System |
|   Version 2.0 | Feuji AI/ML Data Science Team            |
+----------------------------------------------------------+
|   Backend API:    http://localhost:8000                  |
|   API Docs:       http://localhost:8000/docs             |
|   Patient App:    http://localhost:5177                  |
|   Admin Portal:   http://localhost:5178 (use /admin)     |
+----------------------------------------------------------+
""")

def stream_output(proc, prefix, color):
    colors = {"backend": "\033[36m", "patient": "\033[32m", "admin": "\033[35m"}
    c = colors.get(prefix, "")
    reset = "\033[0m"
    for line in iter(proc.stdout.readline, b''):
        try:
            print(f"{c}[{prefix}]{reset} {line.decode().rstrip()}")
        except Exception:
            pass

def check_env():
    env_file = ROOT / ".env"
    if not env_file.exists():
        print("[WARN] .env not found. Copying from .env.example...")
        import shutil
        shutil.copy(ROOT / ".env.example", env_file)
        print("   Edit .env and add your ANTHROPIC_API_KEY before using the chat.")

def check_node():
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True, shell=True)
        subprocess.run(["npm", "--version"], capture_output=True, check=True, shell=True)
        return True
    except FileNotFoundError:
        print("[ERROR] Node.js/npm not found. Install Node.js from https://nodejs.org and ensure npm is on PATH.")
        return False
    except Exception as e:
        print(f"[ERROR] Node.js/npm check failed: {e}")
        return False

def check_python_deps():
    try:
        import fastapi, uvicorn, langchain
        return True
    except ImportError as e:
        print(f"[WARN] Missing Python deps: {e}")
        print(f"   Run: cd backend && pip install -r requirements.txt")
        return False

def install_frontend():
    nm = FRONTEND / "node_modules"
    if not nm.exists():
        print("[INSTALL] Installing frontend dependencies...")
        try:
            subprocess.run(["npm", "install"], cwd=FRONTEND, check=True, shell=True)
            print("[SUCCESS] Frontend deps installed")
        except FileNotFoundError:
            print("[ERROR] npm not found. Skipping frontend dependency install.")
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to install frontend dependencies: {e}")


def start_backend():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
    )
    processes.append(proc)
    t = threading.Thread(target=stream_output, args=(proc, "backend", "cyan"), daemon=True)
    t.start()
    return proc

def start_patient():
    env = os.environ.copy()
    # Increase header size to handle large metadata in dev session
    env["NODE_OPTIONS"] = "--max-http-header-size=64000"
    proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=FRONTEND, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, env=env
    )
    processes.append(proc)
    t = threading.Thread(target=stream_output, args=(proc, "patient", "green"), daemon=True)
    t.start()
    return proc

def start_admin():
    env = os.environ.copy()
    env["NODE_OPTIONS"] = "--max-http-header-size=64000"
    proc = subprocess.Popen(
        ["npm", "run", "admin"],
        cwd=FRONTEND, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True, env=env
    )
    processes.append(proc)
    t = threading.Thread(target=stream_output, args=(proc, "admin", "magenta"), daemon=True)
    t.start()
    return proc

def shutdown(sig, frame):
    print("\n\n[STOP] Shutting down PRISM...")
    for p in processes:
        try: p.terminate()
        except Exception: pass
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print_banner()
    check_env()

    if not check_python_deps():
        print("Install Python deps first and retry.")

    if check_node():
        install_frontend()

    print("[START] Starting PRISM services...\n")

    # Backend
    print("[RUN] Starting FastAPI backend on :8000...")
    start_backend()
    time.sleep(3)

    # Frontend
    if check_node():
        print("[RUN] Starting Patient UI on :5173...")
        start_patient()
        time.sleep(1)
        print("[RUN] Starting Admin Portal on :5174...")
        start_admin()

    print("\n[SUCCESS] All services started! Press Ctrl+C to stop.\n")

    # Keep alive
    try:
        while True:
            time.sleep(1)
            # Check if backend crashed
            if processes and processes[0].poll() is not None:
                print("[ERROR] Backend crashed. Restarting...")
                processes.pop(0)
                start_backend()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
