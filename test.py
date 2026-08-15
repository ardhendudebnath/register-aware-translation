"""
Deprecated shim. This file used to contain ``print("Hello")``.

The real suite lives in ``tests/``:

    python -m pytest tests/ -q

and the register evaluation in:

    python -m evaluation.run
"""

import subprocess
import sys


if __name__ == "__main__":
    print(__doc__.strip(), "\n")
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", "tests/", "-q"]))
