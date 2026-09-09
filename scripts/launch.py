from __future__ import annotations

import argparse
import atexit
import json
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_URL = "http://127.0.0.1:8765/api/health"
FRONTEND_URL = "http://127.0.0.1:3000/"
BACKEND_MARKER = '"product":"Transcript Review Studio"'
FRONTEND_MARKER = "Transcript Review Studio"
processes: list[subprocess.Popen] = []


def response_contains(url: str, marker: str, timeout: float = 0.7) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                return False
            return marker in response.read(256_000).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_for(url: str, marker: str, process: subprocess.Popen | None, seconds: int = 35) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if response_contains(url, marker):
            return
        if process and process.poll() is not None:
            raise RuntimeError(f"A local service exited early with code {process.returncode}.")
        time.sleep(0.3)
    raise RuntimeError(f"Timed out waiting for {url}")


def stop_services() -> None:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
    for process in reversed(processes):
        if process.poll() is None:
            try:
                process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                process.kill()


def launch() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--practice", action="store_true")
    args = parser.parse_args()
    backend_url = BACKEND_URL.replace(":8765", ":8766") if args.practice else BACKEND_URL
    frontend_url = FRONTEND_URL + ("?practice=1" if args.practice else "")
    python = ROOT / ".venv" / "bin" / "python"
    if not python.exists():
        raise RuntimeError("Setup has not been run. Double-click ‘Setup Transcript Review Studio.command’ first.")
    if not (ROOT / "node_modules").exists():
        raise RuntimeError("JavaScript dependencies are missing. Run the setup command first.")

    backend_process: subprocess.Popen | None = None
    frontend_process: subprocess.Popen | None = None
    if not response_contains(backend_url, BACKEND_MARKER):
        backend_process = subprocess.Popen([str(python), "backend/run.py", *(["--practice"] if args.practice else [])], cwd=ROOT)
        processes.append(backend_process)
    wait_for(backend_url, BACKEND_MARKER, backend_process)
    with urllib.request.urlopen(backend_url, timeout=5) as response:
        capabilities = json.load(response)["capabilities"]
    if bool(capabilities.get("practice_mode")) != args.practice:
        raise RuntimeError("An incompatible workspace is already using the service port. Close its launcher before continuing.")
    print("✓ Local processing service is ready")

    if not response_contains(FRONTEND_URL, FRONTEND_MARKER):
        frontend_process = subprocess.Popen(
            ["npm", "run", "start", "--", "--hostname", "127.0.0.1"],
            cwd=ROOT,
        )
        processes.append(frontend_process)
    wait_for(FRONTEND_URL, FRONTEND_MARKER, frontend_process)
    print("✓ Transcript Review Studio is ready")
    print(f"  {frontend_url}")
    print("Close this window or press Control-C to stop the local app.")
    webbrowser.open(frontend_url)

    if processes:
        while all(process.poll() is None for process in processes):
            time.sleep(0.8)
    else:
        print("The app was already running. You may close this launcher window.")


def handle_signal(_signum: int, _frame: object) -> None:
    stop_services()
    raise SystemExit(0)


if __name__ == "__main__":
    atexit.register(stop_services)
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    try:
        launch()
    except Exception as exc:
        print(f"\nCould not start Transcript Review Studio:\n{exc}\n", file=sys.stderr)
        print("Press Return to close this window.")
        try:
            input()
        except EOFError:
            pass
        raise SystemExit(1) from exc
