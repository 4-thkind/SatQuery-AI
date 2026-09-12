"""Rebuild every demo data artefact from scratch, then verify it.

    python scripts/build_data.py

Exits non-zero if verification fails, so it works as a CI gate.
"""

import subprocess
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
# register_real.py runs AFTER make_manifest.py: that step rewrites
# manifest.json from scratch off data/demo/*.tif, so real-scene entries
# appended earlier would be silently erased.
STEPS = ["make_scenes.py", "make_previews.py", "make_manifest.py",
         "register_real.py", "make_rainfall.py", "verify_scenes.py"]


def main():
    for s in STEPS:
        print(f"\n=== {s} " + "=" * (60 - len(s)))
        r = subprocess.run([sys.executable, str(HERE / s)])
        if r.returncode != 0:
            print(f"\nFAILED at {s}")
            return r.returncode
    print("\n=== data build complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
