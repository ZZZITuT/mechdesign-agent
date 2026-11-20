"""``python -m mechdesign`` - starts the web app when called without arguments."""

import sys

from .cli import main

raise SystemExit(main(sys.argv[1:] or ["serve"]))
