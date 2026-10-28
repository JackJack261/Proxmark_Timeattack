"""Launcher: ``python3 pm3trainer.py [--port /dev/ttyACM0]``."""
import sys

from pm3trainer.__main__ import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
