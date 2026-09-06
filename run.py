"""One command to build, verify and serve. This is the entry point.

    python run.py            build if needed, verify, serve, open the browser
    python run.py --full     force a data rebuild first (~90 s)
    python run.py --check    build + verify only, no server (CI / pre-flight)
    python run.py --serve    skip checks, just serve (fastest restart)
    python run.py --port N   serve somewhere other than 8000

Why a script rather than a chain of shell commands: `uvicorn` blocks, so
`... && python scripts/ui_check.py` after it never runs. The server has to start
in the background, be waited for, then be torn down again. That is enough moving
parts to be worth writing once.

Every step prints PASS or FAIL and a non-zero exit stops the run.
"""

from __future__ import annotations

import argparse
import http.client
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
PY = sys.executable
DEMO = ROOT / "data" / "demo"

# Windows consoles default to cp1252 and the narration is multilingual, so every
# subprocess gets UTF-8 forced or the Punjabi and Tamil output raises
# UnicodeEncodeError before it reaches the terminal.
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def step(name: str) -> None:
    print(f"\n\033[1m>> {name}\033[0m", flush=True)


def run(args: list[str], quiet: bool = False) -> bool:
    """Run a subprocess, streaming or capturing. True when it exits 0."""
    r = subprocess.run(args, cwd=ROOT, env=ENV,
                       capture_output=quiet, text=True, encoding="utf-8",
                       errors="replace")
    if quiet and r.returncode != 0:
        print(r.stdout or "", r.stderr or "")
    return r.returncode == 0


def port_busy(port: int) -> int | None:
    """PID holding `port`, or None. netstat is the only thing guaranteed present
    on a bare Windows box -- psutil would be another dependency to install."""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                             timeout=15).stdout
    except Exception:
        return None
    for line in out.splitlines():
        if f":{port} " in line and "LISTENING" in line:
            parts = line.split()
            if parts and parts[-1].isdigit():
                return int(parts[-1])
    return None


def wait_for_health(port: int, timeout: float = 60.0) -> bool:
    """Poll /health until the server answers. Starting uvicorn and immediately
    firing requests at it is a race; on a cold start rasterio and skimage take
    several seconds to import."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
            c.request("GET", "/api/v1/health")
            if c.getresponse().status == 200:
                return True
        except Exception:
            time.sleep(0.5)
        finally:
            try:
                c.close()
            except Exception:
                pass
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="force a data rebuild")
    ap.add_argument("--check", action="store_true", help="verify only, no server")
    ap.add_argument("--serve", action="store_true", help="serve only, skip checks")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-open", action="store_true", help="do not open a browser")
    a = ap.parse_args()

    # --- 1. data ---------------------------------------------------------
    if not a.serve:
        have = (DEMO / "truth.json").exists() and len(list(DEMO.glob("*.tif"))) == 7
        if a.full or not have:
            step("Building demo scenes  (~90 s)")
            if not run([PY, "scripts/build_data.py"]):
                print("\nFAILED: scene generation. Fix this before anything else.")
                return 1
        else:
            step("Demo scenes present -- skipping rebuild  (--full to force)")

    # --- 2. backend ------------------------------------------------------
    if not a.serve:
        step("Backend self-checks")
        if not run([PY, "scripts/check.py"]):
            print("\nFAILED: a backend check did not pass. The server would still "
                  "start, but a measurement is wrong -- fix before demoing.")
            return 1

    if a.check:
        print("\n\033[1mAll checks passed.\033[0m  Run without --check to serve.")
        return 0

    # --- 3. free the port ------------------------------------------------
    # A previous run left holding the port is the single most common reason the
    # backend "does not work": uvicorn exits with "address already in use" and
    # the message scrolls past.
    pid = port_busy(a.port)
    if pid:
        step(f"Port {a.port} held by PID {pid} -- stopping it")
        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                       capture_output=True, text=True)
        time.sleep(1.5)
        if port_busy(a.port):
            print(f"\nFAILED: could not free port {a.port}. "
                  f"Try: python run.py --port {a.port + 1}")
            return 1

    # --- 4. serve --------------------------------------------------------
    step(f"Starting server on http://127.0.0.1:{a.port}")
    srv = subprocess.Popen(
        [PY, "-m", "uvicorn", "backend.app:app", "--port", str(a.port),
         "--log-level", "warning"],
        cwd=ROOT, env=ENV)

    try:
        if not wait_for_health(a.port):
            print("\nFAILED: server did not become healthy. Output above.")
            srv.terminate()
            return 1
        print(f"   healthy")

        # --- 5. UI check -------------------------------------------------
        if not a.serve:
            step("Browser check")
            env_ui = {**ENV, "SATQUERY_UI_PORT": str(a.port)}
            r = subprocess.run([PY, "scripts/ui_check.py"], cwd=ROOT, env=env_ui,
                               text=True, encoding="utf-8", errors="replace")
            if r.returncode != 0:
                print("\nBrowser check failed -- the server is still running so "
                      "you can look at it, but do not demo until this is green.")

        print(f"\n\033[1m  SatQuery AI  ->  http://127.0.0.1:{a.port}\033[0m")
        print("   Ctrl+C to stop.\n")
        if not a.no_open:
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{a.port}")
        srv.wait()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except subprocess.TimeoutExpired:
            srv.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
