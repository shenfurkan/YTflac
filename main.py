"""
Convenience entry point — equivalent to `ytflac` console script.
Run with:  python main.py
"""
from ytflac.gui.main import run
import sys

if __name__ == "__main__":
    sys.exit(run())
