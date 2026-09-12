"""Run every self-check in the repo. One command, exits non-zero on any failure.

    python scripts/check.py
"""
import subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULES = [
    "backend.core.bandstack", "backend.core.ingest", "backend.core.feasibility",
    "backend.kernel.spectral", "backend.kernel.segmentation",
    "backend.kernel.measurement", "backend.kernel.executor",
    "backend.planner.intent", "backend.planner.language", "backend.planner.phrases",
    "backend.planner.places",
    "backend.planner.tier_b", "backend.planner.tier_c",
    "backend.planner.validator",
    "backend.rag.retriever",
    "backend.pipeline", "backend.ledger", "backend.app",
]

def main():
    fails = []
    for m in MODULES:
        r = subprocess.run([sys.executable, "-m", m], cwd=ROOT,
                           capture_output=True, text=True)
        out = (r.stdout + r.stderr).strip().splitlines()
        tail = "\n".join(out[-12:]) if r.returncode else out[-1] if out else ""
        print(f"{'PASS' if r.returncode == 0 else 'FAIL'}  {m}")
        if r.returncode:
            print("      " + tail.replace("\n", "\n      "))
            fails.append(m)
        elif tail:
            print(f"      {tail}")
    print()
    print(f"{len(MODULES) - len(fails)}/{len(MODULES)} passed")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
