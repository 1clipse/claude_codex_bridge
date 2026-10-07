"""Native launcher entrypoint; reuse the shared wrapper's guards and metadata."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'lib'))

import ccb
from platforms.windows.herdr.entrypoint import run_native_cli_entrypoint


if __name__ == '__main__':
    raise SystemExit(ccb.main(entrypoint=run_native_cli_entrypoint))
